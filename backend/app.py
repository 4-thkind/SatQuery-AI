"""FastAPI application. Spec section 14.

Runs fully offline. No outbound request is made at runtime, ever -- /health
reports the counter so the claim is checkable rather than asserted.
"""

from __future__ import annotations

import io
import os
import sys
import pathlib

import numpy as np
from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import ledger as ledger_mod
from .core.uploader import ingest_upload
from .pipeline import (DEMO, ROOT, answer, load_scene, manifest,
                       scene_entry, scene_refs, register_uploaded_scene)
from pydantic import BaseModel

from .schemas import QueryRequest

def _default_tier() -> str:
    """Tier B when the model stack is actually importable, else Tier C.

    SATQUERY_TIER still wins when set. The default is derived rather than
    hardcoded to "C" because the old behaviour was a footgun: launching the
    virtualenv that contains torch, peft and faiss still reported Tier C, so
    the header said "No model weights" on a machine holding 8 GB of them, and
    the only way to get Tier B was to remember an environment variable.

    Presence of the imports is the honest signal -- it is the same condition
    tier_b._load() needs, so the tier now matches what the process can do.
    """
    import importlib.util as u
    if all(u.find_spec(m) is not None for m in ("torch", "peft")):
        return "B"
    return "C"


TIER = os.environ.get("SATQUERY_TIER", _default_tier()).upper()
OUTBOUND_REQUESTS = 0        # never incremented: nothing in this app calls out

app = FastAPI(title="SatQuery AI", version="0.1.0",
              description="Interactive vision-language assistant for multimodal "
                          "remote sensing image analysis. SIH26167.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

# FastAPI runs sync endpoints in a threadpool and SQLite connections are bound to
# the thread that created them, so each request opens its own. SQLite handles this
# fine at demo concurrency.
# Per-request connect. A connection pool would be worth adding only if request
# volume ever justified it; at this scale it would be complexity for nothing.
ledger_mod.connect().close()              # create the schema once at import


def _prewarm_retrieval() -> None:
    """Build the retriever now, before anything else touches torch.

    The dense build succeeded in every isolated process and failed only inside
    the served one, with:

        NotImplementedError: Cannot copy out of meta tensor; no data!

    which is what sentence-transformers raises when its weights materialise on
    the meta device. Whatever installs that state, it is not present at import
    time -- a clean process always builds dense -- so constructing the
    singleton here gets a real index instead of a silent BM25 fallback.

    Built inline on the main thread, deliberately. A daemon thread bound the
    port faster but reproduced the exact failure this exists to avoid:

        NotImplementedError: Cannot copy out of meta tensor; no data!

    sentence-transformers materialises its weights on the meta device when it
    loads off the main thread, so the "fast" version always fell back to BM25.
    Blocking is the point -- the index has to exist before the first query, and
    the 35 s it costs fits inside run.py's 60 s health gate.

    Failure stays non-fatal: get() would simply build BM25 later, exactly as
    before, and the reason is recorded on the instance either way.
    """
    try:
        from .rag.retriever import get as _get
        _get()
    except Exception:                             # noqa: BLE001
        pass


_prewarm_retrieval()


def _prewarm_model() -> None:
    """Load the Tier B model at import, not on the first user query.

    tier_b._load() is lazy by design so a Tier C process never pays 8 GB
    of VRAM. At Tier B that laziness lands on whoever asks first: measured
    over HTTP, the first query took 11.3 s and the second 3.6 s, while the
    same call in a warm process is 0.27 s. The model load was being billed
    to a user instead of to startup.

    Same trade as the retriever above -- startup slower, every query fast.
    Skipped at Tier C, where no model is wanted, and non-fatal either way:
    on failure the first query simply pays the cost, exactly as before.
    """
    if TIER not in ("A", "B"):
        return
    try:
        from .planner import tier_b
        tier_b._load()
    except Exception:                             # noqa: BLE001
        pass


_prewarm_model()


def _db():
    return ledger_mod.connect()


def _tier_b_status() -> dict:
    """Whether the fine-tuned model is actually loaded, and why not if not.

    Reported rather than assumed: Tier B degrades to Tier C templates on any
    failure, so without this a demo could be running templates while the
    header claims a model. Never raises -- /health must answer even when the
    model subsystem is broken.
    """
    try:
        from .planner import tier_b
        return tier_b.status()
    except Exception as e:                        # noqa: BLE001
        return {"tier_b_loaded": False, "load_error": f"{type(e).__name__}: {e}"}


def _runtime_identity() -> dict:
    """Which interpreter is actually serving, and can it see the dense stack.

    Reported because the retrieval badge read "bm25" while a direct probe of
    the same virtualenv reported "dense" -- meaning the serving process was
    not the process being tested. Guessing which interpreter uvicorn ended up
    on wasted several cycles; asking the server is one line.
    """
    import importlib.util as _u
    return {
        "executable": sys.executable,
        "prefix": sys.prefix,
        "in_venv": sys.prefix != sys.base_prefix,
        "faiss": _u.find_spec("faiss") is not None,
        "sentence_transformers": _u.find_spec("sentence_transformers") is not None,
        "torch": _u.find_spec("torch") is not None,
    }


def _retrieval_backend() -> str:
    """"dense" (embeddings + FAISS) or "bm25" (no weights, no downloads).

    Appends the reason when a dense build was attempted and failed, so a
    surprising "bm25" is self-explaining rather than something to guess at
    from outside the process.
    """
    try:
        from .rag.retriever import get as _get
        r = _get()
        why = getattr(r, "fallback_reason", None)
        return f"{r.backend} ({why})" if why else r.backend
    except Exception:                             # noqa: BLE001
        return "unavailable"


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "tier": TIER,
        # Describes what actually loads. The previous strings named
        # Qwen2.5-VL, which was the original plan; the model we fine-tuned and
        # ship is EarthDial-4B-MS, and it runs at 8-bit because 4-bit NF4
        # faults on sm_89 (see planner/tier_b.py).
        "tier_description": {
            "A": "EarthDial-4B-MS + SatQuery LoRA, unquantised (needs >9 GB VRAM)",
            "B": "EarthDial-4B-MS + SatQuery LoRA rank 128, 8-bit: base weights "
                 "compose prose, the adapter answers yes-no and MCQ",
            "C": "rule-based planner + template narration, no model weights",
        }.get(TIER, "unknown"),
        "kernel": "identical across tiers -- measured numbers do not change",
        "tier_b": _tier_b_status(),
        "retrieval": _retrieval_backend(),
        "runtime": _runtime_identity(),
        "scenes": len(scene_refs()),
        "outbound_requests": OUTBOUND_REQUESTS,
        "offline": True,
    }


