"""Convert Bhoonidhi Resourcesat LISS-III scenes into SatQuery-readable GeoTIFFs.

    python scripts/ingest_liss3.py                 # all scenes in data/real/
    python scripts/ingest_liss3.py --list          # what is there, no conversion
    python scripts/ingest_liss3.py --full          # no crop, whole 185x171 km scene

What Bhoonidhi gives you is a directory per scene holding four separate
single-band GeoTIFFs -- BAND2, BAND3, BAND4, BAND5 -- plus a BAND_META.txt. What
the pipeline wants is one multi-band file whose bands are *named*, because
`load_geotiff` reads roles from the file rather than guessing an ordering.

So this stacks the four into one raster, writes the band descriptions, and copies
the radiometry facts out of BAND_META.txt into tags. After this the scenes load
through exactly the same path as the demo fixtures, with no special cases.

The band mapping is not a guess. BAND_META.txt states `BandNumbers= 2345`, and
LISS-III's documented band plan is:

    BAND2 -> GREEN   0.52-0.59 um
    BAND3 -> RED     0.62-0.68 um
    BAND4 -> NIR     0.77-0.86 um
    BAND5 -> SWIR1   1.55-1.70 um

Note what is absent: no blue, and no SWIR2. That is the real sensor's real
constraint, and it is why a burn-severity query (NBR needs SWIR2) correctly
ABSTAINs on this data rather than returning a number.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import rasterio
from rasterio.windows import Window

REAL = pathlib.Path(__file__).resolve().parent.parent / "data" / "real"

# BAND<n> -> canonical role. From BAND_META.txt's `BandNumbers= 2345`.
BAND_ROLES = {"BAND2": "GREEN", "BAND3": "RED", "BAND4": "NIR", "BAND5": "SWIR1"}
BAND_ORDER = ["BAND2", "BAND3", "BAND4", "BAND5"]

# Supaul / Kosi basin, matching the demo fixtures' footprint so real and
# synthetic scenes are directly comparable.
SUPAUL_LON, SUPAUL_LAT = 86.60, 26.12
CROP_PX = 2048          # 2048 * 24 m = ~49 km across


def read_meta(scene: pathlib.Path) -> dict[str, str]:
    """Parse BAND_META.txt into a dict. `Key= value` per line, spaces everywhere."""
    hits = list(scene.glob("BAND_META.txt")) or list(scene.glob("*.meta"))
    if not hits:
        return {}
    out: dict[str, str] = {}
    for line in hits[0].read_text(errors="replace").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def scene_dirs() -> list[pathlib.Path]:
    """Scene directories: those holding all four expected band files."""
    return sorted(
        d for d in REAL.iterdir()
        if d.is_dir() and all((d / f"{b}.tif").exists() for b in BAND_ORDER)
    )


def crop_window(src, lon: float, lat: float, size: int) -> Window | None:
    """A `size`x`size` window centred on a lon/lat, clipped to the raster.

    Returns None when the point is outside the scene, so the caller can fall
    back to the full extent instead of writing an empty file.
    """
    from rasterio.warp import transform as warp_transform

    xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
    row, col = src.index(xs[0], ys[0])
    half = size // 2
    c0, r0 = col - half, row - half
    # Clip rather than refuse: an AOI near the edge still yields a usable tile.
    c0 = max(0, min(c0, src.width - size))
    r0 = max(0, min(r0, src.height - size))
    if not (0 <= row < src.height and 0 <= col < src.width):
        return None
    if src.width < size or src.height < size:
        return None
    return Window(c0, r0, size, size)


def convert(scene: pathlib.Path, out_dir: pathlib.Path, full: bool = False) -> dict:
    """Stack one scene's four bands into a single named-band GeoTIFF."""
    meta = read_meta(scene)
    date = meta.get("DateOfPass", "unknown").replace("-", "").lower()
    path_row = f"{meta.get('Path', 'p')}_{meta.get('Row', 'r')}"
    stem = f"liss3_{path_row}_{date}"
    out = out_dir / f"{stem}.tif"

    with rasterio.open(scene / "BAND2.tif") as ref:
        profile = ref.profile.copy()
        win = None if full else crop_window(ref, SUPAUL_LON, SUPAUL_LAT, CROP_PX)
        transform = ref.transform if win is None else ref.window_transform(win)
        height = ref.height if win is None else int(win.height)
        width = ref.width if win is None else int(win.width)

    stack = np.zeros((4, height, width), dtype=np.uint16)
    for i, band in enumerate(BAND_ORDER):
        with rasterio.open(scene / f"{band}.tif") as src:
            stack[i] = src.read(1, window=win) if win is not None else src.read(1)

    # ScaleFactor=0.0001 with ValidRange=0-10000 is the same convention the demo
    # fixtures use, so `bs.scaled` comes out True and absolute thresholds are
    # defensible rather than merely indicative.
    scale = 1.0 / float(meta.get("ScaleFactor", "0.0001") or 0.0001)

    profile.update(
        driver="GTiff", height=height, width=width, count=4, dtype="uint16",
        transform=transform, nodata=0, compress="deflate", predictor=2, tiled=True,
        blockxsize=512, blockysize=512,
    )

    with rasterio.open(out, "w", **profile) as dst:
        dst.write(stack)
        for i, band in enumerate(BAND_ORDER, start=1):
            dst.set_band_description(i, BAND_ROLES[band].lower())
        dst.update_tags(
            SATQUERY_BANDS=",".join(BAND_ROLES[b] for b in BAND_ORDER),
            SATQUERY_SCALE=f"{scale:.0f}",
            SATQUERY_SYNTHETIC="0",          # real imagery -- no SYN badge
            SATQUERY_SOURCE="Bhoonidhi / NRSC / ISRO",
            SATQUERY_SENSOR="Resourcesat-2A LISS-III",
            SATQUERY_PROCESSING=meta.get("ProcessingLevel", ""),
            SATQUERY_DATE=meta.get("DateOfPass", ""),
            SATQUERY_PATH_ROW=path_row,
            SATQUERY_ORIGINAL=scene.name,
            SATQUERY_RESOLUTION_M=meta.get("OutputResolutionAlong", "24"),
            SATQUERY_SUN_ELEVATION=meta.get("SunElevationAtCenter", ""),
            SATQUERY_CLOUD_REPORTED=meta.get("CloudPercent", "-NA-"),
        )

    valid = stack[stack > 0]
    return {
        "scene": scene.name,
        "out": out.name,
        "date": meta.get("DateOfPass", "?"),
        "path_row": path_row,
        "size": f"{width}x{height}",
        "cropped": win is not None,
        "mb": out.stat().st_size / 1e6,
        "reflectance_mean": float(valid.mean() / scale) if valid.size else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show scenes, convert nothing")
    ap.add_argument("--full", action="store_true", help="keep the full scene extent")
    ap.add_argument("--out", default=None, help="output directory")
    args = ap.parse_args()

    scenes = scene_dirs()
    if not scenes:
        print(f"no LISS-III scene directories under {REAL}")
        print("expected: one directory per scene containing BAND2/3/4/5.tif")
        return 1

    if args.list:
        print(f"{len(scenes)} scene(s) in {REAL}\n")
        rows = []
        for s in scenes:
            m = read_meta(s)
            rows.append((
                m.get("DateOfPass", "?"),
                f"{m.get('Path', '?')}/{m.get('Row', '?')}",
                m.get("SatID", "?").strip(),
                m.get("ProcessingLevel", "?"),
                s.name,
            ))
        for date, pr, sat, lvl, name in sorted(rows):
            print(f"  {date:12s} path/row {pr:10s} {sat:9s} {lvl:34s} {name}")
        return 0

    out_dir = pathlib.Path(args.out) if args.out else REAL / "converted"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"converting {len(scenes)} scene(s) -> {out_dir}")
    if not args.full:
        print(f"cropping {CROP_PX}x{CROP_PX} px (~{CROP_PX * 24 / 1000:.0f} km) "
              f"around Supaul {SUPAUL_LAT}N {SUPAUL_LON}E\n")

    results = []
    for s in scenes:
        try:
            r = convert(s, out_dir, full=args.full)
            results.append(r)
            crop = "crop" if r["cropped"] else "FULL"
            print(f"  {r['date']:12s} {r['size']:>11s} {crop:4s} "
                  f"{r['mb']:6.1f} MB  mean_refl={r['reflectance_mean']:.4f}  "
                  f"-> {r['out']}")
        except Exception as e:
            print(f"  FAILED {s.name}: {type(e).__name__}: {e}")

    if not results:
        return 1

    print(f"\n{len(results)} converted. Bands named "
          f"{', '.join(BAND_ROLES[b].lower() for b in BAND_ORDER)}; "
          f"tagged SATQUERY_SYNTHETIC=0.")

    prs = {r["path_row"] for r in results}
    if len(prs) == 1 and len(results) >= 2:
        dates = sorted(r["date"] for r in results)
        print(f"All on path/row {prs.pop()} — already co-registered, so any two "
              f"form a bi-temporal pair.")
        print(f"Widest interval: {dates[0]} .. {dates[-1]}")

    print("\nNext: python scripts/verify_real.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
