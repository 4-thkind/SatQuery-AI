# SatQuery AI — Project Context and Plan

**SIH26167** — An Interactive Vision-Language Assistant for Multimodal Remote
Sensing Image Analysis through Text Queries. ISRO / Dept. of Space. Team KERNEL.

This document is the working context for the team. Read it before asking an AI
assistant for help on this repo — paste the relevant section in as context so
it does not invent architecture we do not have.

Last updated after Round 2 training run 3.

---

## 1. The one rule everything else follows

> **No number reaches the user unless a deterministic function computed it from
> actual pixels. The language model plans and narrates; it never measures.**

This is the whole project. If a change would let a model produce a figure that
a user reads as a measurement, the change is wrong. Every design decision below
exists to protect this invariant.

Practical consequence worth internalising: **the backend loads no model at
all.** We verified this by grep — there are zero references to model weights,
LoRA adapters, or safetensors anywhere in `backend/`. The fine-tuned model is a
separate artifact used for planning and phrasing; the numbers come from
`backend/kernel/`.

---

## 2. Architecture as built

Six layers. A query moves down them in order.

| Layer | Where | What it does |
|---|---|---|
| L0 Ingest | `backend/core/ingest.py` | read GeoTIFF, resolve band roles from file metadata, not hardcoded order |
| L1 Feasibility gate | `backend/core/feasibility.py` | decide ANSWER / DEGRADE / ABSTAIN **before** measuring |
| L2 Planner | `backend/planner/` | classify intent, pick index, emit a tool plan |
| L3 Kernel | `backend/kernel/` | the only code allowed to produce numbers |
| L4 Narration | `backend/planner/tier_c.py` | phrase the result, validate no fabricated numerals |
| L5 Ledger | `backend/ledger.py` | SQLite record of every turn and its provenance |

### The kernel tool registry

Six tools, in `backend/kernel/registry.py`. The planner may only compose these:

```
compute_index          ndvi | ndwi | mndwi | ndbi | nbr | savi | evi | vari
threshold_mask         otsu | absolute | percentile, direction gt|lt
mask_difference        sub | union | intersect
measure_area           mask -> hectares / km² / scene fraction
threshold_sensitivity  sweep the threshold, report the area range
zonal_stats            statistics of a raster inside a mask
```

Five spectral indices are implemented in `backend/kernel/spectral.py`:

```
ndvi   (NIR - RED)   / (NIR + RED)
ndwi   (GREEN - NIR) / (GREEN + NIR)
mndwi  (GREEN - SWIR1) / (GREEN + SWIR1)
ndbi   (SWIR1 - NIR) / (SWIR1 + NIR)
nbr    (NIR - SWIR2) / (NIR + SWIR2)
```

### Tiers

Set by `SATQUERY_TIER`, reported at `/api/v1/health`. **The kernel is identical
across tiers — measured numbers never change between them.** Only planning and
phrasing differ.

| Tier | What runs |
|---|---|
| A | Qwen2.5-VL-7B planner + composer (4-bit) |
| B | Qwen2.5-VL-3B planner + composer (4-bit) |
| C | rule-based planner + template narration, no model weights |

Default is **C**. That is deliberate: the system must be fully demonstrable
with no model loaded at all.

---

## 3. The five guards

These are what make refusal a feature rather than a bug. A demo that never
refuses is a demo that will fabricate under pressure.

1. **`BandStack.band()` refusal** — asking for a band the sensor does not carry
   raises rather than substituting a near neighbour.
2. **Feasibility gate** — runs before any measurement, returns
   ANSWER / DEGRADE / ABSTAIN with a stated reason.
3. **Otsu separability floor** — `OTSU_MIN_SEPARABILITY = 0.35` in
   `backend/kernel/segmentation.py`. A weak backstop against a fully degenerate
   split.
4. **Physical support** *(added in Round 2 — see §4)* —
   `MIN_PHYSICAL_SUPPORT = 0.01` against the index's physical zero crossing.
