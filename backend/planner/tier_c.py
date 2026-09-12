"""Tier C: rule-based planner and template narration. Spec sections 12, 16.2.

No model weights, no GPU, no downloads. Tier C is a COMPLETE, honest system, not
a stub: it plans, measures, cites evidence and abstains. Tiers A and B replace
only the planning and the prose -- they call the same kernel through the same
registry, so the numbers are identical across all three tiers.
"""

from __future__ import annotations

from ..core.bandstack import BandStack
from ..schemas import Confidence, FeasibilityVerdict, PlanStep, ToolPlan
from ..kernel.spectral import INDEX_FOR_TARGET

# intent -> (index target, threshold direction, label)
INTENT_RECIPE = {
    "flood_extent":      ("water", "gt", "flood water"),
    "water_extent":      ("water", "gt", "water"),
    "shoreline":         ("water", "gt", "water"),
    "vegetation_health": ("vegetation", "gt", "healthy vegetation"),
    "crop_stress":       ("vegetation", "lt", "stressed vegetation"),
    "builtup_extent":    ("builtup", "gt", "built-up land"),
    "burn_severity":     ("burn", "lt", "burn scar"),
}


def pick_index(bs: BandStack, target: str) -> str | None:
    """First index whose bands this scene actually has."""
    from ..kernel.spectral import INDEX_DEFS
    for name in INDEX_FOR_TARGET.get(target, []):
        roles, _ = INDEX_DEFS[name]
        if bs.has(*roles):
            return name
    return None


def build_plan(intent: str, bs: BandStack, is_change: bool = False,
               bs_b: BandStack | None = None) -> ToolPlan:
    """Deterministic plan for an intent. The Tier A/B VLM emits this same shape."""
    if intent not in INTENT_RECIPE:
        # Scene overview. This used to emit a single compute_index step whose
        # result nothing read, so every describe query returned the same content
        # -free "analysis completed" line. Summarise the indices this scene can
        # actually support instead, so the answer differs per scene.
        steps, n = [], 0
        for target in ("vegetation", "water", "builtup"):
            idx = pick_index(bs, target)
            if not idx:
                continue
            n += 1
            steps.append(PlanStep(id=f"s{n}", tool="compute_index",
                                  params={"index": idx}))
            n += 1
            steps.append(PlanStep(id=f"s{n}", tool="zonal_stats",
                                  params={"raster_handle": f"$s{n-1}",
                                          "label": f"{idx} over whole scene"}))
        return ToolPlan(intent=intent, steps=steps,
                        rationale="Scene overview: summarise every index this "
                                  "scene's bands can support, over the full frame.")

    target, direction, label = INTENT_RECIPE[intent]
    index = pick_index(bs, target)
    if index is None:
        return ToolPlan(intent=intent, steps=[], rationale="No usable index.")

    steps = [
        PlanStep(id="s1", tool="compute_index", params={"index": index}),
        PlanStep(id="s2", tool="threshold_mask",
                 params={"raster_handle": "$s1", "mode": "otsu",
                         "direction": direction, "min_area_px": 50}),
    ]

    if is_change and bs_b is not None:
        # Same recipe on the second epoch, then the difference. Both epochs are
        # measured so the ledger shows where the delta came from.
        steps += [
            PlanStep(id="s3", tool="compute_index",
                     params={"index": index, "scene": "b"}),
            PlanStep(id="s4", tool="threshold_mask",
                     params={"raster_handle": "$s3", "mode": "otsu",
                             "direction": direction, "min_area_px": 50,
                             "scene": "b"}),
            PlanStep(id="s5", tool="mask_difference",
                     params={"handle_a": "$s2", "handle_b": "$s4", "op": "sub"}),
            PlanStep(id="s6", tool="measure_area",
                     params={"mask_handle": "$s5", "label": f"new {label}"}),
            PlanStep(id="s7", tool="measure_area",
                     params={"mask_handle": "$s2", "label": f"{label} (epoch A)"}),
            PlanStep(id="s8", tool="measure_area",
                     params={"mask_handle": "$s4", "label": f"{label} (epoch B)",
                             "scene": "b"}),
            # A change figure inherits threshold uncertainty from BOTH epochs, so
            # it needs bounding at least as much as a single-scene measurement.
            # Without this the confidence product has nothing to penalise and
            # reports a falsely perfect 1.000.
            PlanStep(id="s9", tool="threshold_sensitivity",
                     params={"raster_handle": "$s1", "threshold": "$s2.threshold",
                             "direction": direction}),
        ]
        rationale = (f"Compute {index.upper()} on both epochs, threshold each with "
                     f"Otsu, take A-and-not-B for new {label}, and measure all three.")
    else:
        steps += [
            PlanStep(id="s3", tool="measure_area",
                     params={"mask_handle": "$s2", "label": label}),
            PlanStep(id="s4", tool="threshold_sensitivity",
                     params={"raster_handle": "$s1", "threshold": "$s2.threshold",
                             "direction": direction}),
        ]
        rationale = (f"Compute {index.upper()}, threshold with Otsu ({direction}), "
                     f"measure the {label} area, then sweep the threshold to bound it.")

    return ToolPlan(intent=intent, steps=steps, rationale=rationale)


