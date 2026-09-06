# SatQuery AI

**SIH26167** — An Interactive Vision-Language Assistant for Multimodal Remote
Sensing Image Analysis through Text Queries. ISRO / Dept. of Space. Team KERNEL.

> No number reaches the user unless a deterministic function computed it from
> actual pixels. The language model plans and narrates; it never measures.

## Run it

```bash
pip install rasterio numpy pillow scikit-image pydantic fastapi "uvicorn[standard]"
python run.py
```

That is the whole thing. `run.py` builds the demo scenes if they are missing,
runs every self-check, frees port 8000 if a previous run is still holding it,
starts the server, verifies the UI in a real browser, and opens it.

No npm, no build step, no network.

| Command | What it does |
|---|---|
| `python run.py` | build if needed, verify, serve, open browser |
| `python run.py --full` | force a scene rebuild first (~90 s) |
| `python run.py --check` | verify only, no server — use this in CI |
| `python run.py --serve` | skip checks, just serve (fastest restart) |
| `python run.py --port 8001` | serve on another port |

The individual steps still work on their own if you want to run one:

```bash
python scripts/build_data.py   # regenerate scenes + verify against ground truth
python scripts/check.py        # 16 backend self-checks
python scripts/ui_check.py     # browser render + interaction (needs a server up)
```

Note `uvicorn` blocks, so chaining it with `&&` before `ui_check.py` will hang —
that is the reason `run.py` exists rather than a one-line shell chain.

## What it does

Ask a question about a scene. The system classifies intent, decides whether the
question is answerable **from these bands at all**, plans a sequence of kernel
tools, executes them, and narrates the result — refusing to narrate any number
the kernel did not compute.

| Query | Result |
|---|---|
| "How much area is flooded?" | **2,603.12 ha**, confidence 0.98 |
| "how much more water than before?" | **2,355.14 ha** new inundation, both epochs measured |
| "kitna area baadh me hai" | same intent, identical number, answered in Hinglish |
| "ਹੜ੍ਹ ਦਾ ਖੇਤਰ ਕਿੰਨਾ ਹੈ" | answered in Punjabi, same measured figure |
| "how much flooding in Assam" | **ABSTAIN** — no imagery for Assam, refused by name |
| "describe this scene" | per-index means, different for every scene |
| "show me the burn scar" | **ABSTAIN** — no SWIR2 band, recommends Sentinel-2 B12 |
| flood query on the cloudy scene | **DEGRADE** — confidence drops 0.98 → 0.36 |

## Languages

A question is answered in the language it was asked in — English, हिन्दी,
Hinglish, ਪੰਜਾਬੀ, বাংলা, தமிழ் and తెలుగు. Detection is by Unicode script block
(exact — the Indic scripts occupy disjoint ranges) plus romanised markers for
Hinglish, which shares the Latin block with English.

**No reply template contains a numeral.** Numbers arrive as parameters from the
kernel, so `validate_narration()` works unchanged in every language and a
translation cannot alter a figure. A self-check in `planner/phrases.py` enforces
this. The same flood question in seven languages returns the same hectares.

## Coverage

`planner/places.py` recognises place names and checks them against the imagery
actually loaded. A question about a district we do not hold is refused **by
name** rather than answered from whichever scene happens to be selected —
a correct number attached to the wrong place is the worst failure this system
can produce. Adding a district means ingesting its scene; the analysis path does
not change.

## Architecture

```
L0  ingest      GeoTIFF -> BandStack        backend/core/ingest.py
L1  gate        can these bands answer it?  backend/core/feasibility.py
L2  planner     query -> ToolPlan           backend/planner/
L3  kernel      the only place numbers      backend/kernel/
                are produced
L4  render      mask overlays               backend/app.py
L5  ledger      evidence, SQLite            backend/ledger.py
```

**Three tiers, one kernel.** `SATQUERY_TIER=A|B|C` swaps the planner and the
prose writer — never the measurement. Tier C (default) is rule-based with no
model weights and is a complete, honest system. Tiers A/B add a Qwen2.5-VL
planner. Because the kernel is identical, **the numbers cannot change between
tiers**. `/api/v1/health` reports the active tier.

### The invariants

- `BandStack.band(role)` raises `BandUnavailable` — it never substitutes another
  band. A wrong band yields a plausible wrong number, which is the failure mode
  this project exists to prevent.
- Every tool returns a `ToolResult` whose `provenance` is sufficient to recompute
  the value from the source raster alone.
- `validate_narration()` rejects any prose containing a numeral the kernel did
  not produce. It caught a hardcoded constant in our own template during
  development — that is the point.
- Confidence is the product of five measured components, never a model output.
- Zero outbound requests at runtime; the counter is exposed at `/health`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | tier, scene count, outbound-request counter |
| `GET /api/v1/scenes` | scene catalogue |
| `GET /api/v1/scenes/{id}` | scene detail + BandStack facts |
| `POST /api/v1/query` | `{query, scene_id}` -> AnswerPayload + turn_id |
| `GET /api/v1/evidence/{turn_id}` | full ledger for one answer |
| `GET /api/v1/ledger` | recent turns |
| `GET /api/v1/scenes/{id}/mask.png` | mask overlay (transparent if unsupportable) |

## Layout

```
backend/
  schemas.py          every wire contract (Pydantic v2)
  core/               bandstack, ingest, feasibility gate
  kernel/             spectral, segmentation, measurement, executor, registry
  planner/            intent, tier_c planner + narration, numeral validator
  pipeline.py         the one function that answers a question
  ledger.py           SQLite evidence store
  app.py              FastAPI
frontend/index.html   entire UI, one file, React via CDN, no build
scripts/              data generation + checks
data/                 demo scenes, ground truth, previews  (see data/README.md)
docs/screens/         screenshots from the last ui_check run
```

Every backend module has a `_demo()` self-check runnable with
`python -m backend.<module>`. They assert against the fixture ground truth, so a
broken measurement fails loudly rather than silently returning a wrong number.

## Data

Synthetic scenes with exact ground truth — see [data/README.md](data/README.md)
for why, and for how to swap in real Sentinel-2 imagery (no code changes needed).
**Scenes are labelled synthetic in the UI and carry a `SATQUERY_SYNTHETIC=1` tag
in the GeoTIFF metadata.** The ground truth is exact by construction, which is
what makes every measurement verifiable.

## Status

Built and verified: L0 ingest, L1 feasibility gate, L2 planner (7 languages,
place coverage), L3 kernel, L4 narration with the numeral guard, L5 evidence
ledger, the HTTP API, the UI, and a first retrieval slice over a local corpus.

Not yet built: Tier A/B VLM planner, SAR path, dense-vector retrieval,
GeoJSON/KML/PDF export, SAM segmentation, LoRA fine-tuning. The tool registry and
plan schema already accommodate them.

Known gap: `forest_burn` returns ABSTAIN because NBR requires SWIR2 (Sentinel-2
B12) and the fixtures carry only SWIR1 (B11). This mirrors a real sensor
limitation — Resourcesat-2 LISS-III has the same four-band constraint — so the
refusal is behaving correctly. Adding a B12 band to the generator would close it.
