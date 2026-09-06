"""Tool registry. Spec section 10.

One dict, name -> callable. The Tier A/B planner emits tool names as JSON; the
Tier C planner emits the same names from rules. Same registry, same kernel, so
the numbers cannot differ between tiers.
"""

from __future__ import annotations

from .measurement import measure_area, threshold_sensitivity, zonal_stats
from .segmentation import mask_difference, threshold_mask
from .spectral import compute_index

TOOLS = {
    "compute_index": compute_index,
    "threshold_mask": threshold_mask,
    "mask_difference": mask_difference,
    "measure_area": measure_area,
    "threshold_sensitivity": threshold_sensitivity,
    "zonal_stats": zonal_stats,
}

# Descriptions go into the planner prompt at Tier A/B.
TOOL_CATALOGUE = {
    "compute_index": "Compute a spectral index raster. params: index "
                     "(ndvi|ndwi|mndwi|ndbi|nbr|savi|evi|vari)",
    "threshold_mask": "Threshold an index raster into a boolean mask. params: "
                      "raster_handle, mode (otsu|absolute|percentile), value, "
                      "direction (gt|lt), min_area_px",
    "mask_difference": "Combine two masks. params: handle_a, handle_b, "
                       "op (sub|union|intersect)",
    "measure_area": "Convert a mask to real-world area. params: mask_handle, label",
    "threshold_sensitivity": "Sweep the threshold and report the area range. "
                             "params: raster_handle, threshold, direction",
    "zonal_stats": "Summary statistics of a raster inside a mask. params: "
                   "raster_handle, mask_handle, label",
}