def compose_confidence(v: FeasibilityVerdict, cloud_frac: float,
                       sensitivity_spread: float | None, scaled: bool,
                       grounding: float = 1.0) -> Confidence:
    """Product of measurable components. Never a vibe, never a model output."""
    comp = {
        "feasibility_prior": round(v.prior, 3),
        "cloud_penalty": round(1.0 - min(cloud_frac, 1.0), 3),
        "threshold_stability": 1.0 if sensitivity_spread is None
                               else round(max(0.0, 1.0 - min(sensitivity_spread, 1.0)), 3),
        "radiometry_penalty": 1.0 if scaled else 0.75,
        "grounding_quality": round(grounding, 3),
    }
    score = 1.0
    for x in comp.values():
        score *= x
    band = "High" if score >= 0.70 else "Medium" if score >= 0.40 else "Low"
    weakest = min(comp, key=comp.get)
    return Confidence(
        score=round(score, 3), band=band, components=comp,
        explanation=(f"Product of five measured components; the limiting factor is "
                     f"{weakest.replace('_', ' ')} at {comp[weakest]}."),
    )


def _fmt(n: float) -> str:
    return f"{n:,.2f}"


def _read_index(index: str, mean: float) -> str:
    """Plain-language reading of an index mean. "" when the index is unknown.

    Every index here has a documented zero crossing: positive means more of
    the thing it detects, negative means less. Saying so turns a number into
    an answer without adding a claim -- deliberately no land-cover label, no
    position, no waterbody type, since the kernel measured none of those and
    validator.validate_claims rejects them.
    """
    sign = "strongly " if abs(mean) >= 0.30 else ""
    fam = {
        "ndvi": ("vegetation response", "vegetation is sparse or absent"),
        "evi": ("vegetation response", "vegetation is sparse or absent"),
        "savi": ("vegetation response", "vegetation is sparse or absent"),
        "ndwi": ("open-water response", "most of the scene is not open water"),
        "mndwi": ("open-water response", "most of the scene is not open water"),
        "ndbi": ("built-up/bare response", "little built-up or bare surface"),
    }.get(index.lower())
    if not fam:
        return ""
    positive, negative = fam
    if mean > 0:
        return f"a {sign}positive {positive} on average"
    if mean < 0:
        return f"on average negative, so {negative}"
    # Exactly zero is neither: saying "negative" here would misreport the
    # measurement over a sign convention's own crossing point.
    return f"on average at the zero crossing for {positive}"


