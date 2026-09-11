# SatQuery knowledge base

Reference notes on the spectral indices, thresholds and instruments this system
uses. Every chunk is delimited by a `## ` heading and carries a `source:` line.

These are working notes compiled for this project, not verbatim extracts from the
cited documents. The citation names where the underlying method is defined so a
reader can check it; it is not a claim to quote that document. Nothing here is
used to produce a number -- the kernel measures, and retrieval only supplies the
words around the measurement.

---

## NDWI — Normalised Difference Water Index
source: McFeeters 1996, International Journal of Remote Sensing 17(7)
tags: water, index, ndwi

NDWI = (GREEN - NIR) / (GREEN + NIR)

Water absorbs strongly in the near infrared and reflects comparatively well in
green, so open water returns positive values while vegetation and soil return
negative ones. The conventional cut is 0, but that value assumes calibrated
surface reflectance. On a relative stretch the same threshold is meaningless,
which is why this system derives the cut from the scene's own histogram instead.

Known weakness: built-up surfaces also return positive NDWI, so urban areas are
over-detected as water. MNDWI was introduced to fix exactly this.

## MNDWI — Modified Normalised Difference Water Index
source: Xu 2006, International Journal of Remote Sensing 27(14)
tags: water, index, mndwi, flood

MNDWI = (GREEN - SWIR1) / (GREEN + SWIR1)

Replaces NIR with shortwave infrared. Built-up surfaces are bright in SWIR, so
they fall to negative values and stop being confused with water. This is the
preferred water index whenever a SWIR band is available, and it is what this
system selects by default for flood and water queries on Sentinel-2 data.

For Sentinel-2 the bands are B03 (green, 10 m) and B11 (SWIR1, 20 m); B11 must be
resampled to 10 m before the ratio is formed.

## NDVI — Normalised Difference Vegetation Index
source: Rouse et al. 1974, NASA/GSFC Type III Final Report
tags: vegetation, index, ndvi, crop

NDVI = (NIR - RED) / (NIR + RED)

Healthy vegetation reflects strongly in NIR and absorbs red for photosynthesis,
so dense canopy approaches 0.8. Bare soil sits near 0.1-0.2, and water is
negative. NDVI saturates over dense canopy, which is why EVI and SAVI exist.

Interpretation depends on season and crop calendar: a low NDVI over Bihar in May
is post-harvest fallow, not crop failure. A number without its calendar is not an
answer.

## NDBI — Normalised Difference Built-up Index
source: Zha, Gao and Ni 2003, International Journal of Remote Sensing 24(3)
tags: builtup, index, ndbi, urban

NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)

Concrete and asphalt reflect more SWIR than NIR, so built-up land is positive
while vegetation is negative. Bare soil also returns positive values and is the
main confusion class, so NDBI is normally read alongside NDVI rather than alone.

## NBR — Normalised Burn Ratio
source: Key and Benson 2006, USGS FIREMON LA-1-55
tags: burn, fire, index, nbr

NBR = (NIR - SWIR2) / (NIR + SWIR2)

Fire removes canopy, dropping NIR, and exposes char and dry soil, raising SWIR2.
Burned ground therefore returns low or negative NBR. Severity is normally
assessed as dNBR, the difference between pre-fire and post-fire NBR, rather than
from a single date.

Band requirement: SWIR2 is Sentinel-2 B12, near 2190 nm. B11 (SWIR1, 1610 nm) is
not a substitute -- the burn signal lives in the longer wavelength, and swapping
bands produces a plausible but wrong severity figure. This system refuses the
query instead.

## Otsu's method
source: Otsu 1979, IEEE Transactions on Systems, Man and Cybernetics 9(1)
tags: threshold, otsu, segmentation

Chooses the threshold that maximises between-class variance, equivalently the one
that minimises within-class variance. It needs no training data and adapts to the
scene, which is what makes it appropriate when radiometry is a relative stretch
and a literature threshold has no meaning.

Failure mode: Otsu returns a threshold whether or not two classes exist. On a
single-peaked histogram it splits noise about the mean and reports a large,
confident, meaningless region. This system therefore measures the achieved
between-class separability and refuses the split when it falls below the level a
genuine two-class scene reaches.

## Sentinel-2 MSI
source: ESA Sentinel-2 User Handbook, Issue 1 Rev 2
tags: instrument, sentinel2, bands

Two satellites, 5-day revisit at the equator. 13 bands. Relevant here:

- B02 blue 490 nm, 10 m
- B03 green 560 nm, 10 m
- B04 red 665 nm, 10 m
- B08 NIR 842 nm, 10 m
- B11 SWIR1 1610 nm, 20 m
- B12 SWIR2 2190 nm, 20 m

L2A products are atmospherically corrected surface reflectance, stored as uint16
scaled by 10000. L1C is top-of-atmosphere and needs correction before indices are
compared across dates.

## Resourcesat-2 LISS-III
source: NRSC/ISRO Resourcesat-2 Data User Handbook
tags: instrument, liss3, isro, indian

Indian instrument, 23.5 m resolution, 24-day revisit. Four bands: green (520-590
nm), red (620-680 nm), NIR (770-860 nm) and SWIR (1550-1700 nm).

There is no blue band, so true-colour composites are not possible and NDWI in its
original form cannot be computed. MNDWI works, since it needs green and SWIR.
There is no second SWIR band, so NBR is unavailable and burn severity must come
from another instrument.

## Cloud occlusion and optical limits
source: ESA Sentinel-2 L2A Algorithm Theoretical Basis Document
tags: cloud, quality, monsoon, sar

Optical sensors cannot see the surface through cloud. During the Indian monsoon
this is the normal condition, not the exception, and it is the reason flood
mapping in that window depends on SAR.

Practical bands used here: below 20% cloud an answer is reported normally;
between 20% and 60% the answer is reported with reduced confidence and the cloud
fraction stated; above 60% no surface-dependent question is answered at all.
Cloud shadow is a separate problem -- it darkens the surface without hiding it,
and can be mistaken for water by any index keyed on low NIR.

## Sentinel-1 SAR for flood mapping
source: ESA Sentinel-1 User Handbook / Copernicus EMS flood mapping practice
tags: sar, flood, radar, cloud

