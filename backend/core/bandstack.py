"""BandStack: the canonical in-memory raster. Spec section 7.

Every sensor normalises to this shape, so nothing downstream knows or cares
whether the pixels came from Sentinel-2, LISS-III or a synthetic fixture.

The single most important rule in this file:

    band(role) raises BandUnavailable. It NEVER substitutes another band.

Silently swapping RED for NIR would produce a number that looks fine and is
wrong, which is exactly the failure mode this project exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class BandUnavailable(KeyError):
    """Raised when a requested band role is not in this stack."""


# Canonical role names. Anything not in here is not a role.
ROLES = ("COASTAL", "BLUE", "GREEN", "RED", "REDEDGE1", "REDEDGE2", "REDEDGE3",
         "NIR", "NIR08", "WATERVAPOUR", "CIRRUS", "SWIR1", "SWIR2",
         "VV", "VH", "HH", "HV", "PAN", "THERMAL")

# Aliases seen in real files, mapped to canonical roles. Lowercase keys.
BAND_NAME_ALIASES = {
    "b1": "COASTAL", "b01": "COASTAL", "coastal": "COASTAL", "aerosol": "COASTAL",
    "b2": "BLUE", "b02": "BLUE", "blue": "BLUE",
    "b3": "GREEN", "b03": "GREEN", "green": "GREEN",
    "b4": "RED", "b04": "RED", "red": "RED",
    "b5": "REDEDGE1", "b05": "REDEDGE1", "rededge1": "REDEDGE1",
    "b6": "REDEDGE2", "b06": "REDEDGE2", "rededge2": "REDEDGE2",
    "b7": "REDEDGE3", "b07": "REDEDGE3", "rededge3": "REDEDGE3",
    "b8": "NIR", "b08": "NIR", "nir": "NIR", "b8a": "NIR08", "nir08": "NIR08",
    "b9": "WATERVAPOUR", "b09": "WATERVAPOUR",
    "b10": "CIRRUS", "cirrus": "CIRRUS",
    "b11": "SWIR1", "swir1": "SWIR1", "swir16": "SWIR1",
    "b12": "SWIR2", "swir2": "SWIR2", "swir22": "SWIR2",
    "vv": "VV", "vh": "VH", "hh": "HH", "hv": "HV",
    "pan": "PAN", "thermal": "THERMAL",
}

# Band ordering for sensors whose files do not name their bands.
BAND_ORDERINGS = {
    "sentinel2_l2a_4band": ["GREEN", "RED", "NIR", "SWIR1"],
    "sentinel2_l2a_full": ["COASTAL", "BLUE", "GREEN", "RED", "REDEDGE1",
                           "REDEDGE2", "REDEDGE3", "NIR", "NIR08",
                           "WATERVAPOUR", "SWIR1", "SWIR2"],
    # LISS-III ships green, red, NIR, SWIR -- note there is NO blue band.
    "liss3": ["GREEN", "RED", "NIR", "SWIR1"],
    "liss4": ["GREEN", "RED", "NIR"],
    "rgb": ["RED", "GREEN", "BLUE"],
    "sentinel1_grd": ["VV", "VH"],
}


def normalise_role(name: str) -> str | None:
    """Map a file's band name to a canonical role, or None if unrecognised."""
    if not name:
        return None
    key = str(name).strip().lower().replace(" ", "").replace("_", "")
    if key in BAND_NAME_ALIASES:
        return BAND_NAME_ALIASES[key]
    up = key.upper()
    return up if up in ROLES else None


@dataclass
class BandStack:
    """Canonical raster: float32 (n_bands, H, W) plus everything needed to
    turn a pixel count into a real-world measurement."""

    data: np.ndarray                    # (n_bands, H, W) float32
    roles: list[str]                    # canonical role per band, same order
    crs: str | None = None
    transform: tuple | None = None      # affine, 6 coefficients
    pixel_area_m2: float | None = None
    nodata_mask: np.ndarray | None = None    # True where invalid
    scaled: bool = False                # True = calibrated reflectance 0..1
    modality: str = "optical"           # optical | sar
    scene_id: str | None = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.data.ndim != 3:
            raise ValueError(f"data must be (n_bands, H, W), got {self.data.shape}")
        if len(self.roles) != self.data.shape[0]:
            raise ValueError(
                f"{len(self.roles)} roles for {self.data.shape[0]} bands")
        self.roles = [r.upper() for r in self.roles]
        if self.nodata_mask is None:
            self.nodata_mask = np.zeros(self.data.shape[1:], dtype=bool)
        if self.nodata_mask.shape != self.data.shape[1:]:
            raise ValueError("nodata_mask shape does not match raster")

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape[1], self.data.shape[2]

    def has(self, *roles: str) -> bool:
        return all(r.upper() in self.roles for r in roles)

    def band(self, role: str) -> np.ndarray:
        """Return one band by role.

        Raises BandUnavailable rather than substituting. Do not "fix" this.
        """
        r = role.upper()
        if r not in self.roles:
            raise BandUnavailable(
                f"Band role {r!r} is not present in this scene. "
                f"Available: {sorted(self.roles)}. "
                f"Substituting a different band would produce a plausible "
                f"wrong number, so this is a hard failure."
            )
        return self.data[self.roles.index(r)]

    def valid(self) -> np.ndarray:
        """Boolean mask of usable pixels."""
        return ~self.nodata_mask

    def describe(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "bands": list(self.roles),
            "shape": list(self.shape),
            "crs": self.crs,
            "pixel_area_m2": self.pixel_area_m2,
            "radiometry": "calibrated_reflectance" if self.scaled else "relative_stretch",
            "modality": self.modality,
            "nodata_pixels": int(self.nodata_mask.sum()),
        }


def _demo() -> None:
    """Runnable check: the substitution guard and the role mapping."""
    bs = BandStack(
        data=np.zeros((2, 4, 4), np.float32), roles=["green", "nir"],
        pixel_area_m2=100.0, crs="EPSG:32645",
    )
    assert bs.roles == ["GREEN", "NIR"], bs.roles          # normalised on init
    assert bs.has("GREEN", "NIR") and not bs.has("SWIR1")
    assert bs.band("nir").shape == (4, 4)                   # role lookup is case-free

    try:
        bs.band("SWIR1")
        raise AssertionError("band() must raise for a missing role, not substitute")
    except BandUnavailable:
        pass

    assert normalise_role("B08") == "NIR"
    assert normalise_role("swir16") == "SWIR1"     # our fixtures use this name
    assert normalise_role("nonsense") is None

    try:
        BandStack(data=np.zeros((2, 4, 4), np.float32), roles=["GREEN"])
        raise AssertionError("role/band count mismatch must raise")
    except ValueError:
        pass

    print("bandstack: ok")


if __name__ == "__main__":
    _demo()
