"""Plan executor. Spec sections 10-11.

Runs a ToolPlan step by step, resolving `$sN.field` references between steps, and
emits one EvidenceRecord per step. Every number the user ever sees originates
here and nowhere else.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..core.bandstack import BandStack
from ..schemas import EvidenceRecord, ToolPlan, ToolResult
from .registry import TOOLS

REF = re.compile(r"^\$(?P<step>[A-Za-z0-9_]+)(?:\.(?P<field>[A-Za-z0-9_]+))?$")


class PlanError(RuntimeError):
    pass


def _resolve(value: Any, results: dict[str, ToolResult]) -> Any:
    """Resolve one-level `$s1.field` references against earlier step results.

    `$s1` alone resolves to that step's mask_handle, which is the common case
    (feed the mask from step 1 into step 2).
    """
    if isinstance(value, list):
        return [_resolve(v, results) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, results) for k, v in value.items()}
    if not isinstance(value, str):
        return value

    m = REF.match(value)
    if not m:
        return value

    step, field = m.group("step"), m.group("field")
    if step not in results:
        raise PlanError(f"reference {value!r} points at step {step!r}, which has "
                        f"not run (available: {list(results)})")
    r = results[step]
    if field is None or field == "mask_handle":
        if r.mask_handle is None:
            raise PlanError(f"step {step!r} produced no mask to satisfy {value!r}")
        return r.mask_handle
    if isinstance(r.value, dict) and field in r.value:
        return r.value[field]
    if hasattr(r, field):
        return getattr(r, field)
    raise PlanError(f"step {step!r} has no field {field!r} "
                    f"(value keys: {list(r.value) if isinstance(r.value, dict) else r.value})")


def _upstream(params: dict) -> list[str]:
    """Which step ids does this step reference?"""
    found = []
    def walk(v):
        if isinstance(v, str):
            m = REF.match(v)
            if m:
                found.append(m.group("step"))
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(params)
    return found


def execute(plan: ToolPlan, bs: BandStack, session,
            scenes: dict[str, BandStack] | None = None
            ) -> tuple[list[EvidenceRecord], dict[str, ToolResult]]:
    """Run every step. Returns (ledger, results by step id).

    Stops at the first failed step: a plan whose later steps consume a failed
    result would otherwise measure garbage.
    """
    results: dict[str, ToolResult] = {}
    ledger: list[EvidenceRecord] = []

    for step in plan.steps:
        if step.tool not in TOOLS:
            raise PlanError(f"unknown tool {step.tool!r}; have {sorted(TOOLS)}")

        params = {k: v for k, v in step.params.items() if k != "scene"}
        upstream = _upstream(step.params)
        params = _resolve(params, results)

        # A step may target the second scene of a pair.
        target = bs
        if scenes and "scene" in step.params:
            sid = step.params["scene"]
            if sid not in scenes:
                raise PlanError(f"step {step.id} names scene {sid!r}, "
                                f"which is not loaded ({list(scenes)})")
            target = scenes[sid]

        t0 = time.perf_counter()
        result: ToolResult = TOOLS[step.tool](target, session, **params)
        dt = (time.perf_counter() - t0) * 1000.0

        results[step.id] = result
        ledger.append(EvidenceRecord(
            step_id=step.id, tool=step.tool, params=params, ok=result.ok,
            value=result.value, unit=result.unit,
            arithmetic=result.provenance.get("arithmetic"),
            reproduce=result.provenance.get("reproduce"),
            caveats=result.caveats, provenance=result.provenance,
            upstream=upstream, duration_ms=round(dt, 2),
        ))

        if not result.ok:
            break

    return ledger, results


def _demo() -> None:
    """Runnable check: a 3-step plan must reproduce the fixture ground truth."""
    import json
    import pathlib
    from ..core.ingest import Session, load_geotiff
    from ..schemas import PlanStep

    root = pathlib.Path(__file__).resolve().parents[2]
    truth = json.loads((root / "data/demo/truth.json").read_text())

    s = Session()
    bs = load_geotiff(root / "data/demo/bihar_post_flood.tif")

    plan = ToolPlan(intent="flood_extent", steps=[
        PlanStep(id="s1", tool="compute_index", params={"index": "mndwi"}),
        PlanStep(id="s2", tool="threshold_mask",
                 params={"raster_handle": "$s1", "mode": "otsu", "direction": "gt"}),
        PlanStep(id="s3", tool="measure_area",
                 params={"mask_handle": "$s2", "label": "flood water"}),
    ])
    ledger, results = execute(plan, bs, s)

    assert len(ledger) == 3 and all(e.ok for e in ledger)
    want = truth["scenes"]["bihar_post_flood"]["water_ha"]
    got = results["s3"].value["hectares"]
    assert abs(got - want) / want < 0.02, f"{got} vs {want}"

    # Reference resolution and the upstream chain must be recorded.
    assert ledger[1].upstream == ["s1"] and ledger[2].upstream == ["s2"]
    assert ledger[2].arithmetic and "ha" in ledger[2].arithmetic

    # A scalar field reference, not just a mask handle.
    plan2 = ToolPlan(intent="flood_extent", steps=[
        PlanStep(id="s1", tool="compute_index", params={"index": "mndwi"}),
        PlanStep(id="s2", tool="threshold_mask", params={"raster_handle": "$s1"}),
        PlanStep(id="s3", tool="threshold_sensitivity",
                 params={"raster_handle": "$s1", "threshold": "$s2.threshold"}),
    ])
    l2, r2 = execute(plan2, bs, s)
    assert r2["s3"].ok and l2[2].params["threshold"] == r2["s2"].value["threshold"]

    # Bad references fail loudly rather than silently measuring nothing.
    for bad in ("$s9", "$s1.nonexistent"):
        try:
            execute(ToolPlan(intent="x", steps=[
                PlanStep(id="s1", tool="compute_index", params={"index": "mndwi"}),
                PlanStep(id="s2", tool="measure_area", params={"mask_handle": bad}),
            ]), bs, s)
            raise AssertionError(f"{bad} must raise")
        except PlanError:
            pass

    # A failing step halts the plan instead of feeding garbage downstream.
    l3, _ = execute(ToolPlan(intent="burn", steps=[
        PlanStep(id="s1", tool="compute_index", params={"index": "nbr"}),
        PlanStep(id="s2", tool="threshold_mask", params={"raster_handle": "$s1"}),
    ]), bs, s)
    assert len(l3) == 1 and not l3[0].ok

    print(f"executor: ok  {got} ha over {len(ledger)} steps, "
          f"{sum(e.duration_ms for e in ledger):.0f} ms")


if __name__ == "__main__":
    _demo()
