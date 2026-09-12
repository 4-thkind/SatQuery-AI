"""Crop each real LISS-III scene to its largest fully-valid square.

    python scripts/crop_real.py            # write cropped/ from converted/
    python scripts/crop_real.py --revert   # point the manifest back at converted/

WHY
    A LISS-III product is a rotated swath stored in a north-up raster, so
    30-36% of every scene is nodata. On screen that is a black wedge across a
    third of the frame: it reads as a broken render rather than as the edge of
    a real acquisition, and it is the first thing anyone looking at the demo
    asks about.

    The fix is a spatial subset, which is what every archive offers as a matter
    of course -- not a cosmetic mask. Each scene is cropped to the largest
    axis-aligned square containing no nodata at all. Measured on these eight:
    1212-1328 px on a side, 29-32 km across, 0% gap.

WHY A SQUARE AND NOT THE BIGGEST RECTANGLE
    The largest valid rectangle is about 1080x2040 -- it keeps ~53% of the
    scene against a square's ~37%, but its aspect ratio is 1:1.89. The UI frame
    is `aspect-ratio: 1` with `object-fit: contain`, so that strip would sit in
    the middle of the frame with 47% of the width as black side bars. Trading a
    black wedge for black bars is not a fix. A square fills the frame exactly.

WHY THIS IS HONEST
    The crop is applied to the GeoTIFF, not to the picture. Every derived value
    reads from the scene's own grid, so all of them follow automatically and
    stay mutually consistent:

        mask overlay   np.zeros((bs.shape[0], bs.shape[1], 4))  in app.py
        scale bar      sqrt(pixel_area_m2) * width / 512        in index.html
        coordinates    bounds_wgs84                             from the manifest
        area           pixel count * pixel_area_m2              in the kernel

    Cropping only the preview would have desynchronised the first three -- a
    measurement overlay drawn in the wrong place is worse than an ugly frame.

    The measured hectares DO change, because the question becomes "how much
    water is in this 29 km tile" rather than "in this 49 km scene". That is a
    different question with a different true answer, not a massaged one. The
    manifest records the crop provenance so the subset is visible rather than
    implied.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import rasterio
from rasterio.windows import Window

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

CONVERTED = ROOT / "data" / "real" / "converted"
CROPPED = ROOT / "data" / "real" / "cropped"


def largest_valid_square(gap: np.ndarray, scale: int = 4):
    """Top-left and side of the biggest all-valid square, or None.

    Searched on a 1/scale decimation for speed, then scaled back. Binary search
    on the side length over an integral image of the nodata mask, so testing a
    candidate window is O(1) rather than O(area).
    """
    g = gap[::scale, ::scale]
    h, w = g.shape
    ii = np.pad(g.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    def bad(t: int, l: int, s: int) -> int:
        return ii[t + s, l + s] - ii[t, l + s] - ii[t + s, l] + ii[t, l]

    lo, hi, best = 1, min(h, w), None
    while lo <= hi:
        side = (lo + hi) // 2
        found = None
        step = max(1, side // 16)
        for t in range(0, h - side + 1, step):
            for l in range(0, w - side + 1, step):
                if bad(t, l, side) == 0:
                    found = (t, l, side)
                    break
            if found:
                break
        if found:
            best, lo = found, side + 1
        else:
            hi = side - 1

    if best is None:
        return None
    t, l, side = (v * scale for v in best)
    return t, l, side


def crop_all() -> list[tuple[str, int, float]]:
    CROPPED.mkdir(parents=True, exist_ok=True)
    out = []
    for tif in sorted(CONVERTED.glob("liss3_*.tif")):
        with rasterio.open(tif) as src:
            raw = src.read()
            gap = (raw == 0).all(axis=0)
            found = largest_valid_square(gap)
            if found is None:
                print(f"  {tif.stem}: no valid square, skipped")
                continue
            top, left, side = found
            win = Window(left, top, side, side)

            profile = src.profile.copy()
            profile.update(width=side, height=side,
                           transform=src.window_transform(win))
            tags = src.tags()
            descs = src.descriptions
            data = src.read(window=win)

        dest = CROPPED / tif.name
        with rasterio.open(dest, "w", **profile) as dst:
            dst.write(data)
            for i, d in enumerate(descs, start=1):
                if d:
                    dst.set_band_description(i, d)
            # Carry the source tags, plus provenance for the crop itself so the
            # subset is recorded rather than silently applied.
            dst.update_tags(**tags)
            dst.update_tags(
                SATQUERY_CROP=f"{side}x{side}+{left}+{top}",
                SATQUERY_CROP_SOURCE=tif.name,
                SATQUERY_CROP_REASON="largest nodata-free square of the swath",
            )

        residual = float((data == 0).all(axis=0).mean())
        out.append((tif.stem, side, residual))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true",
                    help="delete cropped/ so register_real falls back to converted/")
    a = ap.parse_args()

    if a.revert:
        import shutil
        if CROPPED.exists():
            shutil.rmtree(CROPPED)
            print(f"removed {CROPPED}")
        else:
            print("nothing to revert")
        return 0

    if not CONVERTED.exists() or not any(CONVERTED.glob("liss3_*.tif")):
        print(f"no liss3_*.tif under {CONVERTED}")
        return 0

    rows = crop_all()
    if not rows:
        print("nothing cropped")
        return 1

    print(f"cropped {len(rows)} scenes -> {CROPPED}")
    for sid, side, residual in rows:
        print(f"  {sid:28s} {side}x{side} px  "
              f"{side * 24 / 1000:.1f} km  gap {100 * residual:.2f}%")
    worst = max(r[2] for r in rows)
    if worst > 0.0:
        print(f"\n!! residual nodata {100 * worst:.2f}% -- the square search failed")
        return 1
    print("\nall crops are 100% valid pixels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