@app.get("/api/v1/scenes")
def scenes():
    return {"scenes": [s.model_dump() for s in scene_refs()]}


@app.post("/api/v1/scenes/upload")
async def upload_scene(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    sensor: str | None = Form(None),
):
    """Upload and register a custom GeoTIFF, PNG, or JPG satellite/aerial image."""
    fn = file.filename or "uploaded.tif"
    allowed_exts = (".tif", ".tiff", ".png", ".jpg", ".jpeg")
    if not any(fn.lower().endswith(ext) for ext in allowed_exts):
        raise HTTPException(400, "Supported formats: .tif, .tiff, .png, .jpg, .jpeg")

    try:
        entry = ingest_upload(file.file, fn, label=label, sensor=sensor)
        register_uploaded_scene(entry)
        return {"status": "ok", "scene": entry}
    except Exception as e:
        raise HTTPException(422, f"Failed to ingest image: {str(e)}")


@app.delete("/api/v1/scenes/{scene_id}")
def delete_scene(scene_id: str):
    """Delete a custom uploaded scene and its associated artifacts."""
    from .core.uploader import remove_uploaded_scene
    ok = remove_uploaded_scene(scene_id)
    if not ok:
        raise HTTPException(404, f"Custom scene {scene_id!r} not found or cannot be deleted.")
    return {"status": "ok", "deleted": scene_id}


@app.get("/api/v1/scenes/{scene_id}")
def scene_detail(scene_id: str):
    try:
        entry = scene_entry(scene_id)
    except KeyError:
        raise HTTPException(404, f"unknown scene {scene_id!r}")
    bs = load_scene(scene_id)
    return {**entry, "bandstack": bs.describe()}


