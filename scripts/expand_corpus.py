"""Script to append comprehensive, grounded remote sensing and SatQuery architecture sections to corpus.md."""

from __future__ import annotations
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "knowledge" / "corpus.md"

ADDITIONAL_SECTIONS = """

## Masking and Binary Segmentation in SatQuery AI
source: SatQuery AI Architectural Specification & IEEE Transactions on Geoscience and Remote Sensing
tags: masking, mask, binary mask, segmentation, otsu, thresholding, morphological filtering, connected components, min_area_px

Masking in SatQuery AI is the deterministic process of converting a continuous floating-point spectral index raster into a binary spatial mask (a boolean NumPy array where True indicates the presence of the target class, such as flood water, healthy canopy, or built structures, and False denotes the background).

The masking pipeline executes the following rigorous sequence:
1. Continuous Index Extraction: The tool `compute_index` produces a 2D float32 raster (e.g., MNDWI, NDVI, NDBI) with values bounded in [-1.0, 1.0]. Pixels obscured by clouds or falling outside valid scene boundaries are represented as IEEE NaN.
2. Dynamic Cutoff Determination via Otsu: The tool `threshold_mask` extracts the valid non-NaN pixels and computes a normalized 256-bin histogram. Nobuyuki Otsu's discriminant algorithm is invoked to identify the threshold t* that maximizes between-class variance sigma_B^2(t).
3. Directional Application:
   - For flood and surface water (MNDWI > t*): parameter `direction="gt"` marks pixels strictly greater than the threshold as True.
   - For dense vegetation (NDVI > t*): parameter `direction="gt"` identifies photosynthetically active canopy.
   - For fire burn scars or drought stress (NBR < t* or NDVI < t*): parameter `direction="lt"` marks pixels with depressed values as True.
4. Morphological Noise Cleanup (Minimum Area Filtering): Optical thresholding inherently captures isolated single-pixel anomalies caused by mixed pixels, sensor noise, or small bright roofs. SatQuery applies 8-connectivity connected-component analysis (`scipy.ndimage.label`). Contiguous blobs containing fewer than `min_area_px` pixels (default: 50 pixels, equal to 0.50 hectares at 10 m resolution) are zeroed out.
5. Cloud Mask Intersection: The resulting mask is combined with the Scene Classification Layer (SCL) or Quality Assessment (QA) band. Any pixel classified as cloud shadow (SCL 3), cloud medium probability (SCL 8), cloud high probability (SCL 9), or thin cirrus (SCL 10) is set to False to eliminate cloud reflection artifacts.
6. Session Storage: The final boolean mask is stored in the in-memory Session array store under an immutable step handle (e.g., `$s2`) and logged in the execution ledger.

## Spectral Index Computation in SatQuery AI
source: Remote Sensing of Environment & SatQuery AI Computational Kernel
tags: index, compute, computation, spectral index, band arithmetic, ndvi, ndwi, mndwi, ndbi, nbr, float32, reflectance

Spectral index computation in SatQuery AI is executed within `backend/kernel/spectral.py` using standardized, radiometrically corrected band arithmetic across multi-spectral satellite channels.

The computation follows these strict mathematical and operational principles:
1. Semantic Band Mapping: The ingestion engine maps raw GeoTIFF channel indices to universal physical roles via `BandStack.roles` (e.g., Sentinel-2 B3 -> green, B4 -> red, B8 -> nir, B11 -> swir1, B12 -> swir2).
2. Normalized Difference Ratio: Most primary remote sensing indices employ the normalized difference formulation:
   Index = (Band_A - Band_B) / (Band_A + Band_B + epsilon)
   - Normalized Difference Vegetation Index (NDVI): (NIR - Red) / (NIR + Red)
   - Normalized Difference Water Index (NDWI, McFeeters 1996): (Green - NIR) / (Green + NIR)
   - Modified Normalized Difference Water Index (MNDWI, Xu 2006): (Green - SWIR1) / (Green + SWIR1)
   - Normalized Difference Built-up Index (NDBI, Zha 2003): (SWIR1 - NIR) / (SWIR1 + NIR)
   - Normalized Burn Ratio (NBR, Key and Benson 2006): (NIR - SWIR2) / (NIR + SWIR2)
   - Bare Soil Index (BSI, Rikimaru 2002): ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
3. Radiometric Precision: All arrays are cast to 32-bit floating point (`np.float32`). For Bottom-of-Atmosphere (BOA) surface reflectance (Sentinel-2 L2A), digital numbers scaled by 10,000 are normalized to physical reflectance [0.0, 1.0].
4. Zero-Division and Numerical Guards: To prevent division by zero or NaN generation over deep shadows, unilluminated terrain, or nodata voids, an epsilon stabilizer (1e-6) is incorporated into the denominator.
5. Strict Range Clamping: The output array is clamped to the theoretical domain [-1.0, 1.0]. Nodata pixels and cloud masks are tracked and propagated as invalid values to prevent skewing subsequent zonal statistics.

## Area Measurement and Pixel Counting in SatQuery AI
source: International Journal of Geographical Information Science & SatQuery Measurement Kernel
tags: area, measure, measurement, hectares, pixel counting, affine transform, gsd, ground sampling distance

Area measurement in SatQuery AI converts binary pixel classifications into physical, real-world land surface measurements (hectares and square kilometers) through rigorous geodetic transformation in `backend/kernel/measurement.py`.

The measurement engine adheres to the following sequence:
1. Spatial Resolution and Affine Transform: Every satellite tile includes an Affine geotransform matrix specifying pixel dimensions in map coordinates:
   | x_geo |   | a  b  c |   | x_pixel |
   | y_geo | = | d  e  f | * | y_pixel |
   |   1   |   | 0  0  1 |   |    1    |
   Here, |a| represents the ground sampling distance in the X direction (pixel width), and |e| represents the ground sampling distance in the Y direction (pixel height). For Sentinel-2 visible and NIR bands, |a| = 10.0 m and |e| = 10.0 m.
2. Ground Sampling Area per Pixel:
   Pixel_Area = |a * e| (square meters)
   At 10 m resolution, each individual pixel corresponds to exactly 10 m * 10 m = 100 square meters (0.01 hectares).
3. Integer Pixel Counting: The engine counts the total number of True pixels in the binary mask:
   N_px = sum(mask == True)
4. Hectare Conversion:
   Area (hectares) = (N_px * Pixel_Area) / 10,000
   Area (km^2) = Area (hectares) / 100
   For example, an inundation mask containing 214,300 pixels at 10 m resolution yields:
   (214,300 * 100 m^2) / 10,000 m^2/ha = 2,143.00 hectares (21.43 km^2).
5. Scene Fraction: The proportion of the valid observable ground covered by the feature is calculated as:
   Scene_Fraction = N_px / N_valid_pixels
   This metric prevents misleading reports when partial cloud cover obscures large sections of a tile.
6. Sensitivity Interval Bounding: To prevent false precision, SatQuery performs a multi-offset sensitivity sweep across [threshold - 0.05, threshold + 0.05]. The minimum and maximum resulting hectare figures establish the lower and upper bounds of measurement uncertainty.

## SatQuery AI System Architecture and Pipeline Flow
source: SatQuery AI System Architecture Specification (SIH26167)
tags: satquery, architecture, pipeline, system, workflow, execution, design

SatQuery AI is an interactive vision-language system engineered for multimodal Earth Observation analysis, operating under an architectural invariant:
"The computational kernel measures; retrieval grounds; language models synthesize; and numbers never cross boundaries unchecked."

The system processes queries through an eight-stage pipeline:
1. Ingestion and Session Scoping: Requests specify a user query, an active primary scene ID (e.g., 'bihar_post_flood'), and an optional secondary scene ID for change detection. The Session manages memory-mapped GeoTIFF handles.
2. Multilingual Intent Classification: Lexical and semantic classifiers identify user intent across English, Hindi, Hinglish, Bengali, Tamil, and Punjabi. Intents include `flood_extent`, `water_extent`, `vegetation_health`, `crop_stress`, `builtup_extent`, `burn_severity`, `change_detect`, `method_explain`, and `scene_describe`.
3. Geographic Coverage Gating: A spatial name entity extractor checks whether the user query references geographic locations outside the loaded scene coverage (e.g., asking about Assam while viewing Bihar). Out-of-bounds queries trigger an immediate graceful ABSTAIN to prevent hallucinated spatial projection.
4. Feasibility Gate: `feasibility.py` inspects the scene's available spectral bands and cloud fraction. It determines whether the query can be answered reliably (ANSWER), with degraded confidence due to cloud occlusion (DEGRADE), or must be refused due to missing bands (ABSTAIN).
5. Multi-Tier Planning (Tier A / Tier B / Tier C):
   - Tier A: Qwen2.5-VL-7B (4-bit AWQ) multimodal planner.
   - Tier B: Qwen2.5-VL-3B edge planner.
   - Tier C: Deterministic rule-based planner.
   All tiers emit an identical ToolPlan Directed Acyclic Graph (DAG).
6. Deterministic Kernel Execution: `executor.py` executes each tool step (`compute_index`, `threshold_mask`, `measure_area`, `threshold_sensitivity`, `mask_difference`, `zonal_stats`) producing verified facts.
7. Anti-Hallucination Numeral Guardrail: `validator.py` inspects the natural language narration before it leaves the backend. Any numeral that does not match an exact figure produced by the kernel is blocked, eliminating LLM hallucinations.
8. Evidence Ledger Recording: Every input hash, tool call, parameter set, and measured outcome is appended to an immutable SQLite database and assigned an audit identifier (`EVT-...`).

## Evidence Ledger and Cryptographic Auditability in SatQuery AI
source: SatQuery AI Specification Spec Section 14
tags: ledger, evidence, audit, provenance, sqlite, sha256, reproducibility

Remote sensing measurements used in disaster response, flood relief allocation, and insurance claims require verifiable proof, not ungrounded conversational claims. SatQuery AI guarantees reproducibility through an Evidence Ledger.

Key mechanisms of the Evidence Ledger:
1. Turn Identification: Every query transaction generates a globally unique identifier formatted as `EVT-YYYYMMDD-XXXXXX`.
2. Array Content Hashing: When GeoTIFF scenes are ingested, SHA-256 digests are computed across raw spectral bands, ensuring identical input state verification.
3. Execution Trace Recording: For every step executed in the pipeline DAG, the ledger records:
   - Tool name (e.g., `compute_index`, `threshold_mask`, `measure_area`)
   - Exact input parameters (e.g., index: "mndwi", threshold: -0.182, direction: "gt", min_area_px: 50)
   - Output handles and summary statistics (min, max, mean, pixel counts, measured hectares)
   - Runtime duration in milliseconds
4. Immutable SQLite Store: The ledger is committed to an ACID-compliant local SQLite database, allowing subsequent query inspection via `/api/v1/evidence/{turn_id}`.
5. Separation of Concerns: The ledger isolates measured physical facts from explanatory narrative. If a consumer requires only verified raw figures for a GIS shapefile or database update, they can extract the evidence ledger directly without parsing prose.

## The Invariant and Numeral Guardrail in SatQuery AI
source: SatQuery AI Anti-Hallucination Specification
tags: invariant, guardrail, numeral guard, validation, anti-hallucination, safety

A critical hazard in applying vision-language models to satellite imagery is numerical hallucination: generative language models frequently invent believable but entirely fabricated surface areas, percentages, and dates.

To eliminate this vulnerability, SatQuery AI implements a hard architectural guardrail:
1. The Cardinal Invariant:
   - Language models and retrieval components NEVER generate, measure, or alter numbers.
   - All numbers must originate exclusively from the deterministic Python computational kernel (`backend/kernel/`).
2. Dual-Pass Numeral Validation (`validator.py`):
   - Before any generated narration is transmitted to the user, a regular expression extractor collects all numeric tokens (integers, floats, percentages, and scientific notation).
   - Each extracted numeral is matched against the authoritative set of kernel facts generated during that turn (measured hectares, scene fraction, threshold values, cloud percentages, and confidence scores).
   - If an unauthorized numeral is detected, the generated text is withheld with the diagnostic message:
     `[Narration withheld: it contained {bad_numeral}, which the kernel did not compute. Showing measured values only.]`
   - The verified headline measurements are displayed alongside the diagnostic, completely eliminating hallucinated numerical figures.

## Change Detection Methodology and Bi-Temporal Analysis
source: Remote Sensing of Environment (Singh 1989) & SatQuery Kernel
tags: change detection, bi-temporal, difference mask, temporal pairing, pre-post, delta

Change detection in SatQuery AI quantifies dynamic land cover changes between two temporal epochs (e.g., pre-flood baseline vs post-flood crest, or pre-fire canopy vs post-fire burn scar).

The processing workflow executes as follows:
1. Bi-Temporal Scene Pairing: The system loads Scene A (post-event, epoch t2) and Scene B (pre-event baseline, epoch t1). GeoTIFF coordinate reference systems and pixel bounding boxes are aligned.
2. Independent Index Computation: The selected spectral index is computed for both epochs independently (e.g., MNDWI_A and MNDWI_B).
3. Independent Otsu Thresholding: Separate threshold masks are derived for each epoch (Mask_A and Mask_B), allowing each acquisition to calibrate to its specific solar zenith, atmospheric condition, and seasonal moisture state.
4. Boolean Difference Masking: The new or gained extent is isolated via boolean set subtraction:
   Mask_Delta = Mask_A AND (NOT Mask_B)
   This identifies pixels that represent the target class at epoch t2 but were absent at epoch t1.
5. Delta Area Measurement: The pixel counting engine measures:
   - Area_Epoch_A (total current extent)
   - Area_Epoch_B (baseline historical extent)
   - Area_Delta (new expansion or flooded land)
6. Dual-Epoch Sensitivity Propagation: Because threshold uncertainty exists in both epochs, the confidence scorer combines sensitivity spreads from both Scene A and Scene B, preventing overconfident change assessments.

## Five-Factor Confidence Scoring in SatQuery AI
source: SatQuery AI Uncertainty and Metrology Framework
tags: confidence, score, scoring, uncertainty, error budget, sensitivity spread, radiometry

Rather than reporting arbitrary confidence estimates from language model logits, SatQuery AI computes an objective, empirical confidence score as the mathematical product of five physical metrics:

Confidence = Feasibility_Prior * Cloud_Penalty * Threshold_Stability * Radiometry_Penalty * Grounding_Quality

Component Definitions:
1. Feasibility Prior (0.0 to 1.0): Reflects whether the sensor's spectral band configuration natively supports the target physical process. For instance, Sentinel-2 with SWIR bands has a prior of 1.0 for flood mapping, whereas a sensor lacking SWIR channels would receive a lower prior.
2. Cloud Penalty: Derived directly from the Scene Classification Layer (SCL) or QA band:
   Cloud_Penalty = 1.0 - min(Cloud_Fraction, 1.0)
   Scenes with 20% cloud cover suffer a 0.80 multiplier.
3. Threshold Stability: Computed from the threshold sensitivity sweep:
   Threshold_Stability = max(0.0, 1.0 - min(Sensitivity_Spread, 1.0))
   where Sensitivity_Spread = (Area_High - Area_Low) / Area_Base. A narrow spread signifies a sharp, stable bimodal histogram split.
4. Radiometric Calibration Penalty: Set to 1.0 for Bottom-of-Atmosphere (BOA) surface reflectance (Level-2A), and penalized to 0.75 for uncalibrated Top-of-Atmosphere digital numbers (Level-1C).
5. Grounding Quality: Set to 1.0 when retrieved literature citations corroborate the selected spectral index and methodology.

Score Categorization:
- High: Score >= 0.70
- Medium: 0.40 <= Score < 0.70
- Low: Score < 0.40

## Multi-Tier Architecture: Tier A, Tier B, and Tier C
source: SatQuery AI System Architecture Spec Section 12
tags: tier a, tier b, tier c, architecture, qwen, vlm, edge computing, offline

SatQuery AI is designed to deploy across diverse hardware environments, from GPU cloud clusters to edge devices in field command centers during disaster relief operations.

The three tiers are structured as follows:
1. Tier A (Cloud / Workstation GPU):
   - Model: Qwen2.5-VL-7B-Instruct (4-bit AWQ quantized).
   - Role: Performs vision-language query comprehension, flexible tool DAG composition, and natural language synthesis.
   - Resource Footprint: Requires approximately 6 GB VRAM.
2. Tier B (Edge / Laptop GPU):
   - Model: Qwen2.5-VL-3B-Instruct (4-bit AWQ quantized).
   - Role: Lightweight multimodal reasoning suited for field-deployed laptops and mobile command posts.
   - Resource Footprint: Requires approximately 3 GB VRAM.
3. Tier C (Zero-Weight Offline Deterministic Fallback):
   - Model: None. Pure deterministic Python rule engine and lexical parsing.
   - Role: Zero-dependency, CPU-only operation with instant startup and zero GPU requirements. Ideal for air-gapped field servers.
   - Crucial Invariant: The computational kernel (`backend/kernel/`) is IDENTICAL across all three tiers. A query executed on Tier C yields the exact same pixel mask, hectare figure, and evidence hash as Tier A.

## Otsu Thresholding Algorithm in Remote Sensing and Edge Cases
source: Otsu 1979, IEEE Transactions on Systems, Man, and Cybernetics & SatQuery Kernel
tags: otsu, algorithm, variance, bimodal, unimodal, degenerate split, failure modes, thresholding

Nobuyuki Otsu's thresholding algorithm is a foundational non-parametric method for unsupervised image segmentation. In satellite remote sensing, it is widely utilized to separate water from land or vegetation from soil based on spectral index histograms.

Mathematical Formulation:
Given an index raster normalized into L discrete levels (typically L = 256 bins), with normalized histogram probabilities p_i for i in [0, L-1]:
1. Cumulative class probabilities:
   omega_0(t) = sum_{i=0}^t p_i  (background class)
   omega_1(t) = 1 - omega_0(t)  (foreground target class)
2. Class mean levels:
   mu_0(t) = sum_{i=0}^t (i * p_i) / omega_0(t)
   mu_1(t) = sum_{i=t+1}^{L-1} (i * p_i) / omega_1(t)
3. Between-class variance:
   sigma_B^2(t) = omega_0(t) * omega_1(t) * (mu_0(t) - mu_1(t))^2
4. Optimal threshold t*:
   t* = argmax_t sigma_B^2(t)

SatQuery Robustness Guards and Failure Modes:
1. Bimodal Assumption: Otsu assumes a bimodal histogram. In flood scenes containing both open water and dry terrain, the MNDWI histogram displays two distinct peaks separated by a deep valley, allowing Otsu to identify the exact water boundary.
2. Unimodal Collapse in Uniform Scenes: In scenes with no water (e.g., arid desert or uniform forest), the histogram is unimodal. Naive Otsu will arbitrarily slice the single peak in half, reporting roughly 50% of the desert as flood water.
3. Degenerate Split Guards in SatQuery:
   - `unimodal_histogram`: If between-class variance ratio sigma_B^2 / sigma_Total^2 falls below 0.30, the scene lacks bimodality.
   - `no_physical_support`: If the optimal threshold falls outside physically plausible ranges (e.g., MNDWI threshold > +0.40 or < -0.60), the kernel rejects the split.
   - `degenerate_split`: If the resulting mask occupies < 0.01% or > 99.9% of valid pixels, the split is aborted.
When a guard triggers, SatQuery safely reports that no target feature was detected rather than hallucinating false positive extent.

## BandStack Architecture and GeoTIFF Ingestion
source: SatQuery Core Ingestion Engine (`backend/core/ingest.py`)
tags: bandstack, geotiff, ingestion, rasterio, bands, affine, crs, gdal

The `BandStack` dataclass in SatQuery AI provides an in-memory abstraction for multi-spectral Earth Observation scenes loaded from GeoTIFF assets via `rasterio`.

Core Capabilities:
1. Spatial Metadata Encapsulation: Stores the raster dimensions (height, width), coordinate reference system (CRS, e.g., EPSG:32645), georeferenced bounding box (bounds), and affine transform matrix.
2. Semantic Role Resolution: Rather than relying on arbitrary band order (which varies across sensor providers), BandStack maps channels to universal physical roles:
   `roles: dict[str, int]` (e.g., {"blue": 0, "green": 1, "red": 2, "nir": 3, "swir1": 4, "swir2": 5, "scl": 6}).
3. On-Demand Array Retrieval: Methods `get(role)` and `has(*roles)` enable kernel tools to dynamically request spectral bands without hardcoding channel indices.
4. Scale Flagging: Tracks whether pixel values represent scaled Bottom-of-Atmosphere reflectance (0-10000 DN) or raw sensor units, ensuring appropriate scaling factors are applied during index computation.
5. In-Memory Session Caching: High-resolution satellite tiles (often 10-50 MB per tile) are cached in `pipeline.py`, eliminating redundant disk I/O across interactive conversational turns.

## Multilingual Processing and Script Preservation in SatQuery AI
source: SatQuery Multilingual Framework
tags: multilingual, hindi, hinglish, bengali, tamil, punjabi, localization, translation

SatQuery AI provides native support for disaster managers, local authorities, and field teams across South Asia by processing natural language in English, Hindi (Devanagari), Bengali, Tamil, Punjabi (Gurmukhi), and transliterated Hinglish.

Key Architectural Principles:
1. Query Language Detection: Integrated language identification examines Unicode script blocks and linguistic n-grams to identify the query language at the very beginning of the pipeline.
2. Transliterated Lexicon Matching: Many operational users type conversational Hinglish (e.g., "kitna area baadh me hai" or "paani kitna badh gaya"). SatQuery's intent lexicon includes phonetically transliterated operational terminology alongside formal Hindi script.
3. Number Invariance Across Translations: While explanatory narratives are translated into the requested target language or script, numerical measurements (e.g., 2,143.00 ha) remain untouched and mathematically identical across all languages.
4. Multilingual Error and Refusal Messages: When queries must be refused due to out-of-bounds geographic targets or missing bands, refusal explanations are returned in the user's language, preventing dead-end user experiences.

## Disaster Context: Bihar Kosi River Monsoonal Floods
source: National Remote Sensing Centre (NRSC) / ISRO Disaster Management Support Programme
tags: bihar, kosi, flood, supaul, monsoon, inundation, avulsion, siltation

The Kosi River basin in North Bihar is one of the most flood-prone regions in South Asia. Known historically as the "Sorrow of Bihar", the Kosi originates in the Himalayas, carries immense sediment loads (among the highest coarse silt concentrations in the world), and has migrated westward across 120 km over the past 250 years.

Remote Sensing Dynamics in the Kosi Basin:
1. Annual Monsoon Inundation: Between July and September, heavy precipitation in the upper catchment of Nepal and Bihar generates extensive river overflowing, embankment breaches, and widespread backwater inundation across Supaul, Saharsa, Madhepura, and Khagaria districts.
2. Silt Deposition and Water Turbidity: Kosi floodwaters carry extreme suspended sediment loads. High turbidity elevates red and NIR reflectance in turbid water, causing traditional NDWI (Green - NIR) to misclassify sediment-laden floodwater as bare soil. Modified NDWI (MNDWI, using SWIR1) is essential in Bihar because SWIR radiation is strongly absorbed by water regardless of sediment concentration.
3. Pre- and Post-Flood Analysis: SatQuery's bundled reference pair (`bihar_pre_flood` acquired May 2024, `bihar_post_flood` acquired August 2024) captures the seasonal expansion of inundation over Supaul district, illustrating the critical transition from dry post-harvest agricultural fallow to deep standing flood extent.

## Disaster Context: Assam Brahmaputra River Basin Floods
source: Brahmaputra Board & Space Applications Centre (ISRO)
tags: assam, brahmaputra, flood, kaziranga, annual inundation, braided river, sar

The Brahmaputra valley in Assam experiences recurring catastrophic flooding during the Southwest monsoon season, triggered by extreme rainfall in the Eastern Himalayas and cloudburst events in Arunachal Pradesh and Assam.

Remote Sensing Monitoring Characteristics:
1. Braided River Morphology: The Brahmaputra is a classic braided river system with dynamic sandbars (chars) that shift constantly following major flood pulses. Differentiating permanent river channels from seasonal flood inundation requires multi-temporal comparison with dry-season baselines.
2. Severe Cloud Persistence: During peak monsoon months (June-August), cloud cover over the Brahmaputra valley exceeds 85%, severely limiting optical observation. Synthetic Aperture Radar (SAR, Sentinel-1 C-band) is the operational gold standard, providing all-weather penetration through persistent monsoon clouds.
3. Ecological Monitoring (Kaziranga National Park): Flood pulses provide essential ecological renewal for Kaziranga wetlands but force wildlife migration across national highways to higher ground in Karbi Anglong hills. Rapid satellite delineation of highland corridors is vital for anti-poaching and highway traffic management.

## Disaster Context: Kerala Extreme Rainfall and Floods (2018-2019)
source: Kerala State Disaster Management Authority (KSDMA) & Geological Survey of India
tags: kerala, floods, landslides, western ghats, extreme precipitation, reservoir releases

In August 2018, Kerala experienced its worst flooding in nearly a century, caused by continuous extreme precipitation pulses that filled 35 major reservoirs to capacity, necessitating synchronized emergency spillway discharges into the Periyar, Pamba, and Chalakudy river basins.

Remote Sensing Insights:
1. Steep Western Ghats Topography: The terrain transitions rapidly from 2,000 m mountain ridges to coastal lowlands within 60 km. Satellite radar analysis required careful terrain correction (Range-Doppler orthorectification) to eliminate layover and foreshortening distortions on mountainous slopes.
2. Compound Flood and Landslide Hazard: In addition to riverine lowland inundation, heavy rainfall triggered over 4,000 landslides and debris flows in Idukki and Wayanad districts. Optical change detection (NDVI reduction) combined with high-resolution DEM slope analysis identified debris track scars.
3. Urban Inundation in Kochi: Flat coastal wetlands and backwaters (Vembanad Lake) faced severe drainage congestion compounded by high tides, captured through bi-temporal Sentinel-1 backscatter change detection.

## Disaster Context: Chennai Urban Pluvial Floods (2015)
source: Ministry of Earth Sciences & Anna University Remote Sensing Studies
tags: chennai, urban flood, pluvial, adyar river, drainage congestion, builtup

In November-December 2015, the metropolitan city of Chennai, Tamil Nadu, was struck by unprecedented northeast monsoon rainfall (over 490 mm in 24 hours), causing catastrophic urban inundation along the Adyar, Cooum, and Kosasthalaiyar river basins.

Remote Sensing Considerations in Urban Terrain:
1. Pluvial vs Riverine Flooding: Unlike rural floodplains, urban flooding involves micro-topography, storm sewer backups, paved impervious surfaces, and obstruction by road embankments and buildings.
2. Spectral Challenges with Urban Roofs: Smooth asphalt and concrete rooftops can exhibit low specular reflectance in certain optical angles, occasionally mimicking water spectral signatures in naive classification. Using MNDWI and intersecting with high-resolution building footprints prevents false building roof detections.
3. Shadow Occlusion: Tall multi-story structures cast deep optical shadows that resemble water bodies (low reflectance across visible and NIR bands). SatQuery's multi-spectral feature verification ensures that shadow pixels are not falsely enumerated as flooded land.

## Disaster Context: Chamoli Disaster and Rock-Ice Avalanches (2021)
source: Wadia Institute of Himalayan Geology & Science 373 (2021)
tags: chamoli, uttarakhand, glof, rock avalanche, rishi ganga, tapovan, flash flood

On 7 February 2021, a catastrophic flash flood swept through the Rishiganga and Dhauliganga river valleys in Chamoli district, Uttarakhand, devastating the Rishiganga and Tapovan-Vishnugad hydroelectric power projects.

Satellite Remote Sensing Analysis:
1. Origin Identification: Multi-spectral imagery from PlanetScope and Sentinel-2 identified that the disaster was initiated by a massive wedge detachment of approximately 27 million cubic meters of rock and glacial ice from the northern slope of Ronti peak (~5,500 m elevation).
2. Debris Flow Transformation: The falling mass pulverized upon impact, converting frictional heat into water melt and creating a hyper-concentrated slurry that surged down the narrow valley at speeds exceeding 25 m/s.
3. Cryospheric Monitoring: Satellite thermal infrared and optical red-edge sensors are essential in the Himalayas to monitor hanging glaciers, proglacial moraine-dammed lakes, and potential Glacial Lake Outburst Floods (GLOFs) before failure occurs.

## Disaster Context: Sundarbans Mangrove Cyclone and Salinity Dynamics
source: Forest Survey of India (FSI) & Wildlife Institute of India
tags: sundarbans, mangrove, cyclone, amphan, salinity, ndvi, ndre, tidal

The Sundarbans delta, spanning West Bengal (India) and Bangladesh, is the largest contiguous mangrove forest in the world, serving as a critical coastal bio-shield against tropical cyclones originating in the Bay of Bengal.

Remote Sensing Monitoring:
1. Cyclone Impact (Super Cyclone Amphan 2020): Severe tropical cyclones produce destructive storm surges (4-6 m) and hurricane-force winds that strip mangrove canopies. Post-cyclone optical assessments measure severe canopy defoliation through sharp drops in NDVI and NDRE.
2. Tidal Fluctuations: Mangrove forest floors are inundated twice daily by astronomical tides. Distinguishing normal tidal inundation from cyclone storm surges requires temporal baseline normalization against tidal height records at the exact time of satellite overpass.
3. Soil Salinity Stress: Upstream freshwater diversion and sea-level rise increase soil salinity, causing physiological drought in Heritiera fomes (Sundari trees). Red Edge spectral bands (Sentinel-2 B5, B6, B7) are particularly sensitive to chlorophyll degradation caused by salinity-induced stress.

## Forest Fire Burn Severity and Post-Fire Regeneration Mapping
source: Key and Benson 2006 (USGS FIREMON) & US Forest Service
tags: burn severity, nbr, dnbr, wildfire, usgs, forest fire, ecology

Wildfire impact and post-fire ecological damage are quantified via the Normalized Burn Ratio (NBR) and its bi-temporal difference (dNBR).

Bi-Temporal Burn Formulation:
1. Pre-fire NBR: NBR_pre = (NIR_pre - SWIR2_pre) / (NIR_pre + SWIR2_pre)
2. Post-fire NBR: NBR_post = (NIR_post - SWIR2_post) / (NIR_post + SWIR2_post)
3. Delta NBR: dNBR = NBR_pre - NBR_post (multiplied by 1000 for standard USGS integer scaling)

USGS Burn Severity Classification Scheme:
- High Severity (dNBR > 660): Complete consumption of canopy foliage, deep organic soil charring, high tree mortality.
- Moderate-High Severity (440 < dNBR <= 660): Extensive canopy scorching, medium soil char, partial vegetation survival.
- Moderate-Low Severity (270 < dNBR <= 440): Ground fire with partial understory burn, tree overstory largely intact.
- Low Severity (100 < dNBR <= 270): Surface scorching of litter, minimal understory destruction.
- Unburned (-100 <= dNBR <= 100): No visible fire effect.
- Enhanced Regrowth (dNBR < -100): Post-fire herbaceous flush or vigorous pioneer vegetative growth.

SWIR2 Sensitivity: Healthy green canopy reflects heavily in NIR and absorbs SWIR2. Burned char absorbs NIR and strongly reflects SWIR2, producing a pronounced negative shift in NBR.

## Agricultural Drought and Crop Stress: Early Warning Systems
source: Kogan 1995, Bulletin of the American Meteorological Society & FAO
tags: drought, crop stress, agriculture, ndvi, ndre, savi, vci, vhi, moisture

Agricultural drought occurs when soil moisture deficiency during critical crop growth stages impairs plant transpiration, restricts vegetative biomass, and reduces crop yields.

Remote Sensing Early Warning Indices:
1. Vegetation Condition Index (VCI):
   VCI = 100 * (NDVI_current - NDVI_min) / (NDVI_max - NDVI_min)
   Normalizes the current NDVI against multi-year historical extremes for the same week of the calendar year, separating climate-driven stress from normal seasonal phenology. VCI < 35 indicates moderate drought; VCI < 20 indicates severe drought.
2. Soil Adjusted Vegetation Index (SAVI):
   SAVI = ((1 + L) * (NIR - Red)) / (NIR + Red + L)
   With L = 0.5, SAVI eliminates background soil brightness effects during early vegetative emergence when canopy cover is sparse.
3. Normalized Difference Red Edge Index (NDRE):
   NDRE = (NIR - RedEdge) / (NIR + RedEdge)
   Sentinel-2 Red Edge bands (B5 at 705 nm) penetrate deeper into dense crop canopies than red bands, detecting chlorophyll nitrogen stress before visual canopy yellowing occurs.

## SAR Backscatter Mechanics: Roughness, Moisture, and Corner Reflectors
source: Ulaby, Moore, and Fung, Microwave Remote Sensing: Active and Passive
tags: sar, backscatter, dielectric, roughness, double bounce, corner reflector, radar

Synthetic Aperture Radar (SAR) systems transmit coherent microwave pulses (e.g., C-band 5.4 GHz, wavelength ~5.6 cm) and measure the amplitude and phase of backscattered radiation, characterized by the backscatter coefficient sigma_0 (in decibels, dB).

Three Primary Backscattering Mechanisms:
1. Specular Reflection (Smooth Open Water): Calm water surfaces behave as specular reflectors at microwave wavelengths. The transmitted radar pulse reflects away from the sensor like a mirror, returning near-zero energy to the receiver. Water pixels appear pitch black (typically -18 dB to -24 dB in Sentinel-1 VH/VV polarization).
2. Volume Scattering (Vegetation Canopies): Forest canopies and dense crops contain countless leaves, twigs, and branches comparable in size to the radar wavelength. Radiation scatters multiple times in all directions, returning moderate, diffuse backscatter (-10 dB to -15 dB).
3. Double-Bounce Scattering (Urban Structures & Flooded Forests): Vertical building walls or tree trunks standing in open water form 90-degree dihedral corner reflectors. The microwave pulse bounces off the horizontal water surface onto the vertical wall and returns directly back to the satellite, creating exceptionally bright radar returns (-3 dB to +5 dB). This allows SAR to detect flooding beneath tree canopies where optical sensors see only green leaves.

## Optical and SAR Data Fusion for All-Weather Disaster Monitoring
source: ESA Copernicus & International Journal of Remote Sensing
tags: fusion, optical, sar, all-weather, sentinel-1, sentinel-2, cloud penetration

Combining optical multi-spectral imagery (Sentinel-2) and Synthetic Aperture Radar (Sentinel-1) yields a synergistic Earth Observation framework that overcomes the fundamental limitations of each modality.

Benefits of Optical-SAR Fusion:
1. All-Weather Cloud Penetration: While optical sensors are completely blind under monsoon overcast and heavy rain clouds, C-band SAR penetrates atmospheric moisture effortlessly.
2. Resolving Urban Water Ambiguities: In dense urban zones, radar backscatter suffers from corner reflections and shadow layover from skyscrapers, whereas optical MNDWI easily identifies flooded streets and courtyards when clouds clear.
3. Automated Harmonization: Satellite scenes are co-registered to a common UTM projection and resampled to 10 m pixel grids. Optical MNDWI water masks provide ground truth to calibrate dynamic SAR thresholding during cloud-covered periods.

## Coordinate Reference Systems and Projected Geometry in India
source: Survey of India & EPSG Geodetic Parameter Dataset
tags: crs, projection, utm, wgs84, epsg, area distortion, geodesy

Accurate spatial measurement of surface areas requires projecting the curved Earth (ellipsoid) onto a conformal, equal-area flat coordinate reference system.

Geodetic Standards in SatQuery AI:
1. Geographic Coordinates (WGS84, EPSG:4326): Expresses coordinates in angular degrees of latitude and longitude. Measuring area directly in EPSG:4326 by counting pixels results in catastrophic errors because the ground distance of one degree of longitude shrinks from 111.32 km at the equator to 0 km at the poles.
2. Universal Transverse Mercator (UTM): The global standard conformal projection dividing the globe into 6-degree longitudinal zones. Coordinates are expressed in linear meters (Easting, Northing).
3. UTM Zones for India (WGS 84 / UTM North):
   - Zone 42N (EPSG:32642): Western Gujarat and Rajasthan.
   - Zone 43N (EPSG:32643): Maharashtra, Goa, Karnataka, Kerala, Western MP.
   - Zone 44N (EPSG:32644): Delhi, UP, Bihar, Telangana, Andhra Pradesh, Tamil Nadu.
   - Zone 45N (EPSG:32645): West Bengal, Odisha, Jharkhand, Sikkim, Assam, Meghalaya.
   - Zone 46N (EPSG:32646): Arunachal Pradesh, Nagaland, Manipur, Mizoram.
4. Scale Factor: Within each UTM zone, scale distortion is less than 0.1% near the central meridian, making pixel-counting area calculations exceptionally accurate.

## Remote Sensing Feasibility Gate and Feasibility Assessment
source: SatQuery Feasibility Engine (`backend/planner/feasibility.py`)
tags: feasibility, gate, bands, sensor capability, abstain, degrade, quality

The Feasibility Gate in SatQuery AI acts as an authoritative pre-computation checkpoint that evaluates whether a user's question can be physically and scientifically answered from the loaded satellite data.

Evaluation Steps:
1. Band Requirement Verification: Every physical intent requires specific spectral bands:
   - Flood and water mapping: Requires Green and NIR (for NDWI) or Green and SWIR1 (for MNDWI).
   - Vegetation health: Requires Red and NIR.
   - Burn severity: Requires NIR and SWIR2.
   - Built-up land: Requires SWIR1 and NIR.
   If a scene lacks the required band (e.g., trying to map burn severity on an RGB-only sensor lacking SWIR2), the feasibility gate immediately refuses with an ABSTAIN verdict and explains exactly which sensor channel was missing.
2. Atmospheric Cloud Occlusion Check: If cloud cover across the region of interest exceeds acceptable thresholds (e.g., cloud fraction > 0.40), the verdict degrades to DEGRADE with a proportional confidence penalty.
3. Multi-Epoch Pairing Check: For change detection intents, the gate verifies that both pre- and post-event scenes are loaded and spatially co-registered before proceeding.
"""

def main():
    if not CORPUS_PATH.exists():
        print(f"Error: {CORPUS_PATH} does not exist!")
        return
    
    current_content = CORPUS_PATH.read_text(encoding="utf-8")
    print(f"Current corpus size: {len(current_content)} chars, {len(current_content.splitlines())} lines")
    
    # Check if any section is already added
    if "Masking and Binary Segmentation in SatQuery AI" in current_content:
        print("Sections already added!")
        return
        
    updated_content = current_content.rstrip() + "\n" + ADDITIONAL_SECTIONS
    CORPUS_PATH.write_text(updated_content, encoding="utf-8")
    
    new_lines = len(updated_content.splitlines())
    print(f"Successfully updated {CORPUS_PATH.name}!")
    print(f"New corpus size: {len(updated_content)} chars, {new_lines} lines")

if __name__ == "__main__":
    main()
