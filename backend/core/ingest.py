"""GeoTIFF -> BandStack. Spec section 7 (L0 Ingest / Sensor Normaliser).

Band roles are read from the file's own band descriptions where present, and only
fall back to a declared sensor ordering when the file names nothing. Guessing an
ordering silently is how you end up computing NDVI from the wrong two bands.
"""

from __future__ import annotations

import pathlib

import numpy as np
import rasterio

from .bandstack import BAND_ORDERINGS, BandStack, normalise_role


class IngestError(RuntimeError):
    pass


def load_geotiff(path: str | pathlib.Path, sensor: str | None = None,
                 scale_factor: float | None = None) -> BandStack:
    """Read a GeoTIFF into a BandStack.

    sensor: key into BAND_ORDERINGS, used ONLY if the file does not name its bands.
    scale_factor: divide by this to reach reflectance 0..1. Read from the
        SATQUERY_SCALE tag when absent; inferred for integer rasters as a last
        resort, which marks the stack unscaled so downstream code knows to prefer
        Otsu over absolute thresholds.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise IngestError(f"scene not found: {path}")

    with rasterio.open(path) as src:
        raw = src.read()
        tags = src.tags()
        descriptions = list(src.descriptions or [])
        crs = str(src.crs) if src.crs else None
        transform = tuple(src.transform)[:6] if src.transform else None
        nodata = src.nodata
        dtype = src.dtypes[0]

    # --- roles ---------------------------------------------------------
    roles: list[str] = []
    tagged = tags.get("SATQUERY_BANDS")
    source = None
    if tagged:
        roles = [normalise_role(b) for b in tagged.split(",")]
        source = "SATQUERY_BANDS tag"
    elif any(descriptions):
        roles = [normalise_role(d) for d in descriptions]
        source = "GeoTIFF band descriptions"
    if not roles or any(r is None for r in roles):
        if sensor:
            order = BAND_ORDERINGS.get(sensor)
            if not order:
                raise IngestError(f"unknown sensor {sensor!r}")
            if len(order) != raw.shape[0]:
                raise IngestError(
                    f"sensor {sensor!r} declares {len(order)} bands, "
                    f"file has {raw.shape[0]}")
            roles, source = list(order), f"BAND_ORDERINGS[{sensor!r}]"
        else:
            raise IngestError(
                f"{path.name}: band roles are not named in the file and no "
                f"sensor ordering was given. Refusing to guess -- a wrong "
                f"ordering yields plausible wrong numbers.")

    # --- radiometry ----------------------------------------------------
    if scale_factor is None and "SATQUERY_SCALE" in tags:
        scale_factor = float(tags["SATQUERY_SCALE"])

    arr = raw.astype(np.float32)
    if scale_factor:
        arr /= float(scale_factor)
        scaled = True
    elif dtype.startswith("float") and float(np.nanmax(arr)) <= 1.5:
        scaled = True                       # already reflectance
    else:
        # Unknown radiometry: normalise per-scene so indices are computable, but
        # flag it so thresholding uses Otsu rather than literature constants.
        hi = float(np.nanpercentile(arr, 99.9)) or 1.0
        arr = arr / hi
        scaled = False

    # --- nodata --------------------------------------------------------
    if nodata is not None:
        nodata_mask = np.all(raw == nodata, axis=0)
    else:
        nodata_mask = np.zeros(arr.shape[1:], bool)
    nodata_mask |= ~np.all(np.isfinite(arr), axis=0)

    pixel_area = None
    if transform:
        pixel_area = abs(transform[0] * transform[4])

    modality = "sar" if any(r in ("VV", "VH", "HH", "HV") for r in roles) else "optical"

    return BandStack(
        data=arr, roles=roles, crs=crs, transform=transform,
        pixel_area_m2=pixel_area, nodata_mask=nodata_mask, scaled=scaled,
        modality=modality, scene_id=path.stem,
        meta={"path": str(path), "role_source": source, "dtype": dtype,
              "scale_factor": scale_factor, "tags": tags},
    )


class Session:
    """Holds intermediate rasters between plan steps.

    In-memory dict. Handles are stable strings that appear in provenance, so an
    evidence record can name the exact array a number came from.
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._arrays: dict[str, np.ndarray] = {}
        self._n = 0

    def store_array(self, name: str, arr: np.ndarray) -> str:
        self._n += 1
        handle = f"{name}#{self._n}"
        self._arrays[handle] = arr
        return handle

    def get_array(self, handle: str) -> np.ndarray:
        if handle not in self._arrays:
            raise KeyError(f"no array {handle!r}; have {list(self._arrays)}")
        return self._arrays[handle]

    def handles(self) -> list[str]:
        return list(self._arrays)


def _demo() -> None:
    """Runnable check against the real fixtures."""
    root = pathlib.Path(__file__).resolve().parents[2]
    bs = load_geotiff(root / "data/demo/bihar_post_flood.tif")

    assert bs.roles == ["GREEN", "RED", "NIR", "SWIR1"], bs.roles
    assert bs.shape == (1024, 1024)
    assert bs.crs == "EPSG:32645"
    assert bs.pixel_area_m2 == 100.0, bs.pixel_area_m2
    assert bs.scaled is True                       # SATQUERY_SCALE tag was found
    assert bs.modality == "optical"
    assert 0.0 <= float(bs.data.min()) and float(bs.data.max()) <= 1.5

    # Reflectance must land in a physical range, else the scale factor was wrong.
    nir_veg = float(np.median(bs.band("NIR")))
    assert 0.05 < nir_veg < 0.6, nir_veg

    s = Session()
    h = s.store_array("ndvi_raster", np.zeros((4, 4), np.float32))
    assert s.get_array(h).shape == (4, 4)
    try:
        s.get_array("nope")
        raise AssertionError("unknown handle must raise")
    except KeyError:
        pass

    print(f"ingest: ok  {bs.describe()}")


if __name__ == "__main__":
    _demo()