C-band synthetic aperture radar penetrates cloud and works at night, which makes
it the instrument of record for monsoon flood extent.

Open water is smooth at C-band wavelengths, so it reflects the signal away from
the sensor and appears very dark in VV backscatter. Thresholding VV therefore
separates water from land without any optical band.

Known confusions: smooth dry surfaces such as airport runways and some sand flats
are also dark, and wind roughening the water surface raises backscatter and can
hide flooding entirely. Radar shadow in terrain produces similar dark returns.

## Flood extent measurement practice
source: Copernicus Emergency Management Service, rapid mapping methodology
tags: flood, method, practice, area

Standard sequence: acquire a pre-event reference and a post-event image, derive a
water mask for each, and difference them. Reporting only the post-event water
area overstates the flood, because permanent water bodies are counted as new
inundation.

Areas are reported as measured extent at the sensor's resolution, and the
resolution belongs with the figure. A 10 m sensor cannot resolve inundation
narrower than about 10 m, so thin flooding along embankments is systematically
missed.

## Kosi basin flood context
source: Central Water Commission and Bihar Water Resources Department reporting
tags: kosi, bihar, flood, context, supaul

The Kosi drains Nepal's eastern hills into north Bihar. It carries an exceptional
sediment load, and its bed aggrades, so the channel has shifted roughly 120 km
west over the last two centuries. Embankments confine it, and breaches rather
than gradual overtopping cause the most severe events -- the 2008 Kusaha breach
inundated districts including Supaul that lay outside the expected flood path.

Consequence for mapping: the pre-event channel is a poor predictor of where water
will go. Measured extent from imagery is the evidence, not a hydraulic model
prior.

## Pixel counting and area
source: standard photogrammetric practice
tags: area, method, pixels, projection

Area is the count of qualifying pixels multiplied by the ground area of one
pixel, which comes from the affine transform of the raster. At 10 m resolution
one pixel is 100 m squared, so 10000 pixels is one hectare.

This requires an equal-area or local projection. Computing area from degrees in
EPSG:4326 is wrong, because a degree of longitude shortens with latitude. UTM is
appropriate for scenes of this size, which is why these scenes are held in
EPSG:32645.

## SAVI — Soil Adjusted Vegetation Index
source: Huete 1988, Remote Sensing of Environment 25(3)
tags: vegetation, index, savi, soil, crop

SAVI = ((NIR - RED) / (NIR + RED + L)) * (1 + L)

In areas with sparse vegetation, the soil background reflects significantly in both red and NIR, which artificially lowers NDVI values. SAVI introduces a soil brightness correction factor, L, to minimize soil background influences. For most generic purposes, L is set to 0.5. It is superior to NDVI in semi-arid regions or early crop growth stages before canopy closure.

## EVI — Enhanced Vegetation Index
source: Huete et al. 2002, Remote Sensing of Environment 83(1-2)
tags: vegetation, index, evi, crop, canopy

EVI = 2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))

EVI was developed to optimize the vegetation signal with improved sensitivity in high biomass regions where NDVI typically saturates. It uses the blue band to correct for aerosol scattering and reduces soil background influence. EVI is preferred over NDVI over dense forests, such as the Western Ghats or mature agricultural canopies, as it continues to respond to structural variations after NDVI has maxed out at ~0.8.

## Landsat 8/9 OLI
source: USGS Landsat 8 Data Users Handbook
tags: instrument, landsat, optical

The Operational Land Imager (OLI) on Landsat 8 and 9 provides 30 m resolution optical and SWIR imagery, with a 16-day revisit time per satellite (8-day combined). Relevant bands:
- Band 2 (Blue): 480 nm
- Band 3 (Green): 560 nm
- Band 4 (Red): 655 nm
- Band 5 (NIR): 865 nm
- Band 6 (SWIR1): 1610 nm
- Band 7 (SWIR2): 2200 nm

While its resolution (30 m) is lower than Sentinel-2 (10-20 m), Landsat has a much longer consistent historical archive going back decades, making it essential for long-term historical context.

## Brahmaputra basin flood context
source: Assam State Disaster Management Authority (ASDMA) flood reports
tags: brahmaputra, assam, flood, context

The Brahmaputra river flows through Assam, constrained by the Himalayas to the north and the Meghalaya plateau to the south. During the southwest monsoon (June-September), heavy rainfall causes recurrent, extensive flooding. Unlike the Kosi's sudden breaches, Brahmaputra flooding is characterized by widespread inundation over vast floodplains, channel braiding, and significant bank erosion. 

Cloud cover during the Assam monsoon is near-constant, meaning SAR (Sentinel-1) is almost always required for operative flood mapping in this region during the peak season.

## Sentinel-2 Scene Classification Layer (SCL)
source: ESA Sentinel-2 L2A Data Quality Report
tags: cloud, mask, scl, methodology

Sentinel-2 L2A products include a Scene Classification Layer (SCL) generated by the Sen2Cor algorithm. It is a 20m resolution categorical mask that flags pixels as:
- 4: Vegetation
- 5: Not-vegetated
- 6: Water
- 8: Cloud (medium probability)
- 9: Cloud (high probability)
- 3: Cloud shadows

This system uses the SCL to mask out clouds and cloud shadows before computing indices. If a pixel is flagged as cloud (8, 9) or shadow (3), it is excluded from area calculations for surface features like flooding or vegetation. Measuring flooded area without applying this mask first leads to severe false positives.

## NDSI — Normalised Difference Snow Index
source: Dozier 1989, Remote Sensing of Environment 28
tags: snow, ice, index, ndsi

NDSI = (GREEN - SWIR1) / (GREEN + SWIR1)

Snow is highly reflective in the visible wavelengths (green) but strongly absorbs shortwave infrared (SWIR). This distinct spectral signature makes NDSI very effective at separating snow from clouds, as clouds remain highly reflective in SWIR. An NDSI value greater than 0.4 is typically used to classify a pixel as snow-covered, although fractional snow cover can be estimated for lower values.

## Burn Severity Classification (dNBR)
source: UN-SPIDER Burn Severity mapping practice
tags: burn, fire, severity, dnbr, threshold

