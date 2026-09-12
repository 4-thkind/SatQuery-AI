"""The one function that answers a question. Layers L0-L5 in order.

    ingest -> feasibility gate -> plan -> execute -> compose -> validate

Every number in the returned AnswerPayload came out of the kernel. The narration
is checked against those numbers before it is allowed to leave this function.
"""

from __future__ import annotations

import json
import pathlib
import time

from .core.bandstack import BandStack
from .core.feasibility import assess
from .core.ingest import Session, load_geotiff
from .kernel.executor import execute
from .planner.intent import classify
from .planner.language import detect as detect_language, label as language_label
from .planner.places import coverage_message, detect as detect_place, is_covered
from .rag.retriever import get as get_retriever
from .planner import tier_b
from .planner.tier_c import build_plan, compose_confidence, narrate
from .planner.validator import (validate_against_sources,
                                validate_narration)
from .schemas import AnswerPayload, Confidence, SceneRef

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "data" / "demo"

# threshold_mask refusal codes that mean "the target class is not in this scene"
# rather than "something went wrong". Both deserve a real explanation in the
# narration, not a bare "analysis completed". Kept as a set so a new guard in
# segmentation.py only has to add its code here.
ABSENT_CLASS_REASONS = frozenset({"no_physical_support", "degenerate_split",
                                  "unimodal_histogram"})

_manifest_cache: dict | None = None
_scene_cache: dict[str, BandStack] = {}
_uploaded_scenes: dict[str, dict] = {}


def get_uploaded_scenes() -> dict[str, dict]:
    global _uploaded_scenes
    from .core.uploader import load_uploaded_manifest
    disk_manifest = load_uploaded_manifest()
    _uploaded_scenes = dict(disk_manifest)
    return _uploaded_scenes


def register_uploaded_scene(entry: dict) -> None:
    global _uploaded_scenes
    _uploaded_scenes[entry["id"]] = entry


def unregister_uploaded_scene(scene_id: str) -> None:
    global _uploaded_scenes, _scene_cache
    _uploaded_scenes.pop(scene_id, None)
    _scene_cache.pop(scene_id, None)


def manifest() -> dict:
    global _manifest_cache
    if _manifest_cache is None:
        _manifest_cache = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
    return _manifest_cache


def scene_refs() -> list[SceneRef]:
    bundled = [SceneRef(**{k: v for k, v in s.items() if k in SceneRef.model_fields})
               for s in manifest()["scenes"]]
    uploaded = [SceneRef(**{k: v for k, v in s.items() if k in SceneRef.model_fields})
                for s in get_uploaded_scenes().values()]
    return uploaded + bundled


def scene_entry(scene_id: str) -> dict:
    up = get_uploaded_scenes()
    if scene_id in up:
        return up[scene_id]
    for s in manifest()["scenes"]:
        if s["id"] == scene_id:
            return s
    raise KeyError(f"unknown scene {scene_id!r}")


def load_scene(scene_id: str) -> BandStack:
    """Cached. Fixtures are 16 MB each; reloading per query is pure waste."""
    if scene_id not in _scene_cache:
        _scene_cache[scene_id] = load_geotiff(ROOT / scene_entry(scene_id)["path"])
    return _scene_cache[scene_id]


def rainfall_context(scene_id: str) -> dict | None:
    """Independent corroboration: does the weather agree with the pixels?

    Bundled CSV, no network. Only meaningful for the Kosi scenes.
    """
    path = DEMO / "rainfall_supaul.csv"
    entry = scene_entry(scene_id)
    if not path.exists() or "Supaul" not in entry.get("place", ""):
        return None

    import csv
    with path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)]
    acq = entry["acquired"]
    window = [r for r in rows if r["date"] <= acq][-5:]
    if not window:
        return None

    total = sum(float(r["rainfall_mm"]) for r in window)
    normal = sum(float(r["normal_mm"]) for r in window)
    peak = max(window, key=lambda r: float(r["rainfall_mm"]))
    return {
        "district": window[0]["district"], "state": window[0]["state"],
        "window_days": len(window), "window_end": acq,
        "total_mm": round(total, 1), "normal_mm": round(normal, 1),
        "departure_pct": round((total - normal) / normal * 100, 1) if normal else None,
        "peak_24h_mm": float(peak["rainfall_mm"]), "peak_date": peak["date"],
        "source": window[0]["source"],
        "daily": [{"date": r["date"], "mm": float(r["rainfall_mm"])} for r in window],
    }