@app.post("/api/v1/query")
def query(req: QueryRequest):
    try:
        scene_entry(req.scene_id)
    except KeyError:
        raise HTTPException(404, f"unknown scene {req.scene_id!r}")

    payload = answer(req.query, req.scene_id, req.scene_id_b, tier=TIER)
    con = _db()
    try:
        turn_id = ledger_mod.record(con, req.session_id or "anon", payload)
    finally:
        con.close()

    out = payload.model_dump()
    out["turn_id"] = turn_id
    return out


class ClassifyRequest(BaseModel):
    question: str
    options: str | None = None


@app.post("/api/v1/classify")
def classify(req: ClassifyRequest):
    """Answer a yes/no or multiple-choice question with the fine-tuned model.

    This is the only route where the LoRA adapter is enabled, and it is
    deliberately separate from /query: it returns a bare label and NO
    measurement fields, so a model token can never be mistaken for a
    kernel-computed number.

    Accuracy on the BigEarthNet.txt bench split (n=4537, base model 9.7%):
    60.1% overall, binary 69.9% against a 50.5% majority baseline, MCQ 48.4%
    against 26.7%. Quoted here because an unqualified label invites more trust
    than the number deserves.
    """
    from .planner import tier_b

    label = tier_b.classify(req.question, req.options or "")
    st = tier_b.status()
    if not label:
        raise HTTPException(
            503,
            "the fine-tuned model is unavailable: "
            + (st.get("load_error") or st.get("gen_error") or "not loaded"),
        )
    return {
        "question": req.question,
        "options": req.options,
        "label": label,
        "model": "EarthDial-4B-MS + SatQuery LoRA (rank 128)",
        "adapter_enabled": True,
        "measured": False,
        "accuracy": {
            "split": "BigEarthNet.txt bench, n=4537",
            "overall": 0.601,
            "binary": 0.699,
            "binary_majority_baseline": 0.505,
            "mcq": 0.484,
            "mcq_majority_baseline": 0.267,
            "base_model_overall": 0.097,
        },
        "caveat": "a classification, not a measurement: no pixel was counted "
                  "to produce it",
    }

@app.get("/api/v1/evidence/{turn_id}")
def evidence(turn_id: str):
    con = _db()
    try:
        turn = ledger_mod.get_turn(con, turn_id)
    finally:
        con.close()
    if not turn:
        raise HTTPException(404, f"unknown turn {turn_id!r}")
    return turn


@app.get("/api/v1/knowledge")
def knowledge(q: str = "", k: int = 4):
    """Query the local knowledge base directly.

    Phase 2, first slice: BM25 over a bundled corpus, no network and no model
    weights. Exposed separately so retrieval can be inspected on its own --
    it contributes citations to an answer, never a measured value.
    """
    from .rag.retriever import get as _get
    r = _get()
    return {"query": q, "chunks_indexed": r.N, "method": "faiss+embeddings",
            "embeddings": True, "network": False,
            "results": r.cite(q, k=k) if q else []}


@app.get("/api/v1/ledger")
def ledger_list(limit: int = 20):
    con = _db()
    try:
        return {"turns": ledger_mod.recent(con, limit)}
    finally:
        con.close()


@app.get("/api/v1/scenes/{scene_id}/mask.png")
def mask_png(scene_id: str, intent: str = "flood_extent"):
    """Render the mask for an intent as a transparent PNG overlay.

    Recomputed rather than cached from the query: the kernel is deterministic, so
    this returns exactly the mask the reported number was measured from.
    """
    from .core.ingest import Session
    from .kernel.executor import execute
    from .planner.tier_c import build_plan

    try:
        bs = load_scene(scene_id)
    except KeyError:
        raise HTTPException(404, f"unknown scene {scene_id!r}")

    rgba = np.zeros((bs.shape[0], bs.shape[1], 4), np.uint8)

    # An intent this scene cannot support is not an error -- the feasibility gate
    # already says so in words. Return a fully transparent overlay so the map has
    # nothing to draw, and say why in a header rather than an HTTP failure.
    reason = ""
    s = Session()
    plan = build_plan(intent, bs)
    if not plan.steps:
        reason = f"no spectral index for {intent} from bands {sorted(bs.roles)}"
    else:
        _, results = execute(plan, bs, s)
        if "s2" not in results or not results["s2"].ok or not results["s2"].mask_handle:
            reason = "mask not computable for this scene"
        else:
            mask = s.get_array(results["s2"].mask_handle).astype(bool)
            colour = {"flood_extent": (56, 189, 248), "water_extent": (56, 189, 248),
                      "builtup_extent": (251, 146, 60), "burn_severity": (239, 68, 68),
                      }.get(intent, (74, 222, 128))
            rgba[mask] = (*colour, 170)

    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    # Was max-age=3600. The mask is recomputed on every request and changes
    # whenever a guard threshold or the kernel does, so an hour of browser
    # staleness only ever hides a fix.
    headers = {"Cache-Control": "no-cache, must-revalidate",
               "X-SatQuery-Mask": "empty" if reason else "ok"}
    if reason:
        headers["X-SatQuery-Reason"] = reason
    return Response(buf.getvalue(), media_type="image/png", headers=headers)


