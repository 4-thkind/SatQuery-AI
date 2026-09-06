"""Generate synthetic Sentinel-2-like GeoTIFF demo scenes with known ground truth.

Why synthetic: the ground-truth area is exact by construction, so every number the
kernel produces is checkable against `truth.json`. Real downloads have no label.

Scenes are 10m/px UTM 45N over Supaul, Bihar (Kosi basin). Band order matches
Sentinel-2 L2A subset: B03(green) B04(red) B08(nir) B11(swir16), reflectance x10000
as uint16 -- the same dtype/scaling a real S2 product ships in.

Run:  python scripts/make_scenes.py
"""

import json
import pathlib

import numpy as np
import rasterio
from rasterio.transform import from_origin

SIZE = 1024           # px
RES = 10.0            # m/px  -> 10.24 km across, 104.86 km^2 scene
PX_AREA = RES * RES   # 100 m^2
ORIGIN_X, ORIGIN_Y = 460000.0, 2890000.0   # UTM 45N, ~Supaul Bihar
CRS = "EPSG:32645"
BANDS = ["green", "red", "nir", "swir16"]

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "demo"

# Reflectance signatures (0-1) per band: green, red, nir, swir16.
# Values from typical S2 L2A surface reflectance for each cover type.
SIG = {
    "water":     (0.055, 0.035, 0.020, 0.010),
    "turbid":    (0.090, 0.085, 0.055, 0.025),   # sediment-laden flood water
    "veg":       (0.070, 0.045, 0.340, 0.180),   # healthy cropland
    # Senesced veg: NIR still exceeds SWIR (cell structure intact), so NDBI stays
    # negative -- otherwise background is indistinguishable from built-up.
    "dry_veg":   (0.110, 0.130, 0.280, 0.200),   # senesced / post-harvest
    "soil":      (0.150, 0.190, 0.240, 0.300),   # bare fallow
    "urban":     (0.170, 0.180, 0.195, 0.300),   # concrete: SWIR well above NIR
    "burn":      (0.080, 0.095, 0.090, 0.290),   # char: NIR down, SWIR up
    "cloud":     (0.750, 0.750, 0.760, 0.500),
}


def _grid():
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    return x.astype(np.float64), y.astype(np.float64)


def _river(width_px, meander=60.0, offset=0.0):
    """Sinuous N-S river mask. Multi-harmonic centreline and along-track width
    variation, so the channel reads as a river rather than a sine wave."""
    x, y = _grid()
    t = 2 * np.pi * y / (SIZE * 0.75)
    centre = (SIZE * 0.42 + offset
              + meander * np.sin(t)
              + 0.34 * meander * np.sin(2.7 * t + 1.1)
              + 0.15 * meander * np.sin(5.3 * t + 2.4))
    w = width_px * (1.0 + 0.22 * np.sin(3.1 * t + 0.7) + 0.11 * np.sin(7.9 * t))
    # Bank roughness. A channel whose edge follows an exact analytic curve reads as
    # drawn; real banks are scalloped by erosion at every scale. Seeded off the
    # width so the pre- and post-flood channels stay independent.
    bank = _fractal(np.random.default_rng(900 + int(width_px)),
                    octaves=7, persistence=0.62) * width_px * 0.16
    return np.abs(x - centre) <= (w / 2.0 + bank)


def _disc(cx, cy, r, warp=None, seed=None, rough=0.26):
    """Disc with a fractal-warped boundary.

    Warping is the default, not an option: a perfect circle is the single loudest
    "this was generated" cue in a scene, and nothing on the ground -- a town, a
    pond, a burn scar -- has one. Pass rough=0 only if an exact circle is wanted.
    """
    x, y = _grid()
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    if warp is None and rough > 0 and seed is not None:
        # Higher octaves and low persistence deliberately: the boundary needs
        # detail at the scale of tens of metres, not one smooth lobe. A low-octave
        # field displaced the edge by only a few pixels on a 55 px radius, which
        # is invisible -- the disc still read as a drawn circle.
        warp = _fractal(np.random.default_rng(seed), octaves=7, persistence=0.62)
    if warp is not None:
        d = d + warp * r * rough
    return d <= r


