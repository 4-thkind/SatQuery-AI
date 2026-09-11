"""Spectral Feasibility Gate (L1). Spec section 8.

Runs BEFORE any tool. Decides whether the question is answerable from these
pixels at all. A well-argued ABSTAIN is a better answer than a confident number
computed from bands that cannot support it -- and it is the single feature that
separates this system from a chatbot with a colourmap.
"""

from __future__ import annotations

import numpy as np
from skimage.morphology import disk, opening

from ..schemas import FeasibilityVerdict
from .bandstack import BandStack

# intent -> (required roles, proxy roles, abstain message key)
INTENT_REQUIREMENTS = {
    "vegetation_health": (["NIR", "RED"], ["RED", "GREEN", "BLUE"], "need_nir"),
    "water_extent":      (["GREEN", "NIR"], ["VV"], "need_nir_or_sar"),
    "flood_extent":      (["GREEN", "NIR"], ["VV"], "need_nir_or_sar"),
    "builtup_extent":    (["SWIR1", "NIR"], ["RED", "GREEN", "BLUE"], "need_swir"),
    "burn_severity":     (["NIR", "SWIR2"], [], "need_swir2"),
    "crop_stress":       (["NIR", "RED"], [], "need_nir"),
    "object_count":      (["RED", "GREEN", "BLUE"], ["PAN"], "need_optical"),
    "scene_describe":    ([], [], None),
    "method_explain":    ([], [], None),
    "change_detect":     ([], [], "need_two_scenes"),
    "shoreline":         (["GREEN", "NIR"], ["VV"], "need_nir_or_sar"),
}

ABSTAIN_MESSAGES = {
    "need_nir": (
        "This scene has only visible RGB bands. Vegetation health is measured from "
        "the near-infrared response of chlorophyll, which is not recorded in RGB. "
        "I can give you a rough greenness proxy (VARI), but it will not distinguish "
        "healthy crop from painted surfaces or algal water. For a real answer: "
        "RESOURCESAT-2 LISS-III (bands 2,3,4 include NIR) or Sentinel-2 (B8)."
    ),
    "need_nir_or_sar": (
        "Water extent requires either a near-infrared band (water absorbs NIR almost "
        "completely, which is what makes NDWI work) or SAR backscatter (smooth water "
        "gives specular reflection away from the sensor). This scene has neither. "
        "For flood mapping during monsoon, SAR is the correct instrument regardless: "
        "RISAT-1 or Sentinel-1 see through cloud."
    ),
    "need_swir": (
        "Built-up extent is best separated using the short-wave infrared band; "
        "concrete and asphalt are bright in SWIR and dark in NIR, which is what NDBI "
        "exploits. Without SWIR I can only use texture and brightness heuristics, "
        "which confuse bare soil and dry riverbed with settlement."
    ),
    "need_swir2": (
        "Burn severity uses the Normalised Burn Ratio, which needs SWIR2 (around "
        "2.2 micrometres) where charred material is distinctively bright and healthy "
        "vegetation is dark. Not present in this scene."
    ),
    "need_optical": (
        "Counting discrete objects needs visible-band imagery at sufficient ground "
        "sampling distance. This scene does not provide it."
    ),
    "cloud_blocked": (
        "Roughly {pct}% of this scene is under cloud, and the region you asked about "
        "is inside the cloud mask. Optical sensors cannot see through cloud. "
        "Reporting a number here would be guessing at cloud shadow, which is dark in "
        "NIR and reads as water. Use SAR -- RISAT-1 or Sentinel-1 -- which is "
        "unaffected by cloud cover."
    ),
    "need_two_scenes": (
        "Change detection needs two co-registered scenes of the same area at "
        "different dates. Select a second scene and I will align them and compute a "
        "pixel-wise difference."
    ),
}

RECOMMENDATIONS = {
    "need_nir": "Sentinel-2 (B8) or Resourcesat-2 LISS-III",
    "need_nir_or_sar": "Sentinel-1 SAR or RISAT-1",
    "need_swir": "Sentinel-2 (B11/B12) or Landsat-8 OLI",
    "need_swir2": "Sentinel-2 (B12) or Landsat-8 (B7)",
    "need_optical": "Cartosat-2 or Sentinel-2",
    "cloud_blocked": "Sentinel-1 SAR or RISAT-1 (cloud-penetrating)",
    "need_two_scenes": "select a second acquisition of the same area",
}

CLOUD_ANSWER_MAX = 0.20      # under this: ANSWER
CLOUD_ABSTAIN_MIN = 0.60     # over this: ABSTAIN for surface-dependent intents

# Intents whose answer is destroyed by cloud (they measure the surface).
SURFACE_DEPENDENT = {"vegetation_health", "water_extent", "flood_extent",
                     "builtup_extent", "burn_severity", "crop_stress",
                     "shoreline", "change_detect"}