def answer(query: str, scene_id: str, scene_id_b: str | None = None,
           tier: str = "C") -> AnswerPayload:
    t0 = time.perf_counter()
    session = Session()

    bs = load_scene(scene_id)
    entry = scene_entry(scene_id)
    bs_b = load_scene(scene_id_b) if scene_id_b else None

    intent, is_change, _ = classify(query)
    # Answer in the language the question was asked in. Detected once here and
    # threaded through every return path below, including the refusals -- a
    # refusal a person cannot read is not a refusal, it is a dead end.
    lang = detect_language(query)
    if is_change and bs_b is None and entry.get("pair"):
        # The question is comparative and the manifest knows the partner scene.
        scene_id_b = entry["pair"]
        bs_b = load_scene(scene_id_b)

    verdict = assess(bs, intent, has_second_scene=bs_b is not None)
    scene_label = entry["label"]

    base = dict(query=query, intent=intent, verdict=verdict.verdict,
                scene_ids=[scene_id] + ([scene_id_b] if scene_id_b else []),
                feasibility=verdict, tier=tier,
                language=lang, language_label=language_label(lang))

    # Dynamic RAG check for conceptual/methodology questions falling through to scene_describe
    if intent == "scene_describe":
        norm_q = query.lower()
        is_explicit_describe = any(w in norm_q for w in ["describe", "overview", "summary", "kya hai", "in this scene", "this scene", "batao", "scene"])
        if not is_explicit_describe:
            candidate_cites = get_retriever().cite(query, k=1)
            if candidate_cites and candidate_cites[0]["score"] >= 0.38:
                intent = "method_explain"
                base["intent"] = "method_explain"

    if intent == "method_explain":
        # k=2 to match what the Tier B prompt actually consumes.
        # Retrieving a third chunk only to drop it costs latency in the
        # dense search and adds a chunk the verbatim fallback would
        # otherwise paste into the answer.
        citations = get_retriever().cite(query, k=2)
        if citations:
            top = citations[0]
            title = top.get("title", "Methodology Reference")
            source = top.get("source", "")
            text = top.get("text") or top.get("excerpt", "")

            # Tier B composes an answer from the retrieved chunks. Any
            # Tier B failure falls back to presenting the chunk itself,
            # which is honest but reads as a document dump rather than an
            # answer.
            narration = ""
            if tier.upper() in ("A", "B"):
                narration = tier_b.answer_from_corpus(query, citations,
                                                      lang=lang)
            composed = bool(narration)

            def _verbatim() -> str:
                out = f"{title}\n\n{text}"
                if source:
                    out += f"\n\nSource: {source}"
                return out

            if composed:
                # A model wrote this, so the numeral guard applies.
                # Retrieved documents are NOT kernel facts: a number that
                # lives only in a corpus chunk must never reach the user as
                # if it had been measured. The fact set is empty because
                # nothing was measured on this path -- it answers "how does
                # this work", not "how much is there".
                # Numerals only. The claim guard is deliberately skipped:
                # this text explains a method rather than describing this
                # scene, so words like "river" or "coast" are subject matter,
                # not fabricated observation. Numbers are still fenced --
                # a figure from a paper must not read as a measurement.
                _nums, _bad = validate_against_sources(narration, citations)
                if not _nums:
                    narration, composed = _verbatim(), False
            else:
                narration = _verbatim()

            # Confidence from the retrieval score rather than a constant.
            # A flat 1.0 on any corpus hit is exactly the "vibe" that
            # compose_confidence's own docstring forbids.
            _rel = round(max(0.0, min(float(top.get("score", 0.0)), 1.0)), 3)
            conf = Confidence(
                score=_rel,
                band=("High" if _rel >= 0.70 else
                      "Medium" if _rel >= 0.40 else "Low"),
                components={
                    "retrieval_relevance": _rel,
                    "composed_by_model": 1.0 if composed else 0.0,
                },
                explanation=(
                    f"Cosine similarity {_rel} against the local corpus; "
                    + ("prose composed by the fine-tuned model and checked "
                       "by the numeral guard" if composed
                       else "chunk presented verbatim")
                    + (f". Source: {source}." if source else ".")
                ),
            )
            verdict.verdict = "ANSWER"
            return AnswerPayload(
                **{**base, "verdict": "ANSWER"},
                narration=narration,
                headline=None,
                confidence=conf,
                evidence=[],
                layers={},
                plan=None,
                corroboration=None,
                citations=citations,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
        else:
            verdict.verdict = "ABSTAIN"
            narration = (
                "This query is outside the remote sensing and spectral analysis knowledge base. "
                "The local corpus covers satellite sensors (Sentinel-2, LISS-III, RISAT-1), "
                "spectral indices (NDVI, NDWI, MNDWI, NDBI, NBR), and segmentation algorithms "
                "(Otsu thresholding)."
            )
            return AnswerPayload(
                **{**base, "verdict": "ABSTAIN"},
                narration=narration,
                headline=None,
                confidence=Confidence(
                    score=0.0,
                    band="Low",
                    components={"corpus_coverage": 0.0},
                    explanation="No relevant literature found in the local knowledge base.",
                ),
                evidence=[],
                layers={},
                plan=None,
                corroboration=None,
                citations=[],
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )

    # --- coverage gate: does the question name a place we hold? ------------
    # Runs before the feasibility gate and before any measurement. A question
    # about Assam answered from the Bihar scene is a correct number attached to
    # the wrong place, which is worse than no answer at all.
    place = detect_place(query)
    if not is_covered(place):
        covered = sorted({e.get("place", "") for e in manifest()["scenes"]
                          if e.get("place") and "Simulated" not in e["place"]})
        verdict.verdict = "ABSTAIN"
        verdict.reason = coverage_message(place, covered)
        verdict.recommendation = None
        return AnswerPayload(
            **{**base, "verdict": "ABSTAIN"},
            narration=narrate(intent, verdict, {}, scene_label, lang=lang),
            duration_ms=round((time.perf_counter() - t0) * 1000, 2))

    if verdict.verdict == "ABSTAIN":
        return AnswerPayload(
            **base, narration=narrate(intent, verdict, {}, scene_label, lang=lang),
            duration_ms=round((time.perf_counter() - t0) * 1000, 2))

    plan = build_plan(intent, bs, is_change=is_change and bs_b is not None, bs_b=bs_b)
    if not plan.steps:
        verdict.verdict = "ABSTAIN"
        verdict.reason = (f"No spectral index available for {intent} from bands "
                          f"{sorted(bs.roles)}.")
        return AnswerPayload(**{**base, "verdict": "ABSTAIN"},
                             narration=narrate(intent, verdict, {}, scene_label, lang=lang),
                             duration_ms=round((time.perf_counter() - t0) * 1000, 2))

    scenes = {"a": bs, "b": bs_b} if bs_b is not None else None
    ledger, results = execute(plan, bs, session, scenes=scenes)

    # --- assemble facts from kernel output only --------------------------
    facts: dict = {"pixel_area_m2": bs.pixel_area_m2}
    layers: dict[str, str] = {}
    headline = None
    _, direction, label = _recipe(intent)
    facts["label"] = label

    if "s1" in results and results["s1"].ok:
        facts["index"] = plan.steps[0].params["index"]
        layers["index"] = results["s1"].mask_handle

    # Locate the threshold step by tool name, not by step id. The overview plan
    # puts zonal_stats at s2, and assuming s2 is always a threshold_mask made
    # this KeyError on any describe query.
    thr_id = next((st.id for st in plan.steps if st.tool == "threshold_mask"), None)
    thr = results.get(thr_id) if thr_id else None
    if thr and thr.ok:
        facts["threshold"] = thr.value["threshold"]
        layers["mask"] = thr.mask_handle
    elif thr is not None and thr.provenance.get("failed") in ABSENT_CLASS_REASONS:
        # The kernel refused to threshold because the target class is not there:
        # either no pixels sit on the physically meaningful side of the index's
        # zero crossing, or the histogram is degenerate. Both are an answer --
        # "this class is not present here" -- not a crash, so carry the reason
        # into the narration instead of falling through to a bare "analysis
        # completed" with no number and no explanation.
        facts["absent"] = thr.caveats[0]

    # Every measure_area step in plan order. Step ids are NOT positions: the
    # change plan, the simple plan and the overview plan all number their steps
    # differently, and reading a fixed id was producing KeyErrors the moment a
    # new plan shape appeared. Order within the plan is the contract.
    areas = [results[st.id] for st in plan.steps
             if st.tool == "measure_area" and results.get(st.id)
             and results[st.id].ok]

    if len(areas) >= 3:                                  # change-detection plan
        delta, a_area, b_area = areas[0], areas[1], areas[2]
        facts["delta_ha"] = delta.value["hectares"]
        facts["a_ha"] = a_area.value["hectares"]
        facts["b_ha"] = b_area.value["hectares"]
        facts["arithmetic"] = delta.provenance["arithmetic"]
        facts["a_date"] = entry["acquired"]
        facts["b_date"] = scene_entry(scene_id_b)["acquired"] if scene_id_b else None
        layers["change"] = delta.mask_handle
        headline = {"value": facts["delta_ha"], "unit": "hectares",
                    "label": f"New {label}"}
    elif areas:
        m = areas[0]
        facts.update(hectares=m.value["hectares"],
                     scene_fraction=m.value["scene_fraction"],
                     arithmetic=m.provenance["arithmetic"])
        headline = {"value": facts["hectares"], "unit": "hectares", "label": label}

    # Scene overview: collect every zonal summary the plan produced, so a
    # describe query returns this scene's actual index statistics rather than a
    # generic completion line.
    summaries = []
    for st in plan.steps:
        if st.tool != "zonal_stats":
            continue
        r = results.get(st.id)
        if r and r.ok:
            idx = st.params.get("label", "").split()[0].upper()
            # Round here, not at print time. The narration must contain exactly
            # the figure recorded as a fact, or the numeral guard rejects the
            # sentence for quoting a number the kernel did not produce -- which
            # is precisely what it is for.
            summaries.append({"index": idx,
                              "mean": round(r.value["mean"], 3),
                              "min": round(r.value["min"], 3),
                              "max": round(r.value["max"], 3)})
    if summaries:
        facts["summaries"] = summaries

    spread = None
    sens_id = next((st.id for st in plan.steps
                    if st.tool == "threshold_sensitivity"), None)
    if sens_id and results.get(sens_id) and results[sens_id].ok:
        has = [v["hectares"] for v in results[sens_id].value.values()
               if isinstance(v, dict) and v.get("hectares") is not None]
        if has:
            from .kernel.measurement import SENSITIVITY_OFFSETS
            facts["sens_low_ha"], facts["sens_high_ha"] = min(has), max(has)
            facts["sens_width"] = max(SENSITIVITY_OFFSETS)
            base_ha = facts.get("hectares") or facts.get("delta_ha") or 1.0
            spread = (max(has) - min(has)) / base_ha

    conf = compose_confidence(verdict, verdict.cloud_fraction, spread, bs.scaled)

    # Tier B lets the fine-tuned model phrase the measurement. The facts
    # are the kernel's either way -- only the wording differs -- and the
    # numeral guard below runs on both paths, so a model that invents a
    # figure loses its narration instead of shipping it.
    narration = ""
    if tier.upper() in ("A", "B"):
        narration = tier_b.narrate_measurement(intent, facts, scene_label,
                                               lang=lang)
        # Reject a reply that is technically non-empty but says nothing. The
        # model returns the class label rather than a sentence more often than
        # not on this path -- measured: "Flood_extent", then "Water bodies",
        # then "Flood water" across three prompt revisions. Testing only for
        # emptiness let those through, so the user saw a two-word label where
        # a sentence belonged and Tier C never got a chance.
        #
        # A usable narration restates the measurement, so it has to carry at
        # least one of the kernel's own numbers. That is a property of the
        # output, not a guess about phrasing, which is why it is checked here
        # rather than patched into the prompt a fourth time.
        _unit_words = ("hectare", "hectares", "ha", "%", "percent",
                       "square", "m2", "km")
        if narration and not any(c.isdigit() for c in narration):
            narration = ""
        elif len(narration.split()) < 5:
            narration = ""
        elif not any(u in narration.lower() for u in _unit_words):
            # A measured quantity without its unit is not a measurement.
            # Probe output "The water in the image was measured at 2603.12."
            # cleared both checks above: it is long enough and it carries the
            # right number, but dropping "hectares" turns an area into a bare
            # figure the reader has to guess at. Templates always carry units,
            # so falling back loses nothing.
            narration = ""
    if not narration:
        narration = narrate(intent, verdict, facts, scene_label, conf,
                            lang=lang)

    # --- the guard: no numeral may appear that the kernel did not compute ---
    # scene_label goes in the allowed set. Every template interpolates the
    # scene name into the prose, so a name containing digits puts numerals in
    # the narration that the kernel never computed -- and the guard withheld
    # the whole sentence. It fired on all eight real scenes, whose labels
    # carry an acquisition date ("Kosi Basin (LISS-III) - 2022-08-18"),
    # rejecting ['08', '18,']. Uploaded scenes hit the same wall, since their
    # label is derived from the filename.
    #
    # A scene's own name is not a measurement claim, so it belongs in `extra`
    # alongside the ledger values rather than being stripped from labels.
    #
    # conf.components for the same reason. The confidence line names its
    # weakest component and its value ("threshold stability at 0.453"), and
    # only conf.score was allowed -- so a component value appearing in prose
    # read as fabricated. Latent since Tier C: on synthetic scenes
    # threshold_stability came out 1.0, and "1" is in ALWAYS_OK. Real imagery
    # produces genuine intermediate values and the guard started firing.
    #
    # `spread` for the same reason, pre-emptively: it feeds
    # compose_confidence and does not currently reach the prose, but it is a
    # kernel-derived ratio of exactly the shape that caused the two failures
    # above, so a future sensitivity phrase quoting it would withhold the
    # whole narration.
    ok, bad = validate_narration(narration, facts, extra=[
        e.value for e in ledger] + [conf.score, conf.components, spread,
                                    verdict.cloud_fraction, scene_label])
    if not ok:
        narration = (f"[Narration withheld: it contained {bad}, which the kernel "
                     f"did not compute. Showing measured values only.]\n\n"
                     + (f"{facts.get('hectares', facts.get('delta_ha'))} hectares "
                        f"of {label}." if headline else ""))

    # Retrieved method references. Attached to the answer as citations, never
    # merged into `facts` -- the numeral validator runs on facts, so a number
    # appearing in a retrieved document can never become a number in the
    # narration. Retrieval explains the method; the kernel measures.
    citations = get_retriever().cite(query, k=2)

    return AnswerPayload(
        **base, narration=narration, headline=headline, confidence=conf,
        evidence=ledger, layers=layers, plan=plan,
        corroboration=rainfall_context(scene_id),
        citations=citations,
        duration_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


def _recipe(intent: str):
    from .planner.tier_c import INTENT_RECIPE
    return INTENT_RECIPE.get(intent, ("vegetation", "gt", "the target class"))


def _demo() -> None:
    """Runnable check: the full pipeline on every demo path."""
    truth = json.loads((DEMO / "truth.json").read_text())["scenes"]

    # 1. Measurement matches ground truth.
    a = answer("How much area is flooded?", "bihar_post_flood")
    assert a.verdict == "ANSWER" and a.headline
    want = truth["bihar_post_flood"]["water_ha"]
    assert abs(a.headline["value"] - want) / want < 0.02, (a.headline, want)
    assert a.evidence and a.confidence.band == "High"
    assert a.corroboration and a.corroboration["total_mm"] > 400

    # 2. Change detection auto-pairs from the manifest.
    c = answer("how much more water than before?", "bihar_post_flood")
    assert len(c.scene_ids) == 2, c.scene_ids
    wd = truth["bihar_post_flood"]["delta_vs_pre_ha"]
    assert abs(c.headline["value"] - wd) / wd < 0.03, (c.headline, wd)

    # 3. ABSTAIN on missing bands, with no number invented.
    b = answer("show me the burn scar", "forest_burn")
    assert b.verdict == "ABSTAIN" and b.headline is None
    assert "SWIR2" in b.narration

    # 4. DEGRADE on cloud, and confidence must drop.
    d = answer("How much area is flooded?", "bihar_post_flood_cloudy")
    assert d.verdict == "DEGRADE" and d.confidence.score < a.confidence.score

    # 5. Negative control: barren scene must not report a large water area.
    n = answer("how much water is there?", "barren")
    # Barren has no water at all, so Otsu has no bimodal split to find. The kernel
    # must refuse rather than cut the single peak in half and report half the tile
    # as water -- that regression is why this assertion is strict about zero.
    assert n.headline is None, n.headline
    assert "No water was detected" in n.narration, n.narration

    # 6. Hinglish reaches the same intent and the same number.
    h = answer("kitna area baadh me hai", "bihar_post_flood")
    assert h.headline["value"] == a.headline["value"]

    # 7. The reply is written in the language the question was asked in, and the
    #    measured number does not move between languages -- translation may
    #    change the words around a figure, never the figure.
    for q, code in [("बाढ़ का क्षेत्र कितना है", "hi"),
                    ("ਹੜ੍ਹ ਦਾ ਖੇਤਰ ਕਿੰਨਾ ਹੈ", "pa"),
                    ("পানি কত আছে", "bn"),
                    ("நீர் எவ்வளவு", "ta")]:
        m = answer(q, "bihar_post_flood")
        assert m.language == code, (q, m.language)
        assert m.headline and abs(m.headline["value"] - a.headline["value"]) < 0.01, \
            f"{code} returned a different number: {m.headline}"
        # Narration must actually be in that script, not English with a label.
        assert not m.narration.startswith("2,"), f"{code} narrated in English"

    # 8. A question naming a place we hold no imagery for is refused by name,
    #    rather than answered from whichever scene happens to be selected.
    off = answer("how much flooding in Assam", "bihar_post_flood")
    assert off.verdict == "ABSTAIN" and off.headline is None
    assert "Assam" in off.narration, off.narration

    # 9. Scene overview differs per scene. It used to emit one content-free
    #    "analysis completed" line for every scene and every question.
    d1 = answer("describe this scene", "bihar_post_flood").narration
    d2 = answer("describe this scene", "barren").narration
    assert d1 != d2 and "index means" in d1 and "index means" in d2
    assert "withheld" not in d1, "overview numerals failed the guard"

    # 10. Knowledge / methodology questions return direct RAG explanation
    o = answer("what id the meaning of otsu", "bihar_post_flood")
    assert o.verdict == "ANSWER" and o.intent == "method_explain" and o.headline is None
    assert "Otsu" in o.narration and "variance" in o.narration

    print(f"pipeline: ok")
    print(f"  flood       {a.headline['value']} ha  conf {a.confidence.score} "
          f"({a.duration_ms:.0f} ms)")
    print(f"  change      {c.headline['value']} ha  ({len(c.evidence)} evidence rows)")
    print(f"  cloudy      {d.verdict}, conf {d.confidence.score}")
    print(f"  burn        {b.verdict}")
    print(f"  barren      {n.headline['value'] if n.headline else 'no area'} ha")


if __name__ == "__main__":
    _demo()
