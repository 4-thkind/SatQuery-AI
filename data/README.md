# SatQuery — Demo Imagery

Rebuild everything:

```
python scripts/build_data.py
```

Takes ~30 s. Deterministic — fixed seeds, so every machine produces byte-identical
scenes. Nothing here is downloaded; there is no network dependency.

## What's here

| File | What it is |
|---|---|
| `demo/*.tif` | 7 scenes, 1024×1024, 4 bands, uint16 |
| `demo/truth.json` | Exact ground-truth areas per scene |
| `demo/manifest.json` | Scene catalogue the backend loads at startup |
| `demo/previews/*.png` | False-colour + natural-colour renders for the UI |
| `demo/rainfall_supaul.csv` | Ancillary rainfall for the corroboration panel |

## The scenes

| Scene | Purpose | Ground truth |
|---|---|---|
| `bihar_pre_flood` | Baseline | 247.98 ha water |
| `bihar_post_flood` | Flood extent | 2603.17 ha water |
| `bihar_post_flood_cloudy` | **DEGRADE path** | 31.8% cloud |
| `forest_burn` | NBR / burn scar | 1210.63 ha |
| `urban_t1` / `urban_t2` | NDBI change | 452.25 → 1144.92 ha (+692.67) |
| `barren` | **ABSTAIN path** — negative control | 0 ha water |

Change detection pair: post − pre = **2355.19 ha** new inundation.

## Format

- **CRS** EPSG:32645 (UTM 45N), **10 m/px**, pixel area **100 m²**
- **Bands** `green, red, nir, swir16` — named in the GeoTIFF band descriptions,
  so ingest reads roles from the file rather than guessing an ordering
- **dtype** uint16, reflectance × 10000 (`SATQUERY_SCALE` tag) — same convention
  as a real Sentinel-2 L2A product, so calibrated-reflectance code paths are exercised
- **nodata** 0
- Footprint 26.036–26.129 °N, 86.600–86.703 °E — Supaul district, Kosi basin

## Why synthetic

Ground truth is exact by construction. Every number the kernel computes is
checkable against `truth.json` to <0.1%, which is exactly what the evidence-ledger
claim needs — with a downloaded scene there is no label to check against.

They are *radiometrically* real: reflectance signatures are physical, so NDWI,
MNDWI, NDVI, NDBI and NBR all behave as they do on real data. `verify_scenes.py`
proves this — it runs the actual index maths and Otsu thresholding and fails if any
index doesn't separate its class or any area drifts >5%.

Scenes carry a `SATQUERY_SYNTHETIC=1` tag and the manifest a `synthetic: true`
flag, and the UI shows a **SYN** badge on every scene. **Keep it that way.** The
integrity of the measurement claim is the point of the system; presenting
synthetic data as real would undermine everything else it does.

## Swapping in real imagery

Nothing above is required — ingest reads geometry and band roles from the file. A
real Sentinel-2 scene drops in once you have one:

1. Copernicus Browser → log in (download requires it) → **SEARCH** tab, not VISUALISE
2. Draw AOI, filter Sentinel-2 L2A, cloud <30%, date Aug–Sep 2024
3. Download icon in the right toolbar → **Analytical** tab
4. TIFF 16-bit, resolution HIGH, bands **B03 B04 B08 B11** (= green red nir swir16)
5. Save to `data/real/`, add an entry to `META` in `scripts/make_manifest.py`

Ground truth won't exist for it, so keep the synthetic scenes as the regression
fixtures either way.
