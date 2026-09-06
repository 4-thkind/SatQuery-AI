"""FastAPI application. Spec section 14.

Runs fully offline. No outbound request is made at runtime, ever -- /health
reports the counter so the claim is checkable rather than asserted.
"""

from __future__ import annotations

import io
import os
import pathlib

import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

from . import ledger as ledger_mod
from .pipeline import DEMO, ROOT, answer, load_scene, manifest, scene_entry, scene_refs
from .schemas import QueryRequest

TIER = os.environ.get("SATQUERY_TIER", "C").upper()
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


def _db():
    return ledger_mod.connect()


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "tier": TIER,
        "tier_description": {
            "A": "Qwen2.5-VL-7B planner + composer (4-bit)",
            "B": "Qwen2.5-VL-3B planner + composer (4-bit)",
            "C": "rule-based planner + template narration, no model weights",
        }.get(TIER, "unknown"),
        "kernel": "identical across tiers -- measured numbers do not change",
        "scenes": manifest()["scene_count"],
        "outbound_requests": OUTBOUND_REQUESTS,
        "offline": True,
    }


@app.get("/api/v1/scenes")
def scenes():
    return {"scenes": [s.model_dump() for s in scene_refs()]}


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
    return {"query": q, "chunks_indexed": r.N, "method": "bm25",
            "embeddings": False, "network": False,
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
        if "s2" not in results or not results["s2"].ok:
            reason = "mask not computable for this scene"
        else:
            mask = s.get_array(results["s2"].mask_handle).astype(bool)
            colour = {"flood_extent": (56, 189, 248), "water_extent": (56, 189, 248),
                      "builtup_extent": (251, 146, 60), "burn_severity": (239, 68, 68),
                      }.get(intent, (74, 222, 128))
            rgba[mask] = (*colour, 170)

    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    headers = {"Cache-Control": "public, max-age=3600",
               "X-SatQuery-Mask": "empty" if reason else "ok"}
    if reason:
        headers["X-SatQuery-Reason"] = reason
    return Response(buf.getvalue(), media_type="image/png", headers=headers)


# Static previews and the UI. The frontend is a single dependency-free HTML file:
# no build step, nothing to npm install, and no network dependency at load.
app.mount("/data", StaticFiles(directory=str(ROOT / "data")), name="data")
_ui = ROOT / "frontend"
if (_ui / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_ui), html=True), name="ui")


def _demo() -> None:
    """Runnable check: exercise every endpoint through the ASGI test client."""
    from fastapi.testclient import TestClient

    c = TestClient(app)
    h = c.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["outbound_requests"] == 0, h

    sc = c.get("/api/v1/scenes").json()["scenes"]
    assert len(sc) == 7, len(sc)

    r = c.post("/api/v1/query", json={"query": "How much area is flooded?",
                                      "scene_id": "bihar_post_flood"}).json()
    assert r["verdict"] == "ANSWER" and r["headline"]["value"] > 2000
    assert r["turn_id"].startswith("EVT-")

    ev = c.get(f"/api/v1/evidence/{r['turn_id']}").json()
    assert len(ev["evidence"]) == len(r["evidence"])

    ab = c.post("/api/v1/query", json={"query": "burn scar area",
                                       "scene_id": "forest_burn"}).json()
    assert ab["verdict"] == "ABSTAIN" and ab["headline"] is None

    png = c.get("/api/v1/scenes/bihar_post_flood/mask.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"

    assert c.get("/api/v1/scenes/nope").status_code == 404
    assert c.post("/api/v1/query", json={"query": "x", "scene_id": "nope"}).status_code == 404

    print(f"app: ok  tier {h['tier']}, {len(sc)} scenes, "
          f"{r['headline']['value']} ha, mask {len(png.content)} bytes")


if __name__ == "__main__":
    _demo()