5. **Numeral validator** — `backend/planner/validator.py` rejects any narration
   containing a number the kernel did not produce.

---

## 4. What Round 2 changed, and why

### 4.1 Real ISRO imagery broke a guard — this is our best finding

We downloaded 8 real Resourcesat-2A LISS-III scenes from **Bhoonidhi** (NRSC /
ISRO), path/row 106/053, converted them to 4-band GeoTIFFs, and ran the existing
kernel on them unmodified.

**Every index ABSTAINed.** The Round-1 separability floor was `0.75`. Measured
separability:

| source | separability |
|---|---|
| synthetic demo scenes | 0.835 – 0.998 |
| synthetic barren (negative control) | 0.632 |
| **real LISS-III** | **0.482 – 0.786** |

Real imagery scores *lower than our synthetic negative control* at identical
correctness. No single separability floor can work — barren sits inside the real
range.

The real discriminator turned out to be physical, not statistical: the fraction
of pixels on the meaningful side of the index's zero crossing. MNDWI > 0 is
**0.00%** for barren versus **3.7–76.5%** for real scenes.

So we added guard 4, `MIN_PHYSICAL_SUPPORT = 0.01`, with a table that is
**derived from radiative physics, not fitted**:

```python
PHYSICAL_ZERO = {
    "ndwi":  (0.0, "gt"),   # water reflects green >> NIR   (McFeeters 1996)
    "mndwi": (0.0, "gt"),   # water reflects green >> SWIR   (Xu 2006)
    "ndvi":  (0.0, "gt"),   # chlorophyll reflects NIR > red
}
```

An index whose sign carries no such interpretation is simply absent from the
table and skips the check, rather than being handed an invented threshold.

Lowered `OTSU_MIN_SEPARABILITY` to `0.35` — it is now a weak backstop only, with
physics doing the real work.

**Why this matters for the pitch:** Round 1 claimed real imagery would drop in
without code changes. It mostly did — ingest read band roles straight from the
file — but testing found a genuine guard-rail defect. That is a stronger story
than "it worked first time", because we can show the measurement that caught it.

### 4.2 Pipeline regression fixed

The new abstain code made narration fall through (17 checks → 16). Fixed with
`ABSENT_CLASS_REASONS` in `backend/pipeline.py`:

```python
ABSENT_CLASS_REASONS = frozenset({
    "no_physical_support", "degenerate_split", "unimodal_histogram"})
```

An abstention for these reasons now narrates as *"the class is absent"* rather
than *"the system failed"* — which is the honest reading.

### 4.3 LISS-III has no SWIR2

So NBR (burn severity) correctly refuses on real scenes. That refusal is **the
real sensor's real constraint**, not a limitation of our data. Good demo moment.

---

## 5. Model training — current state

### 5.1 What we chose and why

**EarthDial-4B-MS** (`akshaydudhane/EarthDial_4B_MS`) — InternVL2-4B
(InternViT-300M + Phi-3-Mini), already instruction-tuned on 11.11M remote-sensing
pairs across RGB, SAR, NIR and multispectral. 8.29 GB, Apache-2.0, CVPR 2025
(MBZUAI). Starting there makes our run a *second* adaptation rather than a
from-scratch attempt.

**LoRA, rank 64** — 100.7M trainable of 4.25B (2.37%). Adapter is 403 MB versus
8.29 GB for a full model. Trains in minutes, not hours.

Training corpus: **BigEarthNet.txt** (`BIFOLD-BigEarthNetv2-0/BigEarthNet.txt`),
446 MB parquet of instruction pairs. Imagery from a pre-encoded LMDB subset
(Lithuania summer, 2.5 GB) instead of the full 118.6 GB archive — same format,
minutes instead of hours.

**Honest caveat to state openly:** no prescribed dataset is Indian.
BigEarthNet is Europe; VRSBench/RSVQA/CDVQA are DOTA/DIOR, Netherlands/USA,
China. Our three data roles are therefore:

- **BigEarthNet** trains the model
- **its bench split** gives the quotable number
- **Bhoonidhi LISS-III** proves the pipeline runs on real Indian data

### 5.2 Results so far

Notebook: `notebooks/train_satquery.py` (marimo, runs on molab with a GPU).

| run | change | overall | n |
|---|---|---|---|
| 1 | 4 tasks incl. grounding + captioning | 54.9% | 207 |
| 2 | dropped grounding/captioning, bigger bench | 50.9% | 3,000 |
| 3 | category matching, binary balancing | 56.9% | 4,722 |

Run 3 detail — base model versus tuned, with a majority-class baseline so the
figures are readable:

| task | base | tuned | majority baseline |
|---|---|---|---|
| binary | 16.2% | 64.4% | 50.5% |
| mcq | 0.0% | 48.5% | 26.8% |

Train loss 7.08 → 0.27, val loss 8.12 → 0.26. Val fell with train, so the run
learned rather than memorised.

### 5.3 What we removed from the task mix, and the rule for doing so

This is the part to explain carefully, because "we deleted the hard questions"
is the obvious objection and the answer is a measurement.

**The rule: a category is excluded only if its tuned accuracy is at or below the
majority-class baseline** — meaning it demonstrably learned nothing and
including it reports noise as a result.

Excluded, with measured justification:

| excluded | measured | why |
|---|---|---|
| bounding box | 9.1%, two boxes repeated across 15 of 22 rows | coordinates come from pixels; vision tower is frozen |
| captioning | 45.9% from 6 distinct strings over 10 rows | token F1 was rewarding a memorised opening clause |
| season / climate zone / country | 23.6% / 24.7% / 26.3% against a 25% random floor | answer exists only in the pixels |
| presence | 49.8% binary against a 50.5% baseline — *below the floor* | same cause, caught by the baseline |

**Kept deliberately:** `adjacency` at 57.1% binary / 38.3% MCQ. Weak, but above
its baseline, so it is signal rather than noise. Dropping it too would be
cherry-picking. The rule is the baseline, and it is recorded in the run manifest
alongside the numbers.

All of these are recoverable by **unfreezing the vision tower** so pixels reach
the language model. That is the honest answer to "why not 80%?".

### 5.4 Two measured limits on how high this can go

**Prompt leakage — quote the clean number.** 28% of bench prompts appear
verbatim in training. `patch_id` overlap between splits is **zero** (the corpus
authors split properly); what recurs is question *wording*, applied to a
different patch, often with a different correct answer.

| | n | accuracy |
|---|---|---|
| unseen prompt wording | 2,797 | **59.1%** ← the number to quote |
| seen prompt wording | 745 | 68.3% |

Caveat against over-reading it: 743 of 745 leaked rows are binary, and binary
was essentially flat across the split (70.1% clean vs 68.2% leaked) — so this
looks like a sampling artefact, not memorisation. The notebook now reports both
every run and labels the clean figure explicitly.

**A hard ceiling at 94.1%.** 811 prompts (4,950 training rows, 20.9%) have
identical wording with *contradictory* answers, because the same question applies
to different patches and only the pixels disambiguate. Text-only supervision
cannot resolve these; the best possible is the majority answer per colliding
prompt. Nobody should chase a number above this.

### 5.5 Current notebook configuration

```python
TRAIN_SAMPLES = 40_000
EPOCHS        = 3          # run 3's loss was still falling when it stopped
EVAL_SAMPLES  = 5_000      # category matching trims this
MIN_EVAL_ROWS = 1_500      # below this, do not quote the number
LORA_RANK     = 64
LORA_ALPHA    = 128
BATCH_SIZE    = 16         # effective batch 16 in one pass
GRAD_ACCUM    = 1
LR            = 2e-4
SEED          = 26167
```

Expected runtime 50 min – 1h15m. **59.1% is a measured floor**, not a
prediction — it is run 3's own clean-row accuracy.

