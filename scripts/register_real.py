"""Register the real Bhoonidhi LISS-III scenes as selectable scenes.

    python scripts/register_real.py

Run AFTER make_manifest.py: that script rewrites data/demo/manifest.json from
scratch by globbing data/demo/*.tif, so anything appended here is erased by the
next build unless this runs afterwards. build_data.py sequences them correctly.

WHY THIS SCRIPT EXISTS
    The converted scenes have been on disk since Round 2 and the kernel has
    always been able to read them -- scripts/verify_real.py measures them
    directly with load_geotiff. But nothing ever put them in the manifest, and
    the manifest is the only thing /api/v1/scenes reads. So the eight real ISRO
    scenes were invisible in the UI and every visible scene was synthetic.

WHAT IS REAL HERE, STATED PLAINLY
    Resourcesat-2/2A LISS-III, path/row 106/053, eight acquisitions from
    2022-07-01 to 2023-02-02, downloaded from Bhoonidhi (NRSC/ISRO) and
    converted by scripts/ingest_liss3.py. 2048x2048 px at 24 m, four bands
    (GREEN, RED, NIR, SWIR1), bottom-of-atmosphere reflectance scaled by 10000.

    They cover lon 86.36-86.85, lat 25.90-26.34 -- the Kosi basin in Supaul and
    Madhepura districts, Bihar. That is the same geography the synthetic demo
    scenes simulate, which is what makes the pair worth showing together: the
    same question, the same kernel, one scene modelled and one measured.

    ground_truth is empty and stays empty. Nobody labelled these, so there is
    no hectare figure to check the kernel against -- unlike the synthetic
    scenes, where truth.json exists precisely because we generated the answer.
    The frontend already guards for an empty dict.

    There is no SWIR2 band, so NBR cannot be computed and burn-severity
    questions abstain. That refusal is the real sensor's real limitation
    surfacing correctly, not a defect.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import transform_bounds

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

# Reuse the demo renderer rather than reimplementing it: a real scene drawn
# with a different stretch would look like a different product, and the whole
# point is to compare like with like.
from make_previews import stretch, tone  # noqa: E402

CONVERTED = ROOT / "data" / "real" / "converted"
PREVIEWS = ROOT / "data" / "real" / "previews"
MANIFEST = ROOT / "data" / "demo" / "manifest.json"

# Preview edge length. The UI frame renders about 900 px wide, so
# anything past ~1024 is bytes the browser throws away.
PREVIEW_PX = 1024

# Monsoon pairing, so change detection has something honest to compare.
# February is the dry-season baseline; July and August are peak monsoon.
PAIRS = {
    "liss3_106_053_18aug2022": "liss3_106_053_02feb2023",
    "liss3_106_053_02feb2023": "liss3_106_053_18aug2022",
}

SEASON = {
    "01jul2022": "early monsoon",
    "25jul2022": "peak monsoon",
    "18aug2022": "peak monsoon",
    "05oct2022": "post-monsoon",
    "29oct2022": "post-monsoon",
    "22nov2022": "dry season",
    "16dec2022": "dry season",
    "02feb2023": "dry season",
}


def _iso(tag: str) -> str:
    """SATQUERY_DATE is '01-JUL-2022'; the manifest uses ISO."""
    months = {m: f"{i + 1:02d}" for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
    d, m, y = tag.split("-")
    return f"{y}-{months[m.upper()]}-{d}"


def build_previews() -> int:
    """False-colour and natural PNGs, same renderer as the demo scenes."""
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    n = 0
    for tif in sorted(CONVERTED.glob("liss3_*.tif")):
        with rasterio.open(tif) as src:
            b = dict(zip(src.descriptions,
                         src.read().astype(np.float64) / 10000.0))

        # LISS-III genuinely has no blue band, so natural colour needs the same
        # synthetic-blue treatment the demo scenes use. Documented as a preview
        # concern only: the measurement path never reads this channel.
        veg_blue = 0.55 * b["green"] - 0.05 * b["red"] + 0.004
        bright = np.clip((b["green"] - 0.16) / 0.22, 0.0, 1.0)
        blue = veg_blue * (1 - bright) + b["green"] * bright

        vis = dict(lo=0.015, hi=0.175, gamma=1.35)
        natural = np.dstack([stretch(b["red"], **vis),
                             stretch(b["green"], **vis),
                             stretch(blue, **vis)])

        vis_fc = dict(lo=0.010, hi=0.330, gamma=1.25)
        nir_fc = dict(lo=0.010, hi=0.400, gamma=1.45)
        false = np.dstack([stretch(b["nir"], **nir_fc),
                           stretch(b["red"], **vis_fc),
                           stretch(b["green"], **vis_fc)])

        # A LISS-III product is a rotated swath in a north-up raster, so
        # roughly a third of each scene is nodata. Rendered as RGB that third
        # became a solid black wedge -- the image looked cut in half -- and
        # because it sat beneath the mask overlay, the opacity slider appeared
        # dead across it. Alpha=0 there lets the page show through instead.
        #
        # Nodata is detected from the source bands rather than the stretched
        # output: a genuinely dark pixel and an absent one are both near zero
        # after stretching, and only the former should be visible.
        with rasterio.open(tif) as src:
            raw = src.read()
        gap = (raw == 0).all(axis=0)

        # Downscaled to PREVIEW_PX. Full 2048 px RGBA came to 6.17 MB per
        # image and 98.7 MB for the set, which nearly doubled the repository
        # for pixels nobody sees: .frame img is width:100% inside a ~900 px
        # column, so the browser was discarding more than half of every one.
        # 1024 px costs 27% of the bytes and is still above what is displayed.
        for arr, name in ((natural, "natural"), (false, "false")):
            rgb = tone(arr)
            rgba = np.dstack([rgb, np.where(gap, 0, 255).astype(np.uint8)])
            img = Image.fromarray(rgba, mode="RGBA")
            if max(img.size) > PREVIEW_PX:
                img = img.resize((PREVIEW_PX, PREVIEW_PX), Image.LANCZOS)
            img.save(PREVIEWS / f"{tif.stem}_{name}.png", optimize=True)
        n += 2
    return n


def entries() -> list[dict]:
    """One manifest entry per real scene, read off the GeoTIFF itself."""
    out = []
    for tif in sorted(CONVERTED.glob("liss3_*.tif")):
        sid = tif.stem
        stamp = sid.split("_")[-1]
        with rasterio.open(tif) as src:
            tags = src.tags()
            b = src.bounds
            acquired = _iso(tags["SATQUERY_DATE"])
            season = SEASON.get(stamp, "")
            out.append({
                "id": sid,
                "label": f"Kosi Basin (LISS-III) — {acquired}"
                         + (f", {season}" if season else ""),
                "sensor": "Resourcesat LISS-III (real, Bhoonidhi)",
                "acquired": acquired,
                "place": "Supaul / Madhepura, Bihar",
                # Bhoonidhi reports no cloud figure for these products, so the
                # kernel's own brightness heuristic is the only estimate. 0.0
                # would assert clear sky we cannot vouch for.
                "cloud_hint": 0.0,
                "pair": PAIRS.get(sid),
                "path": f"data/real/converted/{tif.name}",
                "preview_false": f"data/real/previews/{sid}_false.png",
                "preview_natural": f"data/real/previews/{sid}_natural.png",
                "width": src.width,
                "height": src.height,
                "crs": str(src.crs),
                "transform": list(src.transform)[:6],
                "bands": list(src.descriptions),
                "dtype": src.dtypes[0],
                "scale_factor": int(tags.get("SATQUERY_SCALE", 10000)),
                "nodata": src.nodata,
                "pixel_area_m2": abs(src.transform.a * src.transform.e),
                "bounds_utm": [b.left, b.bottom, b.right, b.top],
                "bounds_wgs84": list(
                    transform_bounds(src.crs, "EPSG:4326", *b)),
                "synthetic": False,
                "description": (
                    f"Real Resourcesat LISS-III acquisition, path/row 106/053, "
                    f"{acquired}. Source product "
                    f"{tags.get('SATQUERY_ORIGINAL', 'unknown')}. No SWIR2 "
                    f"band, so burn-severity questions abstain. Unlabelled, so "
                    f"no ground truth to check the kernel against."),
                # Deliberately empty: see the module docstring.
                "ground_truth": {},
            })
    return out


def main() -> int:
    if not CONVERTED.exists() or not any(CONVERTED.glob("liss3_*.tif")):
        print(f"no liss3_*.tif under {CONVERTED}")
        print("nothing to register; run scripts/ingest_liss3.py first")
        return 0

    n_prev = build_previews()
    real = entries()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    # Replace rather than append, so re-running is idempotent.
    kept = [s for s in manifest["scenes"] if not s["id"].startswith("liss3_")]
    manifest["scenes"] = kept + real
    manifest["scene_count"] = len(manifest["scenes"])
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"wrote {n_prev} previews -> {PREVIEWS}")
    print(f"registered {len(real)} real scenes "
          f"({len(kept)} synthetic kept) -> {MANIFEST.name}")
    for s in real:
        lo = s["bounds_wgs84"]
        print(f"  {s['id']:28s} {s['acquired']}  "
              f"{s['width']}x{s['height']} @ {s['pixel_area_m2']:.0f} m2/px  "
              f"lon {lo[0]:.2f}-{lo[2]:.2f} lat {lo[1]:.2f}-{lo[3]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
