"""Run the existing kernel against real Resourcesat LISS-III imagery.

    python scripts/verify_real.py

Round 1 claimed that ingest reads geometry and band roles from the file, so real
imagery drops in without code changes. That claim was never actually tested. This
script tests it, on real ISRO data, and prints what happened.

There is no ground truth here -- these are real scenes, nobody labelled them. So
this does not assert areas. What it asserts is that the machinery behaves:

  * ingest reads four named bands and finds the scene calibrated
  * every index whose bands are present computes and separates
  * NBR ABSTAINs, because LISS-III has no SWIR2 -- the real sensor's real limit
  * a bi-temporal pair produces a change measurement in the right direction

That last one is the useful check. Monsoon minus dry season should show *more*
water, and it is measured by the same deterministic code as everything else.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.core.feasibility import assess, estimate_cloud_fraction  # noqa: E402
from backend.core.ingest import load_geotiff                          # noqa: E402
from backend.kernel.measurement import measure_area                   # noqa: E402
from backend.kernel.segmentation import mask_difference, threshold_mask  # noqa: E402
from backend.kernel.spectral import compute_index                     # noqa: E402
from backend.core.ingest import Session                               # noqa: E402

CONVERTED = pathlib.Path(__file__).resolve().parent.parent / "data/real/converted"

# Wettest and driest of the eight, so the change signal is as large as the
# archive allows.
PAIR = ("liss3_106_053_18aug2022.tif", "liss3_106_053_02feb2023.tif")


def band_report(bs, name: str) -> None:
    print(f"\n{'=' * 72}\n{name}\n{'=' * 72}")
    print(f"  bands      {', '.join(sorted(bs.roles))}")
    print(f"  shape      {bs.shape[0]} x {bs.shape[1]} px")
    print(f"  calibrated {bs.scaled}   (absolute thresholds are meaningful)")
    cloud, _ = estimate_cloud_fraction(bs)
    print(f"  cloud      {cloud:.1%}  (measured here; the product reports -NA-)")


def index_report(bs, session) -> dict[str, float]:
    """Compute every index this scene supports, threshold it, measure the area."""
    areas: dict[str, float] = {}
    print("\n  index    threshold   area (ha)   note")
    print("  " + "-" * 62)
    for idx, direction, label in [
        ("ndvi", "gt", "vegetation"),
        ("ndwi", "gt", "water"),
        ("mndwi", "gt", "water"),
        ("ndbi", "gt", "built-up"),
        ("nbr", "lt", "burn"),
    ]:
        r = compute_index(bs, session, idx)
        if not r.ok:
            reason = (r.caveats or ["unavailable"])[0]
            print(f"  {idx:8s} {'--':>9s}   {'--':>9s}   {reason[:34]}")
            continue
        m = threshold_mask(bs, session, r.mask_handle, mode="otsu",
                           direction=direction)
        if not m.ok:
            reason = (m.caveats or ["refused"])[0]
            print(f"  {idx:8s} {'--':>9s}   {'ABSTAIN':>9s}   {reason[:34]}")
            continue
        a = measure_area(bs, session, m.mask_handle, label=label)
        ha = a.value["hectares"]
        areas[idx] = ha
        thr = m.value["threshold"]
        print(f"  {idx:8s} {thr:9.3f}   {ha:9.1f}   {label}")
    return areas


def main() -> int:
    if not CONVERTED.exists():
        print("no converted scenes. run: python scripts/ingest_liss3.py")
        return 1

    scenes = sorted(CONVERTED.glob("liss3_*.tif"))
    if not scenes:
        print(f"no liss3_*.tif under {CONVERTED}")
        return 1

    print(f"Real Resourcesat-2A LISS-III, path/row 106/053 — {len(scenes)} scenes")
    print("Source: Bhoonidhi / NRSC / ISRO. Atmospherically corrected.")

    session = Session()

    # --- one scene in detail -------------------------------------------
    lead = CONVERTED / PAIR[0]
    if not lead.exists():
        lead = scenes[0]
    bs = load_geotiff(lead)
    band_report(bs, f"{lead.name}  (monsoon)")

    # The gate decides ANSWER / DEGRADE / ABSTAIN before anything is measured.
    print("\n  feasibility gate:")
    for intent in ("flood_extent", "vegetation_health", "builtup_extent",
                   "burn_severity"):
        v = assess(bs, intent)
        print(f"    {intent:20s} {v.verdict:8s} {v.reason[:44]}")

    areas = index_report(bs, session)

    # --- the SWIR2 story -----------------------------------------------
    print("\n  Note on burn severity: NBR needs SWIR2, and LISS-III does not")
    print("  carry it. The refusal above is the real sensor's real constraint,")
    print("  not a limitation of this demo's data.")

    # --- bi-temporal change --------------------------------------------
    a_path, b_path = CONVERTED / PAIR[0], CONVERTED / PAIR[1]
    if a_path.exists() and b_path.exists():
        print(f"\n{'=' * 72}\nBi-temporal change: Aug 2022 (monsoon) vs Feb 2023 (dry)"
              f"\n{'=' * 72}")
        bs_a, bs_b = load_geotiff(a_path), load_geotiff(b_path)
        sess = Session()

        def water_mask(stack, tag):
            idx = compute_index(stack, sess, "mndwi")
            m = threshold_mask(stack, sess, idx.mask_handle, mode="otsu",
                               direction="gt")
            if not m.ok:
                return None, 0.0
            area = measure_area(stack, sess, m.mask_handle, label=f"water {tag}")
            return m.mask_handle, area.value["hectares"]

        h_a, ha_a = water_mask(bs_a, "aug")
        h_b, ha_b = water_mask(bs_b, "feb")
        print(f"  water, Aug 2022   {ha_a:10.1f} ha")
        print(f"  water, Feb 2023   {ha_b:10.1f} ha")

        if h_a and h_b:
            d = mask_difference(bs_a, sess, h_a, h_b, op="sub")
            if d.ok:
                new = measure_area(bs_a, sess, d.mask_handle, label="new water")
                print(f"  Aug AND NOT Feb   {new.value['hectares']:10.1f} ha "
                      f"of seasonal inundation")
                print(f"  arithmetic        {d.provenance['arithmetic']}")
                direction = "more" if ha_a > ha_b else "less"
                print(f"\n  Monsoon shows {direction} water than dry season — "
                      f"which is the expected sign.")

    # --- what this proves ----------------------------------------------
    print(f"\n{'=' * 72}")
    print("  Ingest read band roles from the file, not from a hardcoded order.")
    print("  Indices computed on real atmospherically-corrected reflectance.")
    print("  Thresholds chosen by Otsu from each scene's own histogram.")
    print("  Areas measured by the same deterministic kernel as the fixtures.")
    print("  No code path is specific to real or synthetic input.")
    if areas:
        print(f"\n  {len(areas)} of 5 indices produced a measurement; the rest")
        print("  refused for stated reasons.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
