"""Spectral index computation. Spec section 10.3.

Deterministic arithmetic on pixels. No model touches these numbers.
"""

from __future__ import annotations

import numpy as np

from ..core.bandstack import BandStack
from ..schemas import ToolResult

EPS = 1e-10

# role list, function, human-readable formula
INDEX_DEFS = {
    "ndvi":  (["NIR", "RED"],          lambda n, r: (n - r) / (n + r + EPS)),
    "ndwi":  (["GREEN", "NIR"],        lambda g, n: (g - n) / (g + n + EPS)),
    "mndwi": (["GREEN", "SWIR1"],      lambda g, s: (g - s) / (g + s + EPS)),
    "ndbi":  (["SWIR1", "NIR"],        lambda s, n: (s - n) / (s + n + EPS)),
    "nbr":   (["NIR", "SWIR2"],        lambda n, s: (n - s) / (n + s + EPS)),
    "savi":  (["NIR", "RED"],          lambda n, r: 1.5 * (n - r) / (n + r + 0.5)),
    "evi":   (["NIR", "RED", "BLUE"],
              lambda n, r, b: 2.5 * (n - r) / (n + 6 * r - 7.5 * b + 1 + EPS)),
    "vari":  (["GREEN", "RED", "BLUE"], lambda g, r, b: (g - r) / (g + r - b + EPS)),
}

INDEX_FORMULAE_TEXT = {
    "ndvi":  "(NIR - RED) / (NIR + RED)",
    "ndwi":  "(GREEN - NIR) / (GREEN + NIR)",
    "mndwi": "(GREEN - SWIR1) / (GREEN + SWIR1)",
    "ndbi":  "(SWIR1 - NIR) / (SWIR1 + NIR)",
    "nbr":   "(NIR - SWIR2) / (NIR + SWIR2)",
    "savi":  "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
    "evi":   "2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)",
    "vari":  "(GREEN - RED) / (GREEN + RED - BLUE)",
}

# Which index to prefer for a given target, best first. The planner consults this
# rather than hardcoding an index per intent, so a scene missing SWIR1 still gets
# a correct (if degraded) water index instead of an abstention.
INDEX_FOR_TARGET = {
    "water":   ["mndwi", "ndwi"],
    "vegetation": ["ndvi", "savi", "vari"],
    "builtup": ["ndbi"],
    "burn":    ["nbr"],
}


def compute_index(bs: BandStack, session, index: str) -> ToolResult:
    index = index.lower()
    if index not in INDEX_DEFS:
        return ToolResult(ok=False, caveats=[f"unknown index {index!r}"],
                          provenance={"tool": "compute_index", "failed": "unknown_index"})

    roles, fn = INDEX_DEFS[index]
    if not bs.has(*roles):
        missing = [r for r in roles if r not in bs.roles]
        return ToolResult(
            ok=False,
            caveats=[f"{index.upper()} requires {roles}; this scene has "
                     f"{sorted(bs.roles)} (missing {missing})"],
            provenance={"tool": "compute_index", "index": index,
                        "failed": "missing_bands", "missing": missing},
        )

    arrs = [bs.band(r).astype(np.float64) for r in roles]
    with np.errstate(divide="ignore", invalid="ignore"):
        out = fn(*arrs).astype(np.float32)
    out[bs.nodata_mask] = np.nan

    caveats = []
    if not bs.scaled:
        caveats.append(
            "Source radiometry is a relative stretch, not calibrated reflectance. "
            "Index values are internally consistent but not comparable to published "
            "absolute thresholds; Otsu thresholding is used instead."
        )

    handle = session.store_array(f"{index}_raster", out)
    valid = out[np.isfinite(out)]
    if valid.size == 0:
        return ToolResult(ok=False, caveats=["no valid pixels"],
                          provenance={"tool": "compute_index", "index": index,
                                      "failed": "no_valid_pixels"})

    return ToolResult(
        ok=True,
        value={"mean": round(float(valid.mean()), 4),
               "std": round(float(valid.std()), 4),
               "p10": round(float(np.percentile(valid, 10)), 4),
               "p90": round(float(np.percentile(valid, 90)), 4)},
        unit="index",
        mask_handle=handle,
        caveats=caveats,
        provenance={
            "tool": "compute_index",
            "index": index,
            "formula": INDEX_FORMULAE_TEXT[index],
            "bands_used": {r: bs.roles.index(r) for r in roles},
            "radiometry": "calibrated" if bs.scaled else "stretched",
            "valid_pixels": int(valid.size),
            "nodata_pixels": int(bs.nodata_mask.sum()),
            "scene_id": bs.scene_id,
        },
    )


def _demo() -> None:
    """Runnable check: index values must match hand arithmetic exactly."""
    import pathlib
    from ..core.ingest import Session, load_geotiff

    root = pathlib.Path(__file__).resolve().parents[2]
    s = Session()
    bs = load_geotiff(root / "data/demo/bihar_post_flood.tif")

    # Hand-check NDVI at one pixel against the formula.
    r = compute_index(bs, s, "ndvi")
    assert r.ok
    arr = s.get_array(r.mask_handle)
    n, rd = float(bs.band("NIR")[0, 0]), float(bs.band("RED")[0, 0])
    assert abs(float(arr[0, 0]) - (n - rd) / (n + rd)) < 1e-6

    # Vegetation must be positive NDVI, water negative -- if this flips, the
    # band roles are wrong somewhere upstream.
    assert r.value["p90"] > 0.5, r.value
    assert r.value["p10"] < 0.0, r.value

    # Missing band is a hard failure, never a substitution.
    bad = compute_index(bs, s, "nbr")           # needs SWIR2, fixtures have SWIR1
    assert not bad.ok and bad.provenance["failed"] == "missing_bands"

    assert not compute_index(bs, s, "bogus").ok

    print(f"spectral: ok  ndvi={r.value}")


if __name__ == "__main__":
    _demo()