def narrate(intent: str, verdict: FeasibilityVerdict, facts: dict,
            scene_label: str, conf: Confidence | None = None,
            lang: str = "en") -> str:
    """Template narration in the language the question was asked in.

    Every number here comes from `facts`, which comes from the kernel. The
    numeral validator (validator.py) enforces that, and it works unchanged in
    every language because the templates carry no numerals of their own -- only
    placeholders the kernel fills.
    """
    from . import phrases

    t = phrases.get(lang)
    label = phrases.label_for(lang, facts.get("label", "the target class"))

    if verdict.verdict == "ABSTAIN":
        rec = (t["rec"].format(rec=verdict.recommendation)
               if verdict.recommendation else "")
        return f"{t['cannot'].format(scene=scene_label)}\n\n{verdict.reason}{rec}"

    lines = []

    if "delta_ha" in facts:
        # Name the dates rather than "epoch A/B": which epoch is the baseline is
        # not obvious to a reader, and getting it backwards inverts the finding.
        lines.append(t["change"].format(
            delta=_fmt(facts["delta_ha"]), label=label, scene=scene_label,
            b_ha=_fmt(facts["b_ha"]), b_date=facts.get("b_date") or "-",
            a_ha=_fmt(facts["a_ha"]), a_date=facts.get("a_date") or "-"))
    elif "hectares" in facts:
        lines.append(t["area"].format(
            ha=_fmt(facts["hectares"]), label=label, scene=scene_label,
            pct=f"{facts['scene_fraction'] * 100:.1f}"))
    elif "absent" in facts:
        lines.append(t["absent"].format(
            label=label, scene=scene_label, reason=facts["absent"]))
    elif facts.get("summaries"):
        # Per-index means for this scene. Numbers come from zonal_stats, so the
        # numeral guard accepts them and the text differs from scene to scene.
        #
        # A bare list of index means ("NDVI 0.412, NDWI -0.155") is honest but
        # answers nothing: it restates the ledger and leaves the reader to know
        # what an NDVI of 0.412 implies. Each index has a documented physical
        # sign convention, so the mean can be read out in words without
        # asserting anything the kernel did not measure -- no location, no
        # waterbody type, no land-cover class, all of which validate_claims
        # blocks for good reason. Sign and magnitude only.
        lines.append(f"{scene_label} — scene overview from "
                     f"{len(facts['summaries'])} spectral "
                     f"{'index' if len(facts['summaries']) == 1 else 'indices'}:")
        for d in facts["summaries"]:
            reading = _read_index(d["index"], d["mean"])
            lines.append(f"{d['index']} averages {d['mean']:.3f} across the "
                         f"scene (range {d['min']:.3f} to {d['max']:.3f})"
                         + (f" — {reading}." if reading else "."))
        lines.append("Per-pixel statistics for each index are in the evidence "
                     "ledger. Ask for a specific class (water, vegetation, "
                     "built-up) to get a measured area in hectares.")
    else:
        lines.append(f"{scene_label}: analysis completed.")

    if "index" in facts and "threshold" in facts:
        lines.append(t["method"].format(
            index=facts["index"].upper(), thr=f"{facts['threshold']:.4f}",
            px=f"{facts['pixel_area_m2']:.0f}"))
    if "arithmetic" in facts:
        lines.append(t["arith"].format(arith=facts["arithmetic"]))

    if "sens_low_ha" in facts:
        # The sweep width comes from facts, not a literal: the numeral guard
        # rejects any figure in this prose that the kernel did not produce.
        lines.append(t["sens"].format(
            w=facts.get("sens_width", 0.05),
            lo=_fmt(facts["sens_low_ha"]), hi=_fmt(facts["sens_high_ha"])))

    if verdict.verdict == "DEGRADE":
        lines.append(t["caveat"].format(reason=verdict.reason))
    if conf:
        lines.append(t["conf"].format(
            band=conf.band, score=f"{conf.score:.2f}", expl=conf.explanation))

    note = phrases.fallback_note(lang)
    if note:
        lines.append(note)

    return "\n\n".join(lines)


def _demo() -> None:
    """Runnable check: plan shape, confidence maths, narration numerals."""
    import pathlib
    from ..core.feasibility import assess
    from ..core.ingest import Session, load_geotiff
    from ..kernel.executor import execute

    root = pathlib.Path(__file__).resolve().parents[2]
    bs = load_geotiff(root / "data/demo/bihar_post_flood.tif")
    s = Session()

    plan = build_plan("flood_extent", bs)
    assert [p.tool for p in plan.steps] == [
        "compute_index", "threshold_mask", "measure_area", "threshold_sensitivity"]
    assert plan.steps[0].params["index"] == "mndwi"      # SWIR1 present, so MNDWI

    ledger, res = execute(plan, bs, s)
    assert all(e.ok for e in ledger)

    v = assess(bs, "flood_extent")
    c = compose_confidence(v, v.cloud_fraction, 0.02, bs.scaled)
    assert c.band == "High" and 0 < c.score <= 1.0, c
    # Confidence must be the literal product of its components.
    prod = 1.0
    for x in c.components.values():
        prod *= x
    assert abs(prod - c.score) < 1e-9

    # A degraded scene must score lower than a clear one.
    cloudy = load_geotiff(root / "data/demo/bihar_post_flood_cloudy.tif")
    vc = assess(cloudy, "flood_extent")
    cc = compose_confidence(vc, vc.cloud_fraction, 0.02, cloudy.scaled)
    assert cc.score < c.score, (cc.score, c.score)

    text = narrate("flood_extent", v, {
        "label": "flood water", "hectares": res["s3"].value["hectares"],
        "scene_fraction": res["s3"].value["scene_fraction"], "index": "mndwi",
        "threshold": res["s2"].value["threshold"], "pixel_area_m2": bs.pixel_area_m2,
        "arithmetic": res["s3"].provenance["arithmetic"],
    }, "Kosi Basin post-monsoon", c)
    # Assert the shape, not a literal area: the demo scenes are regenerated and
    # the exact hectare figure moves with them. verify_scenes.py owns the numbers.
    assert "MNDWI" in text and "hectares of flood water" in text

    # ABSTAIN narration must carry the reason, not a number.
    vb = assess(bs, "burn_severity")
    ab = narrate("burn_severity", vb, {}, "Kosi Basin")
    assert "cannot answer" in ab and "SWIR2" in ab

    print(f"tier_c: ok  conf={c.score} ({c.band}) vs cloudy {cc.score} ({cc.band})")


if __name__ == "__main__":
    _demo()