### 5.6 Version traps in the notebook — do not "fix" these

EarthDial pins torch 2.3.0 / CUDA 11.8 / transformers 4.37.2. That stack
**cannot** run on molab's Blackwell GPU (sm_120; torch ≤ 2.4 compiles only to
sm_90). It works anyway because EarthDial *vendors* Phi-3 rather than importing
it. Four patches in the notebook keep it alive:

1. `DynamicCache.get_usable_length` — renamed to `get_seq_length` in modern
   transformers; the alias is restored.
2. `rope_scaling` validator — EarthDial accepts only `['su','yarn']`, the
   checkpoint says `longrope`. Patched across every copy on disk.
3. `save_embedding_layers=False` — PEFT's default re-reads the base config
   through EarthDial's broken validator *after training finishes*.
4. Hand-rolled greedy decode — EarthDial's vendored `Phi3ForCausalLM` is a plain
   `nn.Module` with no `.generate()`.

Do not upgrade transformers past 4.56.

---

## 6. How to move forward

### 6.1 RAG — owner: see team split

Currently **BM25 over a 13-chunk hand-written corpus**. No embeddings, no
network, no model weights. That is a deliberate scope choice, stated plainly in
the module docstring: a corpus this small does not justify half a gigabyte of
sentence-transformer weights.

- Corpus: `data/knowledge/corpus.md`, split on `## ` headings. Add a section to
  add a chunk. **This file is in git** — it is not generated, do not delete it.
- Code: `backend/rag/retriever.py`. Entry point is `get()`.
- Self-test: `python -m backend.rag.retriever`
- Inspect over HTTP: `GET /api/v1/knowledge?q=mndwi&k=4`

`search()` has `min_score=1.0` — an unrelated question returns `[]` **on
purpose**. Retrieval contributes citations, never a measured value.

Existing chunks: NDWI, MNDWI, NDVI, NDBI, NBR, Otsu's method, Sentinel-2 MSI,
Resourcesat-2 LISS-III, cloud occlusion and optical limits, Sentinel-1 SAR for
flood mapping, flood extent measurement practice, Kosi basin flood context,
pixel counting and area.

Worth adding: LISS-III band roles and the missing-SWIR2 constraint, the physical
zero-crossing rationale, Bhoonidhi versus Bhuvan.

### 6.2 Frontend — owner: see team split

`frontend/index.html` — one file, no build step, no npm.

All eight routes:

```
GET  /api/v1/health
GET  /api/v1/scenes
GET  /api/v1/scenes/{scene_id}
GET  /api/v1/scenes/{scene_id}/mask.png
POST /api/v1/query
GET  /api/v1/evidence/{turn_id}
GET  /api/v1/knowledge?q=&k=
GET  /api/v1/ledger
```

`POST /api/v1/query` body:

```json
{"query": "...", "scene_id": "...", "scene_id_b": null, "session_id": null}
```

`scene_id_b` is the second epoch, for change detection.

Interactive docs while the server runs: `http://127.0.0.1:8000/docs`

**Build UI for refusals — this is not an edge case, it is the product.**
`barren` is a negative control where indices abstain by design;
`bihar_post_flood_cloudy` triggers the cloud path. Both must render a refusal
*with its stated reason*, not an error and not a blank. Abstention is a success
state.

Every response carries `turn_id` → `GET /api/v1/evidence/{turn_id}` returns the
full provenance chain. An execution-trace view over that is high value for the
demo.

### 6.3 Backend — all together, after RAG and frontend

Not started yet, in rough priority order:

1. **Registry integration for model-backed tools** — `vqa_answer`,
   `describe_scene`, `ground_region`, `change_describe`, `fuse_optical_sar`.
   These must go through the registry so the numeral validator still applies.
2. **Hash-chained ledger** — tamper-evident provenance.
3. **Execution-trace UI** — surface the plan and each tool's output.
4. **Downloadable report** — per-query PDF or HTML.
5. **Upload + co-registration checking** — reject mismatched pairs with a reason.
6. **4-bit quantisation** for local Tier A/B inference.

