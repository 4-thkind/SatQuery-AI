"""Measurement. Spec section 10.3.

measure_area is THE function of this repository. Everything else exists so that
the mask reaching it is the right mask. It is deliberately trivial arithmetic --
that is the point. A number anyone can recompute by hand.
"""

from __future__ import annotations

import numpy as np

from ..core.bandstack import BandStack
from ..schemas import ToolResult


def measure_area(bs: BandStack, session, mask_handle: str,
                 label: str = "region") -> ToolResult:
    mask = session.get_array(mask_handle).astype(bool)

    if bs.pixel_area_m2 is None:
        return ToolResult(
            ok=False, mask_handle=mask_handle,
            caveats=["This raster has no georeferencing (no CRS or affine "
                     "transform), so pixel size in metres is unknown and real-world "
                     "area cannot be computed. I can report the fraction of the "
                     "image instead."],
            provenance={"tool": "measure_area", "failed": "no_georeference"})

    n_pixels = int(mask.sum())
    area_m2 = n_pixels * bs.pixel_area_m2
    area_ha = area_m2 / 10_000.0
    area_km2 = area_m2 / 1_000_000.0
    frac = float(mask.mean())

    arithmetic = (f"{n_pixels:,} px x {bs.pixel_area_m2:.4f} m2/px "
                  f"= {area_m2:,.1f} m2 = {area_ha:,.2f} ha")

    return ToolResult(
        ok=True,
        value={"pixels": n_pixels, "hectares": round(area_ha, 2),
               "km2": round(area_km2, 4), "scene_fraction": round(frac, 4)},
        unit="hectares",
        mask_handle=mask_handle,
        caveats=[],
        provenance={
            "tool": "measure_area", "label": label,
            "pixel_count": n_pixels, "pixel_area_m2": bs.pixel_area_m2,
            "arithmetic": arithmetic,
            "crs": bs.crs, "scene_pixels": int(mask.size),
            "reproduce": (f"count True pixels in {mask_handle}, multiply by "
                          f"{bs.pixel_area_m2} m2 (from the affine transform of "
                          f"{bs.scene_id}), divide by 10000 for hectares"),
        },
    )


# Sweep offsets in index units. Deliberately NOT a percentage of the threshold:
# normalised indices are signed, so scaling a negative threshold by +10% moves it
# DOWN and silently reverses the meaning of the sweep. An absolute offset on a
# fixed -1..1 scale is well defined whatever the sign.
SENSITIVITY_OFFSETS = (-0.05, -0.02, 0.0, 0.02, 0.05)


def threshold_sensitivity(bs: BandStack, session, raster_handle: str,
                          threshold: float, direction: str = "gt") -> ToolResult:
    """How much does the answer move if the threshold moves?

    Converts a single number into an honest range. Almost nobody does this.
    """
    arr = session.get_array(raster_handle)
    finite = np.isfinite(arr)
    out = {}
    for delta in SENSITIVITY_OFFSETS:
        thr = threshold + delta
        m = (arr > thr) if direction == "gt" else (arr < thr)
        n = int((m & finite).sum())
        out[f"{delta:+.2f}"] = {
            "threshold": round(float(thr), 4),
            "pixels": n,
            "hectares": round(n * bs.pixel_area_m2 / 10_000.0, 2)
                        if bs.pixel_area_m2 else None,
        }

    spread = [v["hectares"] for v in out.values() if v["hectares"] is not None]
    caveats = []
    if spread:
        lo, hi = min(spread), max(spread)
        base = out["+0.00"]["hectares"] or 1.0
        caveats.append(f"Result varies between {lo:,.2f} and {hi:,.2f} ha as the "
                       f"threshold moves by plus-or-minus 0.05 index units "
                       f"({(hi - lo) / base * 100:.1f}% of the reported value).")

    return ToolResult(
        ok=True, value=out, unit="hectares", mask_handle=None, caveats=caveats,
        provenance={"tool": "threshold_sensitivity", "source": raster_handle,
                    "base_threshold": threshold, "direction": direction,
                    "sweep": "absolute offsets in index units: "
                             + ", ".join(f"{d:+.2f}" for d in SENSITIVITY_OFFSETS),
                    "note": "raw threshold comparison, no morphological cleanup, "
                            "so these values differ slightly from the reported "
                            "area which is speckle-filtered"},
    )


def zonal_stats(bs: BandStack, session, raster_handle: str,
                mask_handle: str | None = None, label: str = "region") -> ToolResult:
    """Summary statistics of an index raster, optionally inside a mask."""
    arr = session.get_array(raster_handle).astype(np.float64)
    sel = np.isfinite(arr)
    if mask_handle:
        sel &= session.get_array(mask_handle).astype(bool)
    vals = arr[sel]
    if vals.size == 0:
        return ToolResult(ok=False, caveats=["no pixels in the requested zone"],
                          provenance={"tool": "zonal_stats", "failed": "empty_zone"})
    return ToolResult(
        ok=True,
        value={"mean": round(float(vals.mean()), 4),
               "median": round(float(np.median(vals)), 4),
               "std": round(float(vals.std()), 4),
               "min": round(float(vals.min()), 4),
               "max": round(float(vals.max()), 4),
               "pixels": int(vals.size)},
        unit="index", mask_handle=mask_handle, caveats=[],
        provenance={"tool": "zonal_stats", "source": raster_handle,
                    "zone": mask_handle or "whole scene", "label": label,
                    "arithmetic": f"mean of {vals.size:,} pixels = "
                                  f"{float(vals.mean()):.4f}"},
    )


def _demo() -> None:
    """Runnable check: the reported hectares must equal the fixture ground truth."""
    import json
    import pathlib
    from ..core.ingest import Session, load_geotiff
    from .segmentation import threshold_mask
    from .spectral import compute_index

    root = pathlib.Path(__file__).resolve().parents[2]
    truth = json.loads((root / "data/demo/truth.json").read_text())

    s = Session()
    bs = load_geotiff(root / "data/demo/bihar_post_flood.tif")
    idx = compute_index(bs, s, "mndwi")
    m = threshold_mask(bs, s, idx.mask_handle, mode="otsu")
    a = measure_area(bs, s, m.mask_handle, label="flood water")

    want = truth["scenes"]["bihar_post_flood"]["water_ha"]
    got = a.value["hectares"]
    assert abs(got - want) / want < 0.02, f"{got} vs {want}"

    # The arithmetic string must actually reproduce the number it claims.
    px, ppa = a.provenance["pixel_count"], a.provenance["pixel_area_m2"]
    assert abs(px * ppa / 10_000.0 - got) < 0.01, a.provenance["arithmetic"]

    # Sensitivity must bracket the reported value, within a morphology margin:
    # the sweep is a raw threshold comparison while the reported area has had
    # speckle removed, so the measured value can sit just outside the raw range.
    sens = threshold_sensitivity(bs, s, idx.mask_handle, m.value["threshold"])
    has = [v["hectares"] for v in sens.value.values()]
    margin = 0.01 * got
    assert min(has) - margin <= got <= max(has) + margin, (min(has), got, max(has))
    assert has == sorted(has, reverse=True), has     # gt: higher threshold, less area

    # No georeference -> honest failure, not a fabricated area.
    bs.pixel_area_m2 = None
    assert not measure_area(bs, s, m.mask_handle).ok

    print(f"measurement: ok  {got} ha (truth {want})")
    print(f"  {a.provenance['arithmetic']}")


if __name__ == "__main__":
    _demo()