While NBR identifies burned areas, assessing the actual severity of the fire requires the difference between pre-fire and post-fire imagery (dNBR = pre_NBR - post_NBR). Standard ecological thresholds are:
- Unburned: < 0.10
- Low severity: 0.10 to 0.27
- Moderate-low severity: 0.27 to 0.44
- Moderate-high severity: 0.44 to 0.66
- High severity: > 0.66

These thresholds are empirical and can vary by biome, but they provide the standard categorical mapping for post-fire recovery planning.

## Atmospheric Correction: L1C vs L2A
source: ESA Sentinel-2 Level-2A Product Definition
tags: processing, atmospheric, reflectance, l1c, l2a

Level-1C (L1C) data provides Top-Of-Atmosphere (TOA) reflectance. It includes scattering and absorption effects from atmospheric gases and aerosols. Level-2A (L2A) data provides Bottom-Of-Atmosphere (BOA) or Surface Reflectance, having corrected for these atmospheric effects. 

Computing spectral indices on L1C data often yields lower absolute values (e.g., lower NDVI) due to atmospheric scattering in the visible bands. For time-series analysis or accurate thresholding, L2A surface reflectance is strictly required. This system only processes L2A products to ensure radiometry is physically meaningful.

## Tasseled Cap Transformation (TCT)
source: Kauth and Thomas 1976, LARS Symposia
tags: transformation, tasseled, brightness, greenness, wetness

The Tasseled Cap Transformation converts raw spectral bands into three orthogonal components that map directly to physical scene characteristics:
1. Brightness: Represents overall reflectance, heavily influenced by bare soil and urban surfaces.
2. Greenness: Contrasts visible and near-infrared bands, strongly correlating with photosynthetically active vegetation.
3. Wetness: Contrasts visible/NIR against SWIR, highly sensitive to soil and canopy moisture.

Unlike simple ratios (like NDVI), TCT uses a weighted linear combination of all available bands, making it highly robust for comprehensive land cover classification.

## MODIS and VIIRS for Large-Scale Monitoring
source: NASA Earthdata Sensor Overviews
tags: instrument, modis, viirs, coarse, global

While Sentinel-2 and Landsat provide high-resolution (10-30m) detail, their revisit times (5-8 days) can be too slow for rapidly evolving disasters. Moderate Resolution Imaging Spectroradiometer (MODIS) and Visible Infrared Imaging Radiometer Suite (VIIRS) provide very coarse resolution (250m to 1km) but offer daily or sub-daily global coverage.

They are the primary instruments for active fire detection (using thermal anomalies) and continental-scale drought monitoring. In this system, any query asking for "daily" updates or "continental" scale mapping will likely exceed the bounds of high-resolution sensors and should theoretically fall back to MODIS/VIIRS data if supported.

## NDMI â€” Normalised Difference Moisture Index
source: Gao 1996, Remote Sensing of Environment 58(3)
tags: moisture, index, ndmi, drought, vegetation

NDMI = (NIR - SWIR1) / (NIR + SWIR1)

NDMI is sensitive to moisture content in vegetation canopy. Healthy, hydrated vegetation has high NIR reflectance and low SWIR reflectance, yielding positive NDMI. Stressed or dry vegetation shows reduced NIR and increased SWIR, pulling NDMI toward zero or negative. It is widely used for drought monitoring and agricultural water stress assessment. Unlike NDVI, which saturates early, NDMI continues to respond to moisture changes in a fully green canopy.

For Sentinel-2 the relevant bands are B08 (NIR, 842 nm, 10 m) and B11 (SWIR1, 1610 nm, 20 m). Like MNDWI, B11 must be resampled to 10 m before computing the ratio.

## AWEI â€” Automated Water Extraction Index
source: Feyisa et al. 2014, Remote Sensing of Environment 140
tags: water, index, awei, shadow, urban

AWEI has two forms:
AWEInsh = 4 * (GREEN - SWIR1) - (0.25 * NIR + 2.75 * SWIR2)
AWEIsh  = BLUE + 2.5 * GREEN - 1.5 * (NIR + SWIR1) - 0.25 * SWIR2

AWEInsh is designed for areas without shadow. AWEIsh adds the blue band to suppress false detections from terrain and building shadows that fool simpler water indices. AWEI outperforms NDWI and MNDWI in complex urban-rural mixes and mountainous terrain where shadows and built-up surfaces confuse single-ratio indices. It requires five spectral bands (blue, green, NIR, SWIR1, SWIR2), so it cannot be computed on sensors with fewer bands such as Resourcesat-2 LISS-III.

## MSAVI â€” Modified Soil Adjusted Vegetation Index
source: Qi et al. 1994, Remote Sensing of Environment 48(2)
tags: vegetation, index, msavi, soil

MSAVI = (2 * NIR + 1 - sqrt((2 * NIR + 1)^2 - 8 * (NIR - RED))) / 2

Unlike SAVI, which requires the user to choose a soil brightness correction factor L, MSAVI computes L adaptively from the spectral data itself. This makes it self-correcting across varying soil backgrounds without user intervention. It is particularly useful for mapping sparse vegetation in arid and semi-arid landscapes such as Rajasthan or the Deccan Plateau where soil reflectance dominates the signal and NDVI underestimates the actual vegetation cover.

## GNDVI â€” Green Normalised Difference Vegetation Index
source: Gitelson et al. 1996, Journal of Plant Physiology 148
tags: vegetation, index, gndvi, chlorophyll

GNDVI = (NIR - GREEN) / (NIR + GREEN)

GNDVI substitutes the green band for the red band used in NDVI. Green reflectance is more sensitive to chlorophyll concentration variations than red reflectance, especially at moderate to high chlorophyll levels where red absorption is already near-total. This makes GNDVI more sensitive to chlorophyll content in mature crops and dense canopies. It is often used for precision agriculture applications, including variable-rate nitrogen fertilization.

## BSI â€” Bare Soil Index
source: Rikimaru et al. 2002, Index of Bare Soil
tags: soil, bare, index, bsi, urban, land

BSI = ((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))

