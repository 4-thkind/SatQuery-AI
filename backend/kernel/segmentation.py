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
# Measured separability, by data source (scripts/verify_scenes.py and
# scripts/verify_real.py both print these):
#
#   synthetic demo scenes    0.835 - 0.998   piecewise-smooth, clean class edges
#   synthetic barren         0.632           <- Otsu splitting a single peak
#   REAL LISS-III scenes     0.482 - 0.786   <- genuine water, and it overlaps
#
# That third row is the lesson from running on real Resourcesat imagery. Real
# scenes are mixed pixels, haze gradients and continuous land-cover transitions,
# so the between-class variance is far lower than a synthetic scene's even when
# the target is unmistakably present. Barren's 0.632 sits INSIDE the real range,
# which means no single value of this ratio can separate "target absent" from
# "target present in real data". Raising the floor rejects real imagery; lowering
# it re-admits the barren false positive.
#
# So the floor stays only as a weak sanity check on degenerate splits, and the
# real work of catching an absent class moved to _physical_support() below --
# which asks a question about reflectance physics rather than about histogram
# shape. See the comment there.
OTSU_MIN_SEPARABILITY = 0.35

# Fraction of valid pixels that must sit on the physically meaningful side of an
# index's natural zero crossing for the target class to be considered present.
#
# Measured MNDWI > 0 fraction:
#
#   synthetic barren (0 ha water, ground truth)   0.00%   <- nothing there
#   real LISS-III, eight dates                    3.7% - 76.5%
#   synthetic flood scenes                        2.3% - 25.5%
#
# 1% sits below every scene that genuinely contains the class and above the
# negative control, which registers exactly zero. The gap is three orders of
# magnitude, not a tuned margin -- that is what makes this a better guard than
# the variance ratio.
MIN_PHYSICAL_SUPPORT = 0.01

# Index -> (physical zero crossing, which side means "target present").
#
# These are not fitted values. Normalised difference indices are constructed so
# that the sign carries the meaning: NDWI and MNDWI exceed zero over open water
# because water reflects green far more than NIR/SWIR (McFeeters 1996, Xu 2006);
# NDVI exceeds zero wherever chlorophyll reflects NIR above red. An index whose
# sign has no such interpretation is simply absent from this table and skips the
# check rather than being given an invented threshold.
PHYSICAL_ZERO = {
    "ndwi": (0.0, "gt"),
    "mndwi": (0.0, "gt"),
    "ndvi": (0.0, "gt"),
}


def _otsu_separability(valid: np.ndarray, thr: float) -> float:
    """Between-class variance as a fraction of total variance at `thr`.

    This is Otsu's own objective, normalised. Near 1 the two groups are cleanly
    separated; near 0 the "split" is an arbitrary cut through a single peak.

    Useful for reporting, and for catching a fully degenerate split. Not
    sufficient on its own to decide whether a class is present -- real imagery
    scores much lower than synthetic imagery at identical correctness.
    """
    total_var = float(valid.var())
    if total_var <= 0:
        return 0.0
    lo, hi = valid[valid <= thr], valid[valid > thr]
    if lo.size == 0 or hi.size == 0:
        return 0.0
    w0, w1 = lo.size / valid.size, hi.size / valid.size
    return float(w0 * w1 * (lo.mean() - hi.mean()) ** 2 / total_var)


def _physical_support(valid: np.ndarray, index_name: str | None) -> float | None:
    """Fraction of pixels on the physically meaningful side of the index's zero.

    Returns None when the index has no meaningful zero crossing, in which case
    the caller skips this check rather than inventing a threshold.

    Why this exists: Otsu will always return a threshold, even on a histogram
    with one peak, and on a scene containing no water it puts that threshold deep
    in negative MNDWI and reports half the tile as water. The variance ratio does
    not reliably catch it -- real imagery is noisy enough to look similar. But
    the physics does: MNDWI is negative everywhere on land, so a scene with no
    water has essentially no pixels above zero, while a scene with water has
    percent-scale support regardless of how messy the histogram is.
    """
    if not index_name:
        return None
    entry = PHYSICAL_ZERO.get(index_name.lower())
    if entry is None:
        return None
    zero, side = entry
    return float((valid > zero).mean() if side == "gt" else (valid < zero).mean())


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

        # Guard 1, physics. The index name travels in the handle, which is
        # shaped "mndwi_raster#1" -- so the leading segment names the index and
        # is what tells this check which zero crossing applies.
        index_name = raster_handle.split("#")[0].split("_")[0]
        support = _physical_support(valid, index_name)
        if support is not None and support < MIN_PHYSICAL_SUPPORT:
            # Otsu always returns a threshold, including on a histogram with a
            # single peak where there are no two classes to separate. On a scene
            # with no water at all it splits the noise about the mean and reports
            # half the tile as water -- a plausible wrong number, which is the
            # exact failure this system exists to prevent.
            #
            # The physical zero catches it where histogram shape does not: MNDWI
            # is negative over land everywhere, so a scene without water has
            # essentially no pixels above zero no matter how the histogram looks.
            zero, side = PHYSICAL_ZERO[index_name.lower()]
            return ToolResult(
                ok=False,
                caveats=[
                    f"Only {support:.3%} of pixels have {index_name.upper()} "
                    f"{'>' if side == 'gt' else '<'} {zero:g}, below the "
                    f"{MIN_PHYSICAL_SUPPORT:.0%} needed for the target class to be "
                    f"considered present. Otsu would still return a threshold "
                    f"({thr:.3f}) and that threshold would split noise, so this "
                    f"returns no mask rather than a plausible wrong area."],
                provenance={"tool": "threshold_mask", "failed": "no_physical_support",
                            "index": index_name, "otsu_threshold": round(thr, 4),
                            "physical_support": round(support, 6),
                            "min_physical_support": MIN_PHYSICAL_SUPPORT,
                            "separability": round(sep, 4)})

        # Guard 2, degeneracy. A weak backstop for indices with no meaningful
        # zero crossing. Deliberately low: real imagery separates far less
        # cleanly than synthetic imagery at identical correctness, so a high
        # floor here rejects genuine scenes. See the constant's comment.
        if sep < OTSU_MIN_SEPARABILITY:
            return ToolResult(
                ok=False,
                caveats=[
                    f"Otsu found no usable split in this raster: between-class "
                    f"variance is only {sep:.3f} of the total. The histogram is "
                    f"effectively single-peaked, so the target class is most "
                    f"likely absent from this scene. Returning no mask rather "
                    f"than thresholding noise into a plausible wrong area."],
                provenance={"tool": "threshold_mask", "failed": "degenerate_split",
                            "otsu_threshold": round(thr, 4),
                            "separability": round(sep, 4),
                            "min_separability": OTSU_MIN_SEPARABILITY})

        if support is not None:
            caveats.append(f"{support:.1%} of pixels sit on the water/vegetation "
                           f"side of {index_name.upper()}=0, supporting the "
                           f"presence of the target class.")
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