def _rect(x0, y0, w, h, seed=None, rough=0.06):
    """Rectangle with a slightly irregular edge -- field blocks and built-up
    parcels have ragged boundaries at 10 m/px, not pixel-straight ones."""
    x, y = _grid()
    if seed is not None and rough > 0:
        r = np.random.default_rng(seed)
        jx = _fractal(r, octaves=7, persistence=0.62) * min(w, h) * rough
        jy = _fractal(r, octaves=7, persistence=0.62) * min(w, h) * rough
        return ((x >= x0 + jx) & (x < x0 + w + jx)
                & (y >= y0 + jy) & (y < y0 + h + jy))
    return (x >= x0) & (x < x0 + w) & (y >= y0) & (y < y0 + h)


def _smooth(a, k):
    """Box blur via cumulative sums. Cheap separable smoothing, no scipy needed."""
    if k < 2:
        return a
    pad = k // 2
    out = a
    for axis in (0, 1):
        p = np.pad(out, [(pad, pad) if i == axis else (0, 0) for i in range(2)],
                   mode="reflect")
        c = np.cumsum(p, axis=axis)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        lo = np.take(c, range(0, out.shape[axis]), axis=axis)
        hi = np.take(c, range(k, k + out.shape[axis]), axis=axis)
        out = (hi - lo) / k
    return out