Bare soil reflects strongly in SWIR and red while absorbing in NIR and blue. BSI exploits this four-band contrast to isolate exposed soil from vegetation and water. Positive values indicate bare ground, fallow fields, or recently cleared land. Negative values correspond to vegetated or water-covered surfaces. It is useful for monitoring land degradation, desertification, post-harvest field conditions, and construction activity.

## NDRE â€” Normalised Difference Red Edge Index
source: Gitelson and Merzlyak 1994, Journal of Plant Physiology 143
tags: vegetation, index, ndre, rededge, crop, precision

NDRE = (NIR - RED_EDGE) / (NIR + RED_EDGE)

The red edge lies between 700 nm and 740 nm, where plant reflectance transitions sharply from low (red absorption) to high (NIR reflectance). NDRE uses this transition zone instead of the broader red band, making it far more sensitive to subtle variations in chlorophyll content and canopy nitrogen status. Sentinel-2 provides three red edge bands (B05 at 705 nm, B06 at 740 nm, B07 at 783 nm), giving it a significant advantage over Landsat for precision agriculture.

NDRE does not saturate as readily as NDVI over dense canopy, making it the preferred index for mid-season and late-season crop health assessment. It requires a red edge band, which Landsat and LISS-III do not carry.

## LAI â€” Leaf Area Index estimation
source: Baret and Guyot 1991, Remote Sensing of Environment 37(3)
tags: lai, vegetation, canopy, biophysical, crop

Leaf Area Index is the total one-sided area of leaf tissue per unit ground surface area, expressed in mÂ²/mÂ². It is a key biophysical variable for crop growth modelling, evapotranspiration estimation, and carbon flux calculations. LAI cannot be directly measured by satellite but is inferred from spectral indices.

Empirical relationships link NDVI, EVI, or red edge indices to LAI, but these saturate at LAI values of 3-4 because optical reflectance changes negligibly once the canopy closes. SAR backscatter and lidar penetrate deeper into the canopy, providing complementary LAI information at high biomass levels. For this system, LAI is interpretive context, not a kernel measurement.

## NMDI â€” Normalised Multiband Drought Index
source: Wang and Qu 2007, Geophysical Research Letters 34(20)
tags: drought, moisture, index, nmdi, soil

NMDI = (NIR - (SWIR1 - SWIR2)) / (NIR + (SWIR1 - SWIR2))

NMDI uses the difference between two SWIR bands to separate soil moisture from vegetation water content. When soil dries, SWIR1 and SWIR2 both increase, but their difference changes predictably. This dual-SWIR approach gives NMDI an advantage over single-band moisture indices for mixed land cover. It requires both SWIR1 and SWIR2 bands, meaning it works on Sentinel-2 (B11 + B12) and Landsat (Band 6 + Band 7) but not on Resourcesat-2 LISS-III which carries only one SWIR band.

## RISAT â€” Radar Imaging Satellite (ISRO)
source: ISRO RISAT Data User Handbook
tags: instrument, risat, sar, isro, indian, radar

RISAT-1 was India's first dedicated SAR satellite, operating in C-band (5.35 GHz) with multiple polarisation modes (HH, HV, VV, VH). It provided 3 m to 50 m resolution imagery depending on the imaging mode. RISAT-2B and its follow-ons carry X-band SAR with finer resolution.

For flood mapping in India, RISAT complements Sentinel-1 by providing additional SAR revisits during the monsoon when optical data is cloud-blocked. RISAT SAR data requires different backscatter calibration than Sentinel-1 C-band because antenna patterns and noise floors differ. Cross-sensor flood maps should not directly compare raw backscatter values without radiometric normalisation.

## Cartosat Series (ISRO)
source: NRSC/ISRO Cartosat Data User Handbook
tags: instrument, cartosat, isro, indian, dem, stereo

Cartosat-1 carried two panchromatic cameras tilted fore and aft to generate stereo imagery for Digital Elevation Model (DEM) extraction at 2.5 m resolution. Cartosat-2 and later variants improved ground resolution to sub-metre panchromatic.

DEMs derived from Cartosat stereo pairs are essential for flood modelling â€” water flows downhill, and the accuracy of inundation extent prediction depends directly on terrain elevation accuracy. The CartoDEM product provides 10 m posting DEM for all of India. However, DEMs are static terrain products, not dynamic flood measurements; this system uses them as context for drainage direction, not as a substitute for measured flood extent.

## Resourcesat-2A AWiFS
source: NRSC/ISRO Resourcesat-2A Data User Handbook
tags: instrument, awifs, isro, indian, wide

The Advanced Wide Field Sensor (AWiFS) on Resourcesat-2A provides 56 m resolution across a 740 km swath with a 5-day revisit. It carries four bands: green, red, NIR, and SWIR. The wide swath makes it suitable for national-scale crop monitoring, drought assessment, and large-area land use mapping where the 23.5 m resolution of LISS-III is not required.

AWiFS data is routinely used by the Mahalanobis National Crop Forecast Centre (MNCFC) for district-level crop acreage estimation under the FASAL programme. The coarser resolution means sub-field variability is lost, but state-level and district-level statistics benefit from the frequent repeat coverage.

## Oceansat and Scatwind
source: ISRO/SAC Oceansat-2 Handbook
tags: instrument, oceansat, isro, ocean, wind, chlorophyll

Oceansat-2 carried the Ocean Colour Monitor (OCM) for ocean chlorophyll mapping and Ku-band Scatterometer (ScatSAT) for sea-surface wind measurement. These instruments operate at much coarser resolution than land-imaging sensors (360 m for OCM, 25 km for ScatSAT).

For this system, Oceansat data is not directly relevant to land surface queries. However, ocean colour data can provide context for coastal water quality, sediment plume extent from river discharge during floods, and algal bloom monitoring. A flood query for a coastal district like Kendrapara (Odisha) could benefit from knowing the sediment plume extent into the Bay of Bengal.

## Mixed Pixels and Sub-Pixel Analysis
source: Fisher 1997, International Journal of Remote Sensing 18(3)
tags: pixel, resolution, subpixel, mixed, accuracy