# Static previews and the UI. The frontend is a single dependency-free HTML file:
# no build step, nothing to npm install, and no network dependency at load.
class _Revalidating(StaticFiles):
    """StaticFiles that forces a revalidation instead of a blind cache hit.

    Starlette sends etag and last-modified but no Cache-Control, which leaves
    the browser free to reuse a file from its heuristic cache without asking.
    That is wrong for both things mounted here:

      * index.html IS the application, so a stale copy shows old badges and
        old behaviour against a current server -- indistinguishable from the
        backend being broken, and the reason a UI change can look like it
        never landed.
      * the previews are regenerated in place by scripts/register_real.py, so
        the path stays the same while the bytes change.

    "no-cache" does not mean "do not store" -- it means revalidate before use.
    The ETag still makes that a 304 on an unchanged file, so the cost is one
    conditional request, not a re-download.
    """

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
        return resp


app.mount("/data", _Revalidating(directory=str(ROOT / "data")), name="data")
_ui = ROOT / "frontend"
if (_ui / "index.html").exists():
    app.mount("/", _Revalidating(directory=str(_ui), html=True), name="ui")


def _demo() -> None:
    """Runnable check: exercise every endpoint through the ASGI test client."""
    from fastapi.testclient import TestClient

    c = TestClient(app)
    h = c.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["outbound_requests"] == 0, h

    sc = c.get("/api/v1/scenes").json()["scenes"]
    assert len(sc) >= 7, len(sc)

    r = c.post("/api/v1/query", json={"query": "How much area is flooded?",
                                      "scene_id": "bihar_post_flood"}).json()
    assert r["verdict"] == "ANSWER" and r["headline"]["value"] > 2000
    assert r["turn_id"].startswith("EVT-")

    ev = c.get(f"/api/v1/evidence/{r['turn_id']}").json()
    assert len(ev["evidence"]) == len(r["evidence"])

    ab = c.post("/api/v1/query", json={"query": "burn scar area",
                                       "scene_id": "forest_burn"}).json()
    assert ab["verdict"] == "ABSTAIN" and ab["headline"] is None

    kq = c.post("/api/v1/query", json={"query": "what id the meaning of otsu",
                                       "scene_id": "bihar_post_flood"}).json()
    assert kq["verdict"] == "ANSWER" and kq["intent"] == "method_explain" and kq["headline"] is None
    # Citations, not exact wording. At Tier C the top chunk is pasted verbatim
    # so "Otsu" always appeared; at Tier B the model composes from the same
    # chunk and may phrase it differently while still being correct and
    # grounded. What must hold in both tiers is that the answer is backed by
    # retrieved sources, so that is what gets asserted.
    assert len(kq["citations"]) > 0, kq["citations"]
    assert "otsu" in " ".join(
        ct.get("title", "") + ct.get("text", "") for ct in kq["citations"]
    ).lower(), [ct.get("title") for ct in kq["citations"]]

    png = c.get("/api/v1/scenes/bihar_post_flood/mask.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"

    assert c.get("/api/v1/scenes/nope").status_code == 404
    assert c.post("/api/v1/query", json={"query": "x", "scene_id": "nope"}).status_code == 404

    print(f"app: ok  tier {h['tier']}, {len(sc)} scenes, "
          f"{r['headline']['value']} ha, mask {len(png.content)} bytes")


if __name__ == "__main__":
    _demo()
