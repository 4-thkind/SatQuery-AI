"""Verify the synthetic scenes are actually analysable.

Fails if an index does not separate its target class, or if Otsu-thresholded
area drifts >5% from the ground truth in truth.json. If this passes, the kernel
has a fixture set it can be tested against.

Run:  python scripts/verify_scenes.py
"""

import json
import pathlib
import sys

import numpy as np
import rasterio

DEMO = pathlib.Path(__file__).resolve().parent.parent / "data" / "demo"
TOL = 0.05      # 5% area tolerance


def read(name):
    with rasterio.open(DEMO / f"{name}.tif") as src:
        arr = src.read().astype(np.float64) / 10000.0
        bands = dict(zip(src.descriptions, arr))
    return bands, arr


def nd(a, b):
    """Normalised difference, safe on zero denominators."""
    den = a + b
    return np.divide(a - b, den, out=np.zeros_like(a), where=np.abs(den) > 1e-9)


def otsu(v, bins=256):
    """Otsu threshold. Same algorithm the kernel uses; if it can't split these
    scenes it won't split real ones either."""
    v = v[np.isfinite(v)]
    hist, edges = np.histogram(v, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2.0
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centres)
    mt = m0[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        var = (mt * w0 / w0[-1] - m0) ** 2 / (w0 * w1)
    var[~np.isfinite(var)] = -1
    return float(centres[int(np.argmax(var))])


def check(label, got, want, unit="ha"):
    if want == 0:
        ok = got < 1.0
        err = got
    else:
        err = abs(got - want) / want
        ok = err <= TOL
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label:34s} got {got:10.2f} {unit}  want {want:10.2f}  "
          f"err {err * 100:5.2f}%")
    return ok


def main():
    truth = json.loads((DEMO / "truth.json").read_text())
    px_ha = truth["pixel_area_m2"] / 10000.0
    scenes = truth["scenes"]
    ok = True

    print("MNDWI water extraction (Otsu):")
    for name in ("bihar_pre_flood", "bihar_post_flood", "barren"):
        b, _ = read(name)
        mndwi = nd(b["green"], b["swir16"])
        t = otsu(mndwi)
        # Barren has one mode only -- Otsu will still split it, so require the
        # threshold to be crossed by a physically-water-like value.
        mask = mndwi > max(t, 0.0)
        ok &= check(f"{name} water", float(mask.sum()) * px_ha,
                    scenes[name]["water_ha"])

    print("\nFlood delta (post - pre):")
    bp, _ = read("bihar_pre_flood")
    bq, _ = read("bihar_post_flood")
    pre = nd(bp["green"], bp["swir16"]) > 0.0
    post = nd(bq["green"], bq["swir16"]) > 0.0
    ok &= check("new inundation", float((post & ~pre).sum()) * px_ha,
                scenes["bihar_post_flood"]["delta_vs_pre_ha"])

    print("\nNBR burn scar (Otsu on inverted NBR):")
    b, _ = read("forest_burn")
    nbr = nd(b["nir"], b["swir16"])
    ok &= check("burn scar", float((nbr < otsu(nbr)).sum()) * px_ha,
                scenes["forest_burn"]["burn_ha"])

    print("\nNDBI built-up:")
    for name in ("urban_t1", "urban_t2"):
        b, _ = read(name)
        ndbi = nd(b["swir16"], b["nir"])
        ok &= check(f"{name} built-up", float((ndbi > otsu(ndbi)).sum()) * px_ha,
                    scenes[name]["built_ha"])

    print("\nNDVI separation (sanity: veg vs water in post-flood):")
    ndvi = nd(bq["nir"], bq["red"])
    water_ndvi = float(ndvi[post].mean())
    land_ndvi = float(ndvi[~post].mean())
    sep = land_ndvi - water_ndvi
    print(f"  [{'PASS' if sep > 0.4 else 'FAIL'}] NDVI land-water separation      "
          f"{sep:.3f} (land {land_ndvi:.3f}, water {water_ndvi:.3f})")
    ok &= sep > 0.4

    print("\nCloud fraction (brightness heuristic):")
    b, _ = read("bihar_post_flood_cloudy")
    frac = float(((b["green"] > 0.4) & (b["red"] > 0.4) & (b["nir"] > 0.4)).mean())
    want = scenes["bihar_post_flood_cloudy"]["cloud_fraction"]
    print(f"  [{'PASS' if abs(frac - want) < 0.03 else 'FAIL'}] "
          f"detected                          {frac:.4f}  want {want:.4f}")
    ok &= abs(frac - want) < 0.03
    if not 0.20 <= want <= 0.50:
        print(f"  [FAIL] cloud fraction {want:.2f} outside DEGRADE band 0.20-0.50")
        ok = False

    print("\n" + ("ALL CHECKS PASSED" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