A pixel records the average reflectance of all materials within its ground footprint. At 10 m resolution, a pixel covering a canal bank contains both water and soil, and its index value falls between the pure water and pure soil values. This is the mixed pixel problem and is the fundamental resolution limit of any raster-based analysis.

Consequences for measurement: a flood boundary never aligns with pixel edges, so pixel counting systematically over- or under-estimates the true area. At 10 m resolution the error per boundary pixel is up to 100 mÂ², which accumulates along the entire perimeter. Finer resolution reduces the mixed pixel fraction but increases data volume and processing time quadratically.

Sub-pixel analysis attempts to decompose each pixel into fractional abundances of its constituent materials (spectral unmixing), but requires accurate endmember spectra and introduces its own error budget. This system reports whole-pixel counts and acknowledges the resolution-dependent error.

## Spectral Resolution and Band Width
source: Schott 2007, Remote Sensing: The Image Chain Approach, Oxford University Press
tags: spectral, resolution, bands, hyperspectral, multispectral

Spectral resolution refers to the width and number of wavelength bands a sensor records. Multispectral sensors like Sentinel-2 (13 bands) sample broad portions of the spectrum. Hyperspectral sensors like PRISMA (240 bands) or EnMAP (230 bands) sample narrow contiguous bands across the full visible-to-SWIR range.

Narrow bands can distinguish materials that look identical in broad bands. For example, two minerals with absorption features at 2100 nm and 2200 nm appear identical in Sentinel-2 B12 (which spans 2100-2280 nm as a single band) but are separable in hyperspectral data. For vegetation, narrow red edge bands improve chlorophyll estimation beyond what NDVI achieves.

This system operates on multispectral imagery. Queries asking for mineral identification, species-level vegetation mapping, or other tasks requiring fine spectral discrimination may exceed the capability of the loaded sensor data.

## Radiometric Resolution and Bit Depth
source: Lillesand, Kiefer and Chipman 2015, Remote Sensing and Image Interpretation, 7th Edition, Wiley
tags: radiometric, resolution, bitdepth, dynamic

Radiometric resolution is the number of discrete brightness levels a sensor can distinguish, determined by its bit depth. Sentinel-2 records 12-bit data (4096 levels), while older sensors like Landsat 5 TM recorded 8-bit data (256 levels).

Higher bit depth preserves subtle reflectance differences that are critical for accurate index computation. An 8-bit sensor compresses the reflectance range into 256 steps, so small but meaningful differences in NIR reflectance between healthy and stressed vegetation may fall into the same digital number. Sentinel-2's 12-bit data preserves these differences. When this system computes indices, the precision of the underlying digital numbers determines the noise floor of the result.

## Pan-Sharpening
source: Vivone et al. 2015, IEEE Geoscience and Remote Sensing Magazine 3(3)
tags: pansharpening, fusion, resolution, spatial

Pan-sharpening fuses a high-resolution panchromatic band with lower-resolution multispectral bands to produce a multispectral image at the panchromatic resolution. Sentinel-2 does not carry a panchromatic band, so pan-sharpening does not apply to it. Landsat 8 carries a 15 m panchromatic band (Band 8) that can sharpen the 30 m multispectral bands. Cartosat provides 2.5 m or sub-metre panchromatic data that can be fused with LISS-III 23.5 m multispectral data.

Pan-sharpening changes the pixel values of the multispectral bands, which means spectral indices computed on pan-sharpened data may differ from those computed on the original multispectral data. This spectral distortion varies by algorithm, and indices computed on pan-sharpened imagery should note the pre-processing in provenance.

## Co-registration and Geometric Accuracy
source: ESA Sentinel-2 Geometric Validation Report
tags: registration, geometric, accuracy, alignment, change

When comparing two images from different dates (for change detection, dNBR, or flood differencing), the images must be geometrically aligned so that the same pixel in both images covers the same ground location. Misregistration by even one pixel (10 m for Sentinel-2) introduces false changes along every high-contrast edge in the scene.

Sentinel-2 L2A products are orthorectified to sub-pixel accuracy using ground control points and the Copernicus DEM. LISS-III products from NRSC require separate orthorectification. Cross-sensor comparisons (e.g., comparing a Sentinel-2 flood mask with a LISS-III pre-event mask) require explicit co-registration, and the residual error must be reported.

## Change Detection Methodology
source: Singh 1989, International Journal of Remote Sensing 10(6)
tags: change, detection, temporal, method, flood, urban

Change detection identifies differences between images acquired at different times. The primary methods relevant to this system are:

Image differencing: Subtract one index image from another (e.g., post-NDWI minus pre-NDWI). Simple and effective when both images are radiometrically comparable.

Post-classification comparison: Classify each image independently, then compare the class maps. Errors in either classification propagate, so accuracy depends on both classifications being correct.

Threshold-based masking: Apply a threshold to each date independently and difference the binary masks. This is what this system uses for flood change (pre-water minus post-water).

All methods assume comparable illumination, atmospheric conditions, and phenological state. Comparing a monsoon image with a winter image introduces seasonal differences that masquerade as real change. This system requires pre-event and post-event imagery within a narrow temporal window.

## Indian Crop Calendar â€” Kharif, Rabi, Zaid
source: Directorate of Economics and Statistics, Ministry of Agriculture, Government of India
tags: crop, calendar, kharif, rabi, india, agriculture, season

India's agricultural year divides into three seasons:

Kharif (monsoon, June-October): Rice, maize, soybean, cotton, sugarcane. Sowing coincides with the southwest monsoon onset. Peak NDVI occurs in August-September. Cloud cover during this season is heavy, limiting optical imagery availability.

Rabi (winter, October-March): Wheat, mustard, gram, barley. Sowing begins after the monsoon withdrawal. Cloud-free conditions make this the best season for optical remote sensing of crops. Peak NDVI occurs in January-February.

Zaid (summer, March-June): Short-duration crops like watermelon, cucumber, muskmelon. Limited irrigation-dependent cultivation. NDVI is generally low as most agricultural land is fallow or post-harvest.

Interpreting NDVI without knowing the crop calendar leads to misdiagnosis. Low NDVI in May over the Indo-Gangetic plain is normal post-Rabi harvest fallow, not crop failure. Conversely, low NDVI in September during peak Kharif could indicate flood damage or drought stress and warrants further investigation.

