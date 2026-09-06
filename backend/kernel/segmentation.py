"""Thresholding and mask morphology. Spec section 10.3.

Otsu is the default when radiometry is a relative stretch: a literature threshold
applied to uncalibrated pixels is a number with no meaning.
"""

from __future__ import annotations

import numpy as np
from skimage.filters import threshold_otsu
from skimage.morphology import closing, disk, opening, remove_small_objects

from ..core.bandstack import BandStack
from ..schemas import ToolResult

# Minimum between-class / total variance for an Otsu split to be believed.
#
# Otsu maximises this ratio, so it is precisely the quantity Otsu itself optimises.
# Measured across the demo scenes (scripts/verify_scenes.py prints them):
#
#   real two-class scenes   0.835 - 0.998   (water, built-up, burn, even under cloud)
#   barren, no water at all 0.627           <- Otsu splitting a single peak
#
# 0.75 sits in that gap. Note the margin is narrower than intuition suggests:
# smooth spatial texture is autocorrelated, so even a one-class scene produces a
# fairly confident-looking split. Do not raise this above ~0.80 without re-running
# the demo scenes -- the cloudy scene is the tightest real case at 0.835.
# One global constant. Make it per-index only if a real index turns out to need
# a different floor.
OTSU_MIN_SEPARABILITY = 0.75


def _otsu_separability(valid: np.ndarray, thr: float) -> float:
    """Between-class variance as a fraction of total variance at `thr`.

    This is Otsu's own objective, normalised. Near 1 the two groups are cleanly
    separated; near 0 the "split" is an arbitrary cut through a single peak.
    """
    total_var = float(valid.var())
    if total_var <= 0:
        return 0.0
    lo, hi = valid[valid <= thr], valid[valid > thr]
    if lo.size == 0 or hi.size == 0:
        return 0.0
    w0, w1 = lo.size / valid.size, hi.size / valid.size
    return float(w0 * w1 * (lo.mean() - hi.mean()) ** 2 / total_var)


def threshold_mask(bs: BandStack, session, raster_handle: str, mode: str = "otsu",
                   value: float | None = None, direction: str = "gt",
                   min_area_px: int = 50, morphology: bool = True) -> ToolResult:
    """Turn a continuous index raster into a boolean mask.

    mode: otsu | absolute | percentile
    direction: gt | lt
    """
    arr = session.get_array(raster_handle)
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return ToolResult(ok=False, caveats=["no valid pixels to threshold"],
                          provenance={"tool": "threshold_mask", "failed": "no_valid_pixels"})

    caveats: list[str] = []
    if mode == "absolute":
        if value is None:
            return ToolResult(ok=False, caveats=["absolute mode needs a value"],
                              provenance={"tool": "threshold_mask", "failed": "no_value"})
        thr = float(value)
        if not bs.scaled:
            caveats.append("Absolute threshold applied to non-calibrated radiometry; "
                           "treat the value as indicative.")
    elif mode == "otsu":
        thr = float(threshold_otsu(valid))
        sep = _otsu_separability(valid, thr)
        if sep < OTSU_MIN_SEPARABILITY:
            # Otsu always returns a threshold, including on a unimodal histogram
            # where there are no two classes to separate. On a scene with no water
            # at all it splits the noise about the mean and reports half the tile
            # as water -- a plausible wrong number, which is the exact failure this
            # system exists to prevent. Refuse instead.
            return ToolResult(
                ok=False,
                caveats=[
                    f"Otsu found no bimodal split in this raster: between-class "
                    f"variance is only {sep:.3f} of the total (a real two-class "
                    f"scene sits well above {OTSU_MIN_SEPARABILITY}). The histogram "
                    f"is single-peaked, so the target class is most likely absent "
                    f"from this scene. Returning no mask rather than thresholding "
                    f"noise into a plausible wrong area."],
                provenance={"tool": "threshold_mask", "failed": "unimodal_histogram",
                            "otsu_threshold": round(thr, 4),
                            "separability": round(sep, 4),
                            "min_separability": OTSU_MIN_SEPARABILITY})
        caveats.append(f"Threshold {thr:.3f} chosen automatically by Otsu's method "
                       f"from this scene's own histogram, not from a fixed "
                       f"literature value. Between-class separability {sep:.3f}.")
    elif mode == "percentile":
        if value is None:
            return ToolResult(ok=False, caveats=["percentile mode needs a value"],
                              provenance={"tool": "threshold_mask", "failed": "no_value"})
        thr = float(np.percentile(valid, value))
    else:
        return ToolResult(ok=False, caveats=[f"unknown threshold mode {mode!r}"],
                          provenance={"tool": "threshold_mask", "failed": "bad_mode"})

    mask = (arr > thr) if direction == "gt" else (arr < thr)
    mask = np.where(np.isfinite(arr), mask, False).astype(bool)

    raw_px = int(mask.sum())
    morph_desc = "none"
    if morphology:
        mask = opening(mask, disk(2))
        mask = closing(mask, disk(2))
        if min_area_px > 0:
            mask = remove_small_objects(mask, max_size=min_area_px)
        morph_desc = (f"opening(disk2) -> closing(disk2) -> "
                      f"remove_small_objects(smaller_than={min_area_px}px)")
        dropped = raw_px - int(mask.sum())
        if dropped:
            caveats.append(
                f"Morphological cleanup changed the mask by {dropped:+d} px "
                f"({dropped / max(raw_px, 1) * 100:+.2f}%) removing speckle and "
                f"holes smaller than {min_area_px} px.")

    handle = session.store_array(f"mask_{raster_handle.split('#')[0]}", mask)
    return ToolResult(
        ok=True,
        value={"threshold": round(thr, 4), "positive_pixels": int(mask.sum()),
               "pixels_before_morphology": raw_px},
        unit=None,
        mask_handle=handle,
        caveats=caveats,
        provenance={
            "tool": "threshold_mask", "source": raster_handle, "mode": mode,
            "threshold": round(thr, 6), "direction": direction,
            "morphology": morph_desc,
            "reproduce": f"mask = {raster_handle} {'>' if direction == 'gt' else '<'} "
                         f"{thr:.6f}; then {morph_desc}",
        },
    )


