"""Build data/demo/manifest.json -- the scene catalogue the backend loads at startup.

Reads geospatial metadata straight off the GeoTIFFs so the manifest can never
drift from the actual files. Re-run after make_scenes.py.
"""

import json
import pathlib

import rasterio
from rasterio.warp import transform_bounds

DEMO = pathlib.Path(__file__).resolve().parent.parent / "data" / "demo"

# Narrative metadata. Everything geometric is read from the file itself.
META = {
    "bihar_pre_flood": dict(
        label="Kosi Basin — Pre-Monsoon", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2024-05-18", place="Supaul, Bihar", cloud_hint=0.0,
        pair="bihar_post_flood"),
    "bihar_post_flood": dict(
        label="Kosi Basin — Post-Monsoon Inundation", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2024-08-27", place="Supaul, Bihar", cloud_hint=0.0,
        pair="bihar_pre_flood"),
    "bihar_post_flood_cloudy": dict(
        label="Kosi Basin — Cloud-Occluded Acquisition", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2024-08-24", place="Supaul, Bihar", cloud_hint=0.32, pair=None),
    "forest_burn": dict(
        label="Forest Burn Scar", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2024-04-11", place="Simulated forest block", cloud_hint=0.0, pair=None),
    "urban_t1": dict(
        label="Urban Extent — Epoch 1", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2019-02-08", place="Simulated peri-urban fringe", cloud_hint=0.0,
        pair="urban_t2"),
    "urban_t2": dict(
        label="Urban Extent — Epoch 2", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2024-02-14", place="Simulated peri-urban fringe", cloud_hint=0.0,
        pair="urban_t1"),
    "barren": dict(
        label="Bare Soil — Negative Control", sensor="Sentinel-2 L2A (synthetic)",
        acquired="2024-03-02", place="Simulated fallow block", cloud_hint=0.0, pair=None),
}


def main():
    truth = json.loads((DEMO / "truth.json").read_text())
    scenes = []
    for tif in sorted(DEMO.glob("*.tif")):
        sid = tif.stem
        with rasterio.open(tif) as src:
            b = src.bounds
            scenes.append({
                "id": sid,
                **META[sid],
                "path": f"data/demo/{tif.name}",
                "preview_false": f"data/demo/previews/{sid}_false.png",
                "preview_natural": f"data/demo/previews/{sid}_natural.png",
                "width": src.width, "height": src.height,
                "crs": str(src.crs),
                "transform": list(src.transform)[:6],
                "bands": list(src.descriptions),
                "dtype": src.dtypes[0],
                "scale_factor": int(src.tags().get("SATQUERY_SCALE", 10000)),
                "nodata": src.nodata,
                "pixel_area_m2": abs(src.transform.a * src.transform.e),
                "bounds_utm": [b.left, b.bottom, b.right, b.top],
                "bounds_wgs84": list(
                    transform_bounds(src.crs, "EPSG:4326", *b)),
                "synthetic": src.tags().get("SATQUERY_SYNTHETIC") == "1",
                "description": src.tags().get("SATQUERY_DESC", ""),
                "ground_truth": truth["scenes"].get(sid, {}),
            })

    out = {"version": 1, "scene_count": len(scenes), "scenes": scenes}
    (DEMO / "manifest.json").write_text(json.dumps(out, indent=2))
    print(f"manifest.json: {len(scenes)} scenes")
    for s in scenes:
        lo = s["bounds_wgs84"]
        print(f"  {s['id']:26s} {s['label']:38s} "
              f"({lo[1]:.4f},{lo[0]:.4f})-({lo[3]:.4f},{lo[2]:.4f})")


if __name__ == "__main__":
    main()