## UTM Zones for India
source: Survey of India, National Spatial Reference Frame
tags: projection, utm, coordinate, india, epsg

India spans UTM zones 42 through 47 (covering longitudes 66Â°E to 102Â°E). The major zones and their EPSG codes:
- Zone 42N (EPSG:32642): Western Rajasthan, Gujarat coast
- Zone 43N (EPSG:32643): Most of Rajasthan, Gujarat, Maharashtra west
- Zone 44N (EPSG:32644): Central India, Maharashtra, Madhya Pradesh, parts of UP
- Zone 45N (EPSG:32645): Eastern UP, Bihar, Jharkhand, West Bengal, Odisha
- Zone 46N (EPSG:32646): Northeast India, Assam, Meghalaya, Manipur
- Zone 47N (EPSG:32647): Eastern Arunachal Pradesh, Myanmar border

Using the wrong UTM zone introduces a scale factor error that grows with distance from the central meridian. For scenes within one zone, this error is negligible (less than 0.04%). Cross-zone scenes should use a local projection or be split at the zone boundary.

This system's demo scenes use EPSG:32645 (UTM Zone 45N), appropriate for the Bihar/Kosi region.

## Godavari Basin Flood Context
source: Central Water Commission, Godavari Basin Organisation
tags: godavari, flood, context, andhra, telangana, maharashtra

The Godavari is India's second-longest river, flowing 1465 km from Nashik (Maharashtra) to the Bay of Bengal through Telangana and Andhra Pradesh. Its basin receives heavy rainfall from both the southwest and northeast monsoons, creating a prolonged flood season (July-November).

The lower Godavari delta around Rajahmundry and East Godavari district is extremely flat, with elevations below 10 m. Minor changes in water level inundate vast areas. Historical floods in 1986 and 2022 demonstrated that floodwater spreads across multiple distributary channels, making single-point river gauge measurements inadequate for estimating actual inundation extent. Satellite-derived flood maps are essential here because the flat terrain and braided channels prevent simple stage-discharge relationships.

## Mahanadi Basin Flood Context
source: Central Water Commission, Mahanadi Basin Organisation
tags: mahanadi, flood, context, odisha, chhattisgarh

The Mahanadi flows through Chhattisgarh and Odisha, emptying into the Bay of Bengal near Paradip. The Hirakud Dam on the upper Mahanadi provides significant flood control, but extreme inflows during cyclonic events can exceed dam capacity, requiring emergency releases that flood downstream areas.

The Mahanadi delta is a low-lying, densely populated agricultural zone. The 2008, 2011, and 2022 floods caused widespread inundation in Cuttack and Puri districts. SAR-based flood mapping is critical here because cyclone-associated cloud cover persists for days after the rainfall peak, precisely when the flooding reaches maximum extent.

## Kerala Floods Context (2018, 2019)
source: Kerala State Disaster Management Authority post-flood reports
tags: kerala, flood, context, western, ghats, landslide

The 2018 Kerala floods were triggered by extreme rainfall over the Western Ghats, causing dam releases from 35 of 39 reservoirs, river overflow, and catastrophic landslides simultaneously. The terrain is steep with narrow valleys, so flooding was spatially fragmented rather than sheet-like. This makes flood mapping challenging because inundated areas are small, scattered, and often mixed with landslide debris.

Optical indices underperform in this terrain because of steep slopes (which create shadows), dense tropical vegetation (high NIR even when flooded), and persistent cloud cover. SAR is essential but also problematic because radar shadow and layover in mountainous terrain create dark patches indistinguishable from water. Combining ascending and descending SAR passes partially mitigates this by illuminating slopes from different angles.

## Chennai Urban Floods Context (2015)
source: NRSC rapid flood mapping reports and NDMA post-disaster review
tags: chennai, flood, urban, context, drainage

The 2015 Chennai floods resulted from extreme northeast monsoon rainfall (490 mm in 24 hours on 1-2 December). Unlike riverine floods, Chennai flooding was primarily pluvial â€” rainfall overwhelmed urban drainage and accumulated in low-lying areas. The Adyar and Cooum rivers added riverine overflow to the already saturated city.

Urban flood mapping poses unique challenges for spectral indices: built-up surfaces (concrete, asphalt) can appear spectrally similar to shallow urban floodwater when wet. MNDWI performs better than NDWI in this context because SWIR reflectance distinguishes wet concrete from standing water. However, narrow streets and alleys below the sensor resolution (10 m) are invisible, systematically underestimating urban inundation.

## Uttarakhand Disaster Context (2013)
source: Geological Survey of India and NRSC post-disaster assessment
tags: uttarakhand, kedarnath, flood, landslide, glacial, context

The June 2013 Uttarakhand disaster involved glacial lake outburst flooding (GLOF), extreme rainfall, and massive landslides centered on the Kedarnath region. Mandakini river valley was devastated by debris flows that combined water, rock, and sediment into a destructive mass that cannot be mapped as simple water.

Pre- and post-event satellite imagery (from Resourcesat-2 and Cartosat) revealed that entire sections of valley floor were buried under metres of debris, changing the landscape so fundamentally that pre-event reference images became unusable for standard change detection. In such cases, post-event-only classification (identifying debris, water, and intact land in a single image) is more reliable than differencing.

## Sundarbans Mangrove Context
source: Forest Survey of India biennial State of Forest Reports
tags: sundarbans, mangrove, coast, vegetation, context, bengal

The Sundarbans span approximately 10,000 kmÂ² across India and Bangladesh, forming the world's largest contiguous mangrove forest at the Ganga-Brahmaputra delta. Mangrove mapping requires distinguishing mangrove vegetation from other wetland vegetation and tidal water.

Mangroves are spectrally distinct from terrestrial forests: they show lower NIR reflectance due to waterlogged roots and higher moisture content. NDVI alone cannot separate mangrove from other green vegetation, but combining NDVI with NDWI or NDMI can isolate the characteristic mangrove signature (high green biomass overlying saturated soil). Temporal variability from tidal inundation means a single image captures the tide state, not the permanent land-water boundary. Multi-temporal compositing across tidal cycles is necessary for accurate mangrove extent mapping.