def mask_difference(bs: BandStack, session, handle_a: str, handle_b: str,
                    op: str = "sub") -> ToolResult:
    """Pixels in A but not B (op=sub), or in either (union) / both (intersect).

    This is the change-detection primitive: post AND NOT pre = new inundation.
    """
    a = session.get_array(handle_a).astype(bool)
    b = session.get_array(handle_b).astype(bool)
    if a.shape != b.shape:
        return ToolResult(ok=False,
                          caveats=[f"masks differ in shape: {a.shape} vs {b.shape}; "
                                   f"co-register the scenes first"],
                          provenance={"tool": "mask_difference", "failed": "shape_mismatch"})

    ops = {"sub": a & ~b, "union": a | b, "intersect": a & b}
    if op not in ops:
        return ToolResult(ok=False, caveats=[f"unknown op {op!r}"],
                          provenance={"tool": "mask_difference", "failed": "bad_op"})
    out = ops[op]
    handle = session.store_array(f"mask_{op}", out)
    symbol = {"sub": "A AND NOT B", "union": "A OR B", "intersect": "A AND B"}[op]
    return ToolResult(
        ok=True,
        value={"pixels": int(out.sum()), "a_pixels": int(a.sum()),
               "b_pixels": int(b.sum())},
        unit=None, mask_handle=handle, caveats=[],
        provenance={"tool": "mask_difference", "op": op, "a": handle_a, "b": handle_b,
                    "arithmetic": f"{symbol}: {int(a.sum())} px, {int(b.sum())} px "
                                  f"-> {int(out.sum())} px"},
    )


def _demo() -> None:
    """Runnable check: recover the fixture's known water area via Otsu."""
    import json
    import pathlib
    from ..core.ingest import Session, load_geotiff
    from .spectral import compute_index

    root = pathlib.Path(__file__).resolve().parents[2]
    truth = json.loads((root / "data/demo/truth.json").read_text())

    s = Session()
    bs = load_geotiff(root / "data/demo/bihar_post_flood.tif")
    idx = compute_index(bs, s, "mndwi")
    m = threshold_mask(bs, s, idx.mask_handle, mode="otsu", direction="gt")
    assert m.ok
    got = m.value["positive_pixels"]
    want = truth["scenes"]["bihar_post_flood"]["water_px"]
    assert abs(got - want) / want < 0.02, f"{got} vs {want}"

    # Change detection: post minus pre must recover the known delta.
    bs_pre = load_geotiff(root / "data/demo/bihar_pre_flood.tif")
    idx_pre = compute_index(bs_pre, s, "mndwi")
    m_pre = threshold_mask(bs_pre, s, idx_pre.mask_handle, mode="otsu")
    d = mask_difference(bs, s, m.mask_handle, m_pre.mask_handle, op="sub")
    want_d = truth["scenes"]["bihar_post_flood"]["delta_vs_pre_ha"] * 100  # ha -> px
    assert abs(d.value["pixels"] - want_d) / want_d < 0.03, (d.value, want_d)

    assert not threshold_mask(bs, s, idx.mask_handle, mode="bogus").ok
    assert not threshold_mask(bs, s, idx.mask_handle, mode="absolute").ok

    print(f"segmentation: ok  water={got}px (truth {want}) "
          f"delta={d.value['pixels']}px (truth {want_d:.0f})")


if __name__ == "__main__":
    _demo()