---

### 6.4 Git workflow — one branch per sub-team, never push to `main`

The team is now split across two workstreams, so `main` stays clean and
everything lands through branches.

**Do not commit to `main`. Do not push to `main`.** Only `main` is currently on
the remote; create your branch once and stay on it.

```bash
git checkout -b rag-frontend        # pick ONE name per sub-team, once
git add -A
git commit -m "feat(rag): ..."
git push -u origin rag-frontend     # -u only the first time
```

After the first push, the rest of the work is just:

```bash
git add -A
git commit -m "..."
git push
```

Rules:

- **One branch per sub-team**, not one per change. Keep pushing to the same
  branch — do not spawn a new branch for every commit.
- **Never `git push origin main`**, and never merge your branch into `main`
  yourself. Merges happen together once the backend work starts.
- **Pull `main` before you branch**, so you start from current work:
  `git checkout main && git pull && git checkout -b <your-branch>`
- If you need something from another branch mid-flight, say so rather than
  cherry-picking — two people resolving the same conflict twice wastes more time
  than a five-minute conversation.

Suggested names, so nobody has to guess: `rag-frontend` for the RAG and frontend
workstream, `model-training` for the notebook work.

### The notebook is being actively changed — do not edit it

`notebooks/train_satquery.py` is under live iteration on the `model-training`
side. Three runs are done and a fourth is queued; the configuration, the task
mix and the eval reporting have all changed between runs and will change again.

**Do not edit that file.** If you touch it you will either collide with an
in-flight change or silently invalidate a measured number that §5 quotes.

If you need something from the training side — a different metric reported, a
category reinstated, the adapter exported differently — ask rather than editing.
Same for the two Round-2 guard files, `backend/kernel/segmentation.py` and
`backend/pipeline.py`: the thresholds in them are derived from measurements
(§4.1), so changing a constant there quietly breaks the story we are telling.

Files that are yours to change freely:

| workstream | files |
|---|---|
| RAG | `data/knowledge/corpus.md`, `backend/rag/retriever.py` |
| frontend | `frontend/index.html` |
| either | new files, new scripts, new tests |

Everything else — ask first.

---

## 7. Data — what exists and where it comes from

| what | size | how you get it |
|---|---|---|
| code | small | `git clone` |
| `data/knowledge/corpus.md` | 8.9 KB | in git — RAG corpus, not generated |
| demo scenes (7 GeoTIFFs) | 66 MB | `python scripts/build_data.py`, fixed seed |
| real LISS-III converted | 102 MB | **in git** — cannot be regenerated |
| raw Bhoonidhi products | 3.4 GB | gitignored, nobody needs them |
| BigEarthNet.txt | 446 MB | training only |
| model weights / adapter | 8.29 GB / 403 MB | training only, molab fetches them |

The demo scenes are generated from a **fixed seed**, so everyone gets
byte-for-byte identical imagery — that is why the numbers in `truth.json` match
on every machine.

`data/real/converted/` is committed because those scenes came from a Bhoonidhi
account behind a login and **cannot be rebuilt**. Note the gitignore pattern:
`data/real/*` plus `!data/real/converted/`. A trailing-slash `data/real/` would
stop git descending into the directory at all and the negation could never
re-include anything. Do not "simplify" it.

### Setup

```bash
git clone https://github.com/4-thkind/SatQuery-AI
cd SatQuery-AI
pip install rasterio numpy pillow scikit-image pydantic fastapi "uvicorn[standard]"
python scripts/build_data.py
python scripts/check.py
python run.py
```

Python **3.10–3.12**. Python 3.13+ has no `rasterio` wheels.

Expect `ALL CHECKS PASSED` from `build_data.py` and `17/17 passed` from
`check.py`.

Optional:

```bash
pip install playwright && playwright install chromium
python scripts/ui_check.py      # server must be running
python scripts/verify_real.py   # runs the kernel on the real ISRO scenes
```