def _fractal(rng, octaves=5, persistence=0.55):
    """Value-noise fractal in [-1,1]. Gives scenes terrain-like spatial structure
    instead of flat fills, which is what makes a synthetic tile look real."""
    total = np.zeros((SIZE, SIZE))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cells = 2 ** (o + 2)
        coarse = rng.random((cells, cells))
        up = np.kron(coarse, np.ones((SIZE // cells + 1, SIZE // cells + 1)))
        # Two box blurs, not one: a single pass leaves the kron blocks visible as
        # square facets. Convolving a box with itself is a triangle kernel, which
        # is C1-continuous, so the cell edges stop showing.
        k = max(2, SIZE // cells)
        up = _smooth(_smooth(up[:SIZE, :SIZE], k), max(2, k // 2))
        total += amp * (up - up.mean())
        norm += amp
        amp *= persistence
    total /= norm
    m = np.abs(total).max()
    return total / m if m > 0 else total


def _parcels(rng, cell=14, angle_deg=None):
    """Agricultural field mosaic: a rotated grid of plots, each with its own vigour
    offset, plus within-plot gradient and field boundaries.

    Bihar holdings are small -- median under 1 ha -- so at 10 m/px the cell is ~14 px
    (~2 ha), not the 26 px that read as visible chequerboard squares. Three things
    separate this from a chequerboard: sub-plot gradient (no plot is a flat fill),
    darker bund lines on plot edges, and a second finer grid rotated differently so
    the eye cannot lock onto one lattice."""
    x, y = _grid()
    # Domain warp. Sampling a value table on a straight rotated grid always shows
    # the grid: nearest-neighbour indexing plus a box blur produced visible
    # diagonal facets. Displacing the coordinates by a smooth fractal first bends
    # every plot boundary, so the lattice that generates them stops being legible
    # while the plots stay plot-shaped.
    wx = _fractal(rng, octaves=4) * cell * 1.6
    wy = _fractal(rng, octaves=4) * cell * 1.6

    def lattice(cell_u, cell_v, ang, seed_off):
        r = np.random.default_rng(rng.integers(1 << 30) + seed_off)
        a = np.deg2rad(ang)
        xw, yw = x + wx, y + wy
        u = (xw * np.cos(a) + yw * np.sin(a)) / cell_u
        v = (-xw * np.sin(a) + yw * np.cos(a)) / cell_v
        span = int(3 * SIZE / min(cell_u, cell_v)) + 8
        # Fractional part drives both the within-plot gradient and the bund lines.
        fu, fv = u - np.floor(u), v - np.floor(v)
        iu = np.clip((u + span // 2).astype(int), 0, span - 1)
        iv = np.clip((v + span // 2).astype(int), 0, span - 1)
        val = r.normal(0.0, 1.0, (span, span))
        merge = r.random((span, span)) < 0.30    # ~30% of plots join a neighbour
        val = np.where(merge, np.roll(val, 1, axis=1), val)
        plot = val[iv, iu]
        # Each plot tilts slightly across its own extent: irrigation and drainage
        # mean vigour is never uniform inside a bund.
        tilt = r.normal(0.0, 1.0, (span, span))[iv, iu]
        plot = plot + 0.40 * tilt * (fu - 0.5) + 0.30 * tilt * (fv - 0.5)
        # Bunds: the raised earth boundary between plots reads darker than the crop.
        edge = np.minimum(np.minimum(fu, 1 - fu) * cell_u,
                          np.minimum(fv, 1 - fv) * cell_v)
        plot = plot - 0.8 * np.clip(1.2 - edge, 0.0, 1.0)
        return plot

    a1 = rng.uniform(20, 70) if angle_deg is None else angle_deg
    # Three lattices at incommensurate angles, not two. Two rotated grids beat
    # against each other and produce a regular diamond moire -- the tell-tale
    # texture that made the fields look like a generated pattern. A third angle
    # plus per-lattice cell sizes that are not simple multiples destroys the
    # periodicity, leaving irregular plots.
    coarse = lattice(cell * 2.4, cell * 2.4 * rng.uniform(1.2, 1.8), a1, 0)
    mid = lattice(cell * 1.53, cell * 1.53 * rng.uniform(1.1, 1.6),
                  a1 + rng.uniform(31, 47), 3)
    fine = lattice(cell, cell * rng.uniform(1.1, 1.7), a1 + rng.uniform(67, 89), 7)
    return _smooth(0.46 * coarse + 0.31 * mid + 0.23 * fine, 3)


def _render(layers, seed, noise=0.004, texture=True):
    """layers: list of (mask, cover_name), painted in order. First entry is background.

    Masks stay exact -- texture only modulates brightness *within* a class, never
    across the decision boundary, so ground truth in truth.json remains valid.
    """
    rng = np.random.default_rng(seed)
    arr = np.zeros((len(BANDS), SIZE, SIZE), dtype=np.float64)
    for mask, cover in layers:
        for bi, refl in enumerate(SIG[cover]):
            arr[bi][mask] = refl

    if texture:
        # Multiplicative, class-relative.
        #
        # Amplitude matters more than it looks. Real cropland NIR varies roughly
        # 2x between plots -- crop type, sowing date, irrigation, soil moisture all
        # move it. At the +-6% used earlier every class was effectively a constant
        # fill, and no amount of tone curve in the preview can rescue that: the
        # variance simply is not in the data. +-28% is what makes the tile read as
        # imagery. The masks are untouched and the modulation is common to all
        # bands, so every normalised index (a ratio) is unchanged to first order
        # and verify_scenes.py still reproduces ground truth exactly.
        terrain = _fractal(rng)
        fields = _parcels(rng)
        # A finer fractal: without high-frequency content the tile still reads as
        # smooth poster art no matter how good the field mosaic is.
        grain = _fractal(rng, octaves=7, persistence=0.72)
        modulation = 1.0 + 0.150 * terrain + 0.280 * fields + 0.070 * grain
        arr *= np.clip(modulation, 0.35, 1.9)[None, :, :]

        # Per-band gain jitter. Real sensors do not vary identically across bands:
        # a fully correlated modulation leaves every index perfectly flat within a
        # class, which is what makes the false-colour composite look posterised.
        # Kept small -- this one DOES move index values, so it stays well inside
        # the margin verify_scenes.py checks.
        for bi in range(arr.shape[0]):
            arr[bi] *= 1.0 + 0.035 * _fractal(rng, octaves=6, persistence=0.6)

        # Sub-pixel edge softening: real optics have an MTF, hard step edges do not
        # occur. Applied per band, 1 px, so class areas are preserved to <0.1%.
        for bi in range(arr.shape[0]):
            arr[bi] = 0.72 * arr[bi] + 0.28 * _smooth(arr[bi], 3)

    # Sensor noise is proportional to signal (shot noise dominates in the optical),
    # so scale it by reflectance rather than adding a flat floor everywhere.
    arr += rng.normal(0.0, noise, arr.shape) * (0.4 + arr)
    np.clip(arr, 0.0, 1.0, out=arr)
    return (arr * 10000.0).round().astype(np.uint16)


def write(name, arr, description):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=SIZE, width=SIZE, count=len(BANDS),
        dtype="uint16", crs=CRS, transform=from_origin(ORIGIN_X, ORIGIN_Y, RES, RES),
        nodata=0, compress="deflate", tiled=True,
    ) as dst:
        dst.write(arr)
        for i, b in enumerate(BANDS, start=1):
            dst.set_band_description(i, b)
        dst.update_tags(
            SATQUERY_BANDS=",".join(BANDS),
            SATQUERY_SCALE="10000",
            SATQUERY_SYNTHETIC="1",
            SATQUERY_DESC=description,
        )
    return path


def ha(px):
    return round(float(px) * PX_AREA / 10000.0, 2)


def main():
    truth = {}

    # --- 1. Pre-flood: normal river, cropland ------------------------------
    river_pre = _river(24)
    veg = ~river_pre
    town = _disc(760, 300, 55, seed=101, rough=0.34)
    pre = _render([(veg, "veg"), (town, "urban"), (river_pre, "water")], seed=1)
    write("bihar_pre_flood", pre, "Kosi basin, pre-monsoon. Normal channel width.")
    truth["bihar_pre_flood"] = {
        "water_px": int(river_pre.sum()), "water_ha": ha(river_pre.sum()),
    }

    # --- 2. Post-flood: river burst, turbid inundation ---------------------
    river_post = _river(210)                       # channel + floodplain
    # Fractal-warped ponding: floodwater follows micro-topography, so its edge is
    # ragged. The flooded paddy block keeps a partly straight bund edge.
    w = _fractal(np.random.default_rng(21), octaves=4)
    pond = (_disc(300, 780, 95, warp=w) | _disc(690, 690, 78, warp=w)
            | (_rect(600, 640, 180, 120, seed=103, rough=0.10) & (w < 0.45)))
    flood = river_post | pond
    town_dry = town & ~flood
    post = _render(
        [(~flood, "veg"), (town_dry, "urban"), (flood, "turbid"), (_river(30), "water")],
        seed=2,
    )
    write("bihar_post_flood", post, "Kosi basin, post-monsoon. Inundation event.")
    truth["bihar_post_flood"] = {
        "water_px": int(flood.sum()), "water_ha": ha(flood.sum()),
        "delta_vs_pre_ha": ha(flood.sum() - river_pre.sum()),
    }

    # --- 3. Cloudy: same flood, 38% cloud cover -> ABSTAIN/DEGRADE test ----
    # ~35%: enough to trigger DEGRADE, not so much that every intent ABSTAINs.
    # Fractal-perturbed discs so the cloud edge is ragged, then an alpha ramp so
    # it is semi-transparent at the fringe like real cumulus.
    crng = np.random.default_rng(30)
    warp = _fractal(crng, octaves=4) * 90.0
    x, y = _grid()

    def blob(cx, cy, r):
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) + warp
        return np.clip(1.0 - (d - r * 0.72) / (r * 0.45), 0.0, 1.0)

    alpha = np.maximum.reduce([blob(250, 250, 265), blob(770, 665, 205),
                               blob(120, 880, 150)])
    alpha = _smooth(alpha, 9)
    cloud = alpha > 0.5                       # the mask ground truth refers to
    shadow = np.roll(np.roll(cloud, 70, 0), 45, 1) & ~cloud

    # Cloud tops are not flat. Optical depth varies across a cumulus deck, so
    # brightness does too -- painting one constant reflectance gave featureless
    # white blobs, the loudest "this is drawn" cue in the scene. Modulate the
    # cloud reflectance with its own fractal, and let alpha vary with it so the
    # thinner parts are genuinely more transparent.
    puff = _fractal(np.random.default_rng(31), octaves=7, persistence=0.62)
    alpha = np.clip(alpha * (1.0 + 0.22 * puff), 0.0, 1.0)

    cloudy = post.astype(np.float64) / 10000.0
    for bi, refl in enumerate(SIG["cloud"]):
        # +-14%: enough to read as structure, not enough to drop any cloud pixel
        # below the brightness the cloud-fraction heuristic keys on.
        tex = refl * (1.0 + 0.14 * puff)
        cloudy[bi] = cloudy[bi] * (1 - alpha) + tex * alpha
    cloudy[:, shadow] *= 0.45                 # cast shadow, offset from the cloud
    cloudy = (np.clip(cloudy, 0, 1) * 10000).round().astype(np.uint16)
    write("bihar_post_flood_cloudy", cloudy, "Post-flood scene occluded by cloud.")
    truth["bihar_post_flood_cloudy"] = {
        "cloud_px": int(cloud.sum()),
        "cloud_fraction": round(float(cloud.mean()), 4),
    }

    # --- 4. Burn scar: for NBR / dNBR -------------------------------------
    scar = _disc(500, 500, 180, seed=104) | _disc(620, 380, 110, seed=105)
    burn = _render([(~scar, "veg"), (scar, "burn")], seed=4)
    write("forest_burn", burn, "Forest fire scar for NBR analysis.")
    truth["forest_burn"] = {"burn_px": int(scar.sum()), "burn_ha": ha(scar.sum())}

    # --- 5. Urban growth pair: for NDBI change ----------------------------
    built_t1 = _disc(512, 512, 120, seed=106, rough=0.26)
    built_t2 = (built_t1 | _rect(600, 430, 240, 200, seed=107, rough=0.10)
                | _disc(360, 640, 90, seed=108, rough=0.26))
    t1 = _render([(~built_t1, "dry_veg"), (built_t1, "urban")], seed=5)
    t2 = _render([(~built_t2, "dry_veg"), (built_t2, "urban")], seed=6)
    write("urban_t1", t1, "Urban extent, epoch 1.")
    write("urban_t2", t2, "Urban extent, epoch 2.")
    truth["urban_t1"] = {"built_px": int(built_t1.sum()), "built_ha": ha(built_t1.sum())}
    truth["urban_t2"] = {
        "built_px": int(built_t2.sum()), "built_ha": ha(built_t2.sum()),
        "growth_ha": ha(built_t2.sum() - built_t1.sum()),
    }

    # --- 6. Barren / no-water: ABSTAIN sanity check -----------------------
    barren = _render([(np.ones((SIZE, SIZE), bool), "soil")], seed=7)
    write("barren", barren, "Bare soil, no water body. Negative control.")
    truth["barren"] = {"water_px": 0, "water_ha": 0.0}

    meta = {
        "crs": CRS, "res_m": RES, "pixel_area_m2": PX_AREA,
        "size_px": SIZE, "bands": BANDS, "scale_factor": 10000,
        "dtype": "uint16", "note": "Synthetic. Ground truth is exact by construction.",
        "scenes": truth,
    }
    (OUT / "truth.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {len(list(OUT.glob('*.tif')))} scenes -> {OUT}")
    for k, v in truth.items():
        print(f"  {k:26s} {v}")


if __name__ == "__main__":
    main()