## Urban Heat Island and Land Surface Temperature
source: Voogt and Oke 2003, Remote Sensing of Environment 86(3)
tags: urban, heat, temperature, lst, thermal

Land Surface Temperature (LST) is derived from thermal infrared bands (8-14 micrometres), not from the visible/SWIR bands this system primarily uses. Sentinel-2 does not carry a thermal band, so LST cannot be computed from Sentinel-2 data alone. Landsat 8/9 carries a thermal band (Band 10, 100 m resolution) suitable for LST estimation.

Urban areas show elevated LST compared to surrounding rural areas due to heat absorption by concrete, asphalt, and reduced evaporative cooling from vegetation loss. This Urban Heat Island (UHI) effect can exceed 5-10 degrees Celsius. Mapping UHI requires thermal data, and queries about temperature or heat stress on Sentinel-2 imagery should be declined with a recommendation to use Landsat thermal bands.

## Spectral Signatures of Common Materials
source: USGS Spectral Library Version 7
tags: spectral, signature, material, reflectance, reference

Different materials have characteristic reflectance patterns across wavelengths that enable identification:

Water: Very low reflectance across all bands, near zero in NIR and SWIR. Deep clear water absorbs almost all incoming radiation beyond 700 nm.

Vegetation: Low red (chlorophyll absorption), high NIR (cell structure scattering), low SWIR (water absorption). The sharp transition between red and NIR is the red edge.

Bare soil: Generally increasing reflectance from visible to SWIR. Wet soil has lower reflectance than dry soil across all bands, with the greatest difference in SWIR.

Concrete and asphalt: Moderate, relatively flat reflectance across visible and NIR. Asphalt is darker than concrete. Both show moderate SWIR reflectance, which is why MNDWI separates them from water better than NDWI.

Snow and ice: Very high visible reflectance (near 1.0) but strong absorption in SWIR (near 0.0). This extreme contrast is what makes NDSI effective for snow mapping.

## Histogram Equalisation and Contrast Stretching
source: Gonzalez and Woods 2018, Digital Image Processing, 4th Edition, Pearson
tags: histogram, stretch, contrast, visualisation, display

Raw satellite imagery stored as 12-bit or 16-bit integers often appears very dark on an 8-bit display because the data occupies only a small portion of the available range. Contrast stretching remaps the data values to fill the display range.

Linear stretch maps the minimum and maximum data values to 0 and 255. Percentage clip stretch ignores the top and bottom 2% of values to avoid outliers dominating the stretch. Histogram equalisation redistributes values to achieve a uniform histogram, maximising visual contrast.

These stretches affect only the display and do not change the underlying data. However, visual interpretation of a stretched image can be misleading: two pixels that look very different on screen may differ by only a few digital numbers in the raw data. This system computes indices on the raw values, never on stretched displays, and reports the stretch parameters used for any visual output.

## Image Segmentation Beyond Otsu
source: Blaschke 2010, ISPRS Journal of Photogrammetry and Remote Sensing 65(1)
tags: segmentation, obia, watershed, kmeans, method

Otsu's method is a global threshold that splits an image into two classes. When more than two classes exist, or when the spatial context matters, alternative methods are needed:

K-means clustering: Partitions pixel values into K clusters by minimising within-cluster variance. Unlike Otsu, it handles multiple classes. However, it is non-spatial â€” two distant pixels with the same value are grouped together regardless of spatial context.

Watershed segmentation: Treats the image as a topographic surface and identifies boundaries at gradient ridges. It produces spatially coherent regions but tends to over-segment, requiring post-processing to merge similar adjacent segments.

Object-Based Image Analysis (OBIA): Groups pixels into spatially coherent objects based on spectral similarity, shape, and scale, then classifies objects rather than pixels. This approach naturally handles the mixed pixel problem along boundaries and is the state-of-the-art for high-resolution land cover mapping.

This system uses Otsu for binary class separation (water/not-water, vegetation/not-vegetation). Queries requiring multi-class segmentation (e.g., classifying land into water, vegetation, built-up, and bare soil simultaneously) would need K-means or OBIA extensions.

## Accuracy Assessment and Confusion Matrix
source: Congalton and Green 2019, Assessing the Accuracy of Remotely Sensed Data, 3rd Edition, CRC Press
tags: accuracy, validation, confusion, kappa, method

Any classified map should report its accuracy against independent reference data. The confusion matrix (or error matrix) cross-tabulates mapped classes against ground truth for a set of validation points.

Key metrics derived from the confusion matrix:
- Overall accuracy: Percentage of correctly classified points across all classes.
- Producer's accuracy (recall): For a given class, the percentage of actual instances that were correctly identified. Low producer's accuracy means the class is being missed (omission error).
- User's accuracy (precision): For a given class, the percentage of mapped instances that are actually correct. Low user's accuracy means other things are being incorrectly mapped as this class (commission error).
- Kappa coefficient: Measures agreement above what would be expected by chance. Values above 0.8 indicate strong agreement.

This system does not currently generate a formal confusion matrix because ground truth for the demo scenes is synthetic and exact. For real-world deployment on actual satellite imagery, accuracy assessment against field observations or higher-resolution reference data would be required.

## Temporal Resolution and Revisit Trade-offs
source: Cihlar 2000, International Journal of Remote Sensing 21(6-7)
tags: temporal, resolution, revisit, tradeoff, monitoring

Temporal resolution is how frequently a sensor revisits the same location. There is a fundamental trade-off between spatial resolution, swath width, and revisit time:

Sentinel-2 (10 m, 290 km swath): 5-day revisit.
Landsat 8/9 (30 m, 185 km swath): 8-day combined revisit.
MODIS (250 m, 2330 km swath): Daily global coverage.
Planet SuperDove (3 m, 32 km swath): Daily revisit (due to large constellation).

For flood monitoring, temporal resolution often matters more than spatial resolution because floodwater rises and recedes over hours to days. A 30 m image captured at peak flood is more useful than a 10 m image captured three days after recession. This is why Sentinel-1 SAR (6-day revisit, cloud-independent) is often the primary flood monitoring sensor despite having coarser resolution than Sentinel-2 optical.

