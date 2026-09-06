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