Training only:

```bash
git lfs install
git clone https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt
```

---

## 8. Constraints — non-negotiable

- **Zero outbound network requests at runtime.** Counter exposed at
  `/api/v1/health` as `outbound_requests`, and it is never incremented.
- **Indian satellite imagery must never be POSTed to a foreign API endpoint.**
- **Do not attempt live Bhuvan WMS/WCS ingestion.**
- **Synthetic scenes must be labelled synthetic in the UI.** Every demo scene
  carries a `synthetic` flag in its manifest entry. Use it.
- **Bhoonidhi ≠ Bhuvan.** Bhuvan is a map viewer serving display-stretched
  tiles. Bhoonidhi is the data portal with real bottom-of-atmosphere
  reflectance, full metadata, path/row and cloud search. **Only Bhoonidhi gives
  calibrated reflectance**, which is what absolute thresholds require.

---

## 9. Talking points for the demo

- **Base 8.6% → tuned 56.9%** overall; unseen-prompt accuracy **59.1%**. MCQ
  went 0% → 48.5% against a 26.8% majority baseline.
- **LoRA: 2.37% of parameters trained**, 403 MB adapter, ~20 minutes on one GPU.
  Compute-efficient by design, not brute force.
- **It runs on real ISRO data** — 8 Resourcesat-2A LISS-III scenes from
  Bhoonidhi, and testing them found and fixed a real guard-rail defect.
- **NBR refuses on LISS-III because the sensor has no SWIR2.** A real physical
  constraint, correctly surfaced.
- **The numbers do not come from the model.** Deterministic kernel, pixel
  counting, provenance in the ledger. The tier can be switched to C with no
  model loaded at all and every measurement is identical.
- **Refusals are a feature.** Five independent guards, each with a stated
  reason.

### Questions we should expect, and the honest answers

**"Why only ~59%?"** Most surviving questions still need pixels the frozen
vision tower never sees. Unfreezing it is the next step. Separately, 20.9% of
training rows have contradictory answers for identical prompt wording, which
caps any text-only model at 94.1%.

**"You removed the hard categories."** We removed categories that scored at or
below the majority-class baseline — they were measuring noise. `adjacency`, the
weakest survivor, was kept precisely because it is above its baseline. The rule
and the numbers are in the run manifest.

**"The dataset is European."** Correct, and stated up front. BigEarthNet trains
the model and gives the quotable number; the Bhoonidhi LISS-III scenes prove the
pipeline works on real Indian imagery. The kernel is sensor-agnostic — it reads
band roles from file metadata.

---

## 10. Using an AI assistant on this repo

Paste in the relevant sections above. Then:

**Say this:** the invariant from §1, which layer you are working in, and that
the backend loads no model.

**Watch for these mistakes** — assistants make them repeatedly on this codebase:

- Suggesting the backend load the fine-tuned model to answer questions. It must
  not. Numbers come from the kernel.
- Confusing `data/knowledge/corpus.md` (8.9 KB, RAG, in git) with
  BigEarthNet (446 MB, training only).
- "Fixing" the transformers version pins in the notebook. See §5.6.
- Treating an abstention as a bug to suppress. See §3.
- Adding a sentence-transformer to the RAG. The corpus is 13 chunks; BM25 is the
  right call and the docstring says why.
- Simplifying the `data/real/*` + `!data/real/converted/` gitignore pattern.
- Quoting 56.9% without the unseen-prompt caveat from §5.4.
- **Editing `notebooks/train_satquery.py`.** It is under live iteration on the
  training side (§6.4). An assistant will happily "improve" it and collide with
  an in-flight change or invalidate a measured number.
- **Committing or pushing to `main`.** Every change goes on a sub-team branch
  (§6.4). If an assistant offers `git push origin main`, decline.
- Changing a threshold in `backend/kernel/segmentation.py` or
  `backend/pipeline.py`. Those constants come from measurements (§4.1), not
  taste.