## Coordinate Reference Systems and Reprojection
source: Snyder 1987, Map Projections: A Working Manual, USGS Professional Paper 1395
tags: projection, crs, reprojection, wgs84, utm, geographic

All satellite imagery is delivered in some coordinate reference system (CRS) that maps the curved Earth surface to a flat grid. The two main categories:

Geographic CRS (e.g., EPSG:4326 / WGS84): Coordinates in degrees of latitude and longitude. A degree of longitude narrows with latitude (approximately 111 km at the equator, 79 km at 45 degrees north, 0 km at the poles). Computing area by multiplying degree-based pixel dimensions gives wrong results unless a cosine correction is applied.

Projected CRS (e.g., UTM, Lambert Conformal): Coordinates in metres on a flat plane. Area computation is straightforward (pixel width multiplied by pixel height multiplied by pixel count), but distortion increases away from the projection's central meridian or standard parallels.

This system stores all scenes in UTM (EPSG:32645 for the demo). Any ingested imagery in geographic coordinates must be reprojected to UTM before area measurements are computed. The reprojection resamples pixels, which slightly alters spectral values â€” nearest-neighbour resampling preserves original values for categorical data, while bilinear or cubic convolution is used for continuous reflectance data.

## Water Quality Indicators from Remote Sensing
source: IOCCG Report Number 3, Remote Sensing of Ocean Colour in Coastal Waters
tags: water, quality, turbidity, chlorophyll, coastal

While this system focuses on water extent (presence/absence), satellite data can also indicate water quality through several proxy measurements:

Turbidity and suspended sediment: Turbid water reflects more strongly in the red and NIR bands than clear water. High suspended sediment during floods changes the spectral signature of water, potentially causing thresholding algorithms to miss highly turbid floodwater because it does not look spectrally like clear water.

Chlorophyll-a concentration: Algal blooms increase green reflectance relative to blue, detectable through the ratio of green to blue bands. Coastal eutrophication monitoring uses this principle.

These water quality indicators are not used in the current measurement pipeline, but the spectral effects of turbidity on flood detection are relevant: extremely turbid water during peak flood can show higher NIR reflectance than expected, reducing NDWI and MNDWI values and causing underestimation of flooded area. The system's adaptive thresholding (Otsu) partially compensates for this by deriving the cut from the scene's own histogram rather than assuming a fixed threshold.

## Sentinel-2 Band Combinations for Visual Interpretation
source: ESA Sentinel-2 User Handbook, Issue 1 Rev 2
tags: sentinel2, bands, composite, visualisation, interpretation

Different band combinations highlight different surface features in RGB display:

True colour (B04-B03-B02): Natural appearance. Water is dark blue-black. Vegetation is green. Urban areas are grey.

False colour infrared (B08-B04-B03): Vegetation appears bright red (high NIR). Water is very dark. Urban areas are cyan-grey. This is the standard composite for vegetation health assessment.

SWIR composite (B12-B08-B04): Burns appear bright red. Bare soil is brown. Vegetation is green. Water is dark. Used for fire scar mapping and geological applications.

Agriculture composite (B11-B08-B02): Healthy crops appear bright green. Bare fields are brown-pink. Water is dark blue. Used for crop type discrimination and growth stage assessment.

These composites are for visual interpretation only. This system computes quantitative indices from the raw band values, not from displayed composites. The band combination used for display does not affect any measurement.

## Flood Damage Assessment Beyond Extent
source: UNITAR/UNOSAT Rapid Mapping Guidelines
tags: flood, damage, assessment, impact, population

Flood extent alone does not convey impact. Damage assessment requires overlaying the flood mask with ancillary layers:

Population density: Census-derived gridded population data (e.g., WorldPop or LandScan) intersected with the flood mask estimates the number of people affected.

Land use and land cover: Knowing whether flooded pixels are agricultural, residential, or industrial changes the nature and magnitude of the damage.

Infrastructure: Roads, hospitals, schools, and power infrastructure within the flooded zone identify critical service disruptions.

Crop stage: Flooding during grain filling (September for Kharif rice) causes greater crop loss than flooding during early vegetative growth (July) when replanting is still possible.

This system currently reports extent only. Damage assessment is a downstream application that would combine the measured flood mask with these external datasets.

## Speckle Noise in SAR Imagery
source: Lee et al. 1994, IEEE Transactions on Geoscience and Remote Sensing 32(6)
tags: sar, speckle, noise, filter, radar

SAR images contain a granular noise pattern called speckle, caused by the coherent interference of radar waves scattered from multiple targets within a single resolution cell. Speckle is multiplicative (proportional to signal strength) rather than additive, and it degrades thresholding accuracy because the same surface type shows a wide spread of backscatter values.

Common speckle filters include Lee filter, Enhanced Lee, Frost, and Gamma MAP. Multi-temporal averaging (stacking multiple SAR acquisitions) reduces speckle without spatial smoothing but requires multiple dates. For flood mapping, aggressive filtering risks smoothing out narrow water channels, while insufficient filtering produces noisy water masks with many false positive and false negative pixels.

The choice of filter and its kernel size directly affects the quality of the water-land threshold. This system's SAR path, when implemented, should report the filter applied and its parameters in provenance.

## Copernicus Open Access Hub and Data Access
source: Copernicus Data Space Ecosystem documentation
tags: data, access, copernicus, download, sentinel, archive

Sentinel-1 and Sentinel-2 data are freely available through the Copernicus Data Space Ecosystem. Data is organized by sensing date, processing level, tile identifier, and orbit number. Sentinel-2 tiles follow the Military Grid Reference System (MGRS) with 100 km by 100 km granules.

For India, commonly used Sentinel-2 tiles include 44QKF (Bihar), 43QFV (Mumbai), 44PNQ (Delhi), and 45QUE (Assam). Knowing the tile identifier allows targeted download of specific geographic areas without searching through the full archive.

L2A products include the SCL cloud mask and are the standard input for this system. L1C products require atmospheric correction (e.g., through Sen2Cor processor) before use.


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