def estimate_cloud_fraction(bs: BandStack) -> tuple[float, np.ndarray]:
    """Heuristic cloud fraction. Documented as a heuristic everywhere it surfaces.

    Not Fmask. Honesty about the method is itself a scoring point.
    """
    empty = np.zeros(bs.shape, bool)
    if bs.modality == "sar":
        return 0.0, empty            # SAR sees through cloud

    if bs.has("BLUE", "GREEN", "RED", "SWIR1"):
        vis = (bs.band("BLUE") + bs.band("GREEN") + bs.band("RED")) / 3.0
        # Bright in visible AND in SWIR1. Snow is bright in visible but dark in
        # SWIR1, which is what separates the two.
        mask = (vis > 0.30) & (bs.band("SWIR1") > 0.20)
    elif bs.has("BLUE", "GREEN", "RED"):
        b, g, r = bs.band("BLUE"), bs.band("GREEN"), bs.band("RED")
        vis = (b + g + r) / 3.0
        mx = np.maximum.reduce([b, g, r])
        mn = np.minimum.reduce([b, g, r])
        sat = np.divide(mx - mn, mx + 1e-6)
        mask = (vis > 0.35) & (sat < 0.15)          # bright and spectrally flat
    elif bs.has("GREEN", "RED", "NIR", "SWIR1"):
        # No BLUE (LISS-III, and our 4-band fixtures). Cloud is still bright
        # across every available band; SWIR1 keeps snow out.
        vis = (bs.band("GREEN") + bs.band("RED")) / 2.0
        mask = (vis > 0.30) & (bs.band("NIR") > 0.30) & (bs.band("SWIR1") > 0.20)
    else:
        return 0.0, empty

    mask &= ~bs.nodata_mask
    mask = opening(mask, disk(3))                   # kill speckle
    return float(mask.mean()), mask


def assess(bs: BandStack, intent: str, has_second_scene: bool = False
           ) -> FeasibilityVerdict:
    """The gate. Returns ANSWER / DEGRADE / ABSTAIN with a reason."""
    required, proxy, msg_key = INTENT_REQUIREMENTS.get(intent, ([], [], None))
    present = sorted(bs.roles)
    missing = [r for r in required if r not in bs.roles]
    cloud, _ = estimate_cloud_fraction(bs)

    def v(**kw) -> FeasibilityVerdict:
        base = dict(intent=intent, required_bands=required, present_bands=present,
                    missing_bands=missing, cloud_fraction=round(cloud, 4))
        return FeasibilityVerdict(**{**base, **kw})

    # --- change detection needs a pair, whatever the bands ---------------
    if intent == "change_detect" and not has_second_scene:
        return v(verdict="ABSTAIN", prior=0.0,
                 reason=ABSTAIN_MESSAGES["need_two_scenes"],
                 recommendation=RECOMMENDATIONS["need_two_scenes"])

    # --- band availability ----------------------------------------------
    using_proxy = False
    if missing:
        if proxy and bs.has(*proxy):
            using_proxy = True
        else:
            return v(verdict="ABSTAIN", prior=0.0, using_proxy=False,
                     reason=ABSTAIN_MESSAGES.get(
                         msg_key, f"This scene lacks {missing} and no proxy exists."),
                     recommendation=RECOMMENDATIONS.get(msg_key, ""))

    # --- cloud ------------------------------------------------------------
    if intent in SURFACE_DEPENDENT:
        if cloud > CLOUD_ABSTAIN_MIN:
            return v(verdict="ABSTAIN", prior=0.0, using_proxy=using_proxy,
                     reason=ABSTAIN_MESSAGES["cloud_blocked"].format(
                         pct=round(cloud * 100)),
                     recommendation=RECOMMENDATIONS["cloud_blocked"])
        if cloud > CLOUD_ANSWER_MAX:
            clear = 1.0 - cloud
            return v(verdict="DEGRADE", prior=round(0.6 * clear + 0.2, 3),
                     using_proxy=using_proxy,
                     reason=(f"About {cloud * 100:.0f}% of this scene is under cloud "
                             f"(heuristic estimate). The measurement below covers "
                             f"only the {clear * 100:.0f}% that is clear, so treat it "
                             f"as a lower bound on the true extent."),
                     recommendation=RECOMMENDATIONS["cloud_blocked"])

    if using_proxy:
        return v(verdict="DEGRADE", prior=0.6, using_proxy=True,
                 reason=ABSTAIN_MESSAGES.get(msg_key, "")
                        + " Proceeding with the degraded proxy.",
                 recommendation=RECOMMENDATIONS.get(msg_key, ""))

    return v(verdict="ANSWER", prior=1.0, using_proxy=False,
             reason="Required bands are present and cloud cover is low.")


def _demo() -> None:
    """Runnable check: each verdict must be reachable on the real fixtures."""
    import pathlib
    from .ingest import load_geotiff

    root = pathlib.Path(__file__).resolve().parents[2]
    clear = load_geotiff(root / "data/demo/bihar_post_flood.tif")
    cloudy = load_geotiff(root / "data/demo/bihar_post_flood_cloudy.tif")

    # ANSWER: clear scene, bands present.
    a = assess(clear, "flood_extent")
    assert a.verdict == "ANSWER" and a.prior == 1.0, a

    # DEGRADE: same intent, cloudy scene (~32% cloud).
    d = assess(cloudy, "flood_extent")
    assert d.verdict == "DEGRADE", d
    assert 0.20 < d.cloud_fraction < 0.60, d.cloud_fraction
    assert 0.0 < d.prior < 1.0, d.prior

    # ABSTAIN on bands: burn severity needs SWIR2, fixtures only have SWIR1.
    b = assess(clear, "burn_severity")
    assert b.verdict == "ABSTAIN" and b.missing_bands == ["SWIR2"], b
    assert "Sentinel-2" in b.recommendation

    # ABSTAIN on a missing pair.
    c = assess(clear, "change_detect", has_second_scene=False)
    assert c.verdict == "ABSTAIN", c
    assert assess(clear, "change_detect", has_second_scene=True).verdict == "ANSWER"

    # scene_describe is always answerable.
    assert assess(cloudy, "scene_describe").verdict == "ANSWER"

    print(f"feasibility: ok  clear={a.verdict} cloudy={d.verdict} "
          f"({d.cloud_fraction:.1%} cloud, prior {d.prior}) burn={b.verdict}")


if __name__ == "__main__":
    _demo()
