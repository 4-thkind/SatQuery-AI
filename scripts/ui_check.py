"""Render the UI in a real browser and assert it works. Needs the server running.

    python -m uvicorn backend.app:app &
    python scripts/ui_check.py
"""
import json, os, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

OUT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "screens"

# Expected figures come from the generated ground truth, never from literals:
# regenerating the scenes changes every area, and a hardcoded number here fails
# later for a reason that has nothing to do with the UI it is supposed to test.
def _truth():
    t = json.loads((ROOT / "data/demo/truth.json").read_text(encoding="utf-8"))["scenes"]
    return t


def _fmt_ha(v):
    """Thousands-separated integer part, matching what the UI renders.

    Truncate rather than round: the UI prints 2,670.59, so rounding the expected
    value to 2,671 would never substring-match.
    """
    return f"{int(v):,d}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    errs, fails = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.on("pageerror", lambda e: errs.append(str(e)))

        port = os.environ.get("SATQUERY_UI_PORT", "8000")
        pg.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
        pg.wait_for_selector(".scene", timeout=15000)

        n = pg.locator(".scene").count()
        # Read the count from the manifest rather than hardcoding it. This
        # said 7 and broke the moment the eight real LISS-III scenes were
        # registered -- the same reason the areas above are not hardcoded.
        want = json.loads(
            (ROOT / "data/demo/manifest.json").read_text(encoding="utf-8")
        )["scene_count"]
        if n != want:
            fails.append(f"expected {want} scenes, got {n}")
        pg.screenshot(path=OUT / "01-initial.png")

        # Ask the flood question.
        pg.locator(".sugg button", has_text="How much area is flooded?").click()
        pg.wait_for_selector(".hero", timeout=60000)
        hero = pg.locator(".hero").first.inner_text()
        want = _fmt_ha(_truth()["bihar_post_flood"]["water_ha"])
        if want not in hero: fails.append(f"hero = {hero!r}, expected ~{want}")
        if not pg.locator(".wx").count(): fails.append("weather card missing")
        pg.wait_for_timeout(600)
        pg.screenshot(path=OUT / "02-answer.png")

        # Evidence drawer.
        pg.locator(".chip", has_text="Evidence").first.click()
        pg.wait_for_selector(".draw", timeout=10000)
        if not pg.locator(".arith").count(): fails.append("no arithmetic in drawer")
        arith = pg.locator(".arith").first.inner_text()
        if "px x" not in arith: fails.append(f"arithmetic malformed: {arith!r}")
        pg.screenshot(path=OUT / "03-evidence.png")
        pg.locator(".drawtop button").click()
        pg.wait_for_timeout(300)

        # Translation pills test (translate answer to Hindi).
        if pg.locator(".lang-pill").count():
            pg.locator(".lang-pill", has_text="हिन्दी").first.click()
            pg.wait_for_timeout(1000)
            tr_txt = pg.locator(".card .narr").first.inner_text()
            if "बाढ़" not in tr_txt and "हेक्टेयर" not in tr_txt:
                fails.append("Hindi translation pill did not update narration")
            pg.screenshot(path=OUT / "03b-translate-hi.png")

        # Report card modal test.
        if pg.locator(".chip", has_text="Export Report Card").count():
            pg.locator(".chip", has_text="Export Report Card").first.click()
            pg.wait_for_selector(".rep-card", timeout=5000)
            if not pg.locator(".rep-sec-title").count():
                fails.append("report card missing audit sections")
            pg.screenshot(path=OUT / "03c-report-card.png")
            pg.locator(".rep-head button").click()
            pg.wait_for_timeout(300)

        # Zoom controls test.
        if pg.locator(".zoom-btn").count():
            pg.locator(".zoom-btn", has_text="+").click()
            pg.wait_for_timeout(300)
            if not pg.locator(".zoom-btn.reset").count():
                fails.append("zoom reset button did not appear after zoom in")
            pg.locator(".zoom-btn.reset").click()
            pg.wait_for_timeout(200)

        # ABSTAIN path.
        pg.locator(".scene", has_text="Forest Burn Scar").click()
        pg.wait_for_timeout(700)
        pg.locator(".sugg button", has_text="burn scar").click()
        pg.wait_for_selector(".card.abstain", timeout=60000)
        txt = pg.locator(".card.abstain").first.inner_text()
        if "SWIR2" not in txt: fails.append("abstain card missing the reason")
        if pg.locator(".card.abstain .hero").count(): fails.append("abstain must show no number")
        # No mask may remain on screen after a refusal.
        if pg.locator(".frame img.ov").count() and            pg.locator(".frame img.ov").first.is_visible():
            fails.append("mask overlay still shown after ABSTAIN")
        pg.screenshot(path=OUT / "04-abstain.png")

        # Change detection.
        pg.locator(".scene", has_text="Post-Monsoon Inundation").click()
        pg.wait_for_timeout(700)
        pg.locator(".sugg button", has_text="more water").click()
        pg.wait_for_selector(".hero", timeout=60000)
        h2 = pg.locator(".hero").first.inner_text()
        t = _truth()
        # The change figure is measured from the two morphology-cleaned masks, so
        # it lands within a hectare or two of the raw truth subtraction rather than
        # exactly on it. Assert the magnitude, not the last decimal.
        want2 = t["bihar_post_flood"]["water_ha"] - t["bihar_pre_flood"]["water_ha"]
        got2 = float(h2.replace(",", "").replace("ha", "").strip())
        if abs(got2 - want2) / want2 > 0.02:
            fails.append(f"change hero = {h2!r}, expected ~{want2:,.2f}")
        pg.screenshot(path=OUT / "05-change.png")

        # --- epoch compare & split swipe -----------------------------------
        # Paired scenes offer both split-swipe slider and side-by-side views.
        if not pg.locator(".cmpbtn").count():
            fails.append("paired scene offers no compare control")
        else:
            pg.locator(".cmpbtn").click()
            pg.wait_for_selector(".split-wrap", timeout=10000)
            if not pg.locator(".split-line").count():
                fails.append("split swipe slider line missing")
            if not pg.locator(".split-badge.left").count():
                fails.append("split swipe BEFORE badge missing")
            pg.screenshot(path=OUT / "08a-split-swipe.png")

            # Switch to side-by-side mode
            if pg.locator(".seg button", has_text="Side-by-side").count():
                pg.locator(".seg button", has_text="Side-by-side").click()
                pg.wait_for_selector(".cmp .half", timeout=10000)
                if pg.locator(".cmp .half").count() != 2:
                    fails.append("compare view did not render two epochs")
                lbl = " ".join(pg.locator(".epoch").all_inner_texts())
                if "BEFORE" not in lbl or "AFTER" not in lbl:
                    fails.append(f"compare epochs unlabelled: {lbl!r}")
                if pg.locator(".cmp .half").nth(0).locator("img.ov").count():
                    fails.append("mask drawn on the BEFORE epoch it was not measured from")
                pg.screenshot(path=OUT / "08-compare.png")
            pg.locator(".cmpbtn").click()
            pg.wait_for_timeout(300)

        # --- no ghost controls -------------------------------------------
        # Every visible control must do something. The header once carried an
        # "EN | हिं" badge and the layer panel a readOnly checkbox and slider:
        # all three looked interactive and were inert, which reads as a mockup.
        for sel in ("input[readonly]", "input[type=range][readonly]"):
            if pg.locator(sel).count():
                fails.append(f"inert control still present: {sel}")

        # The scene-preview checkbox must actually toggle the base image.
        base = pg.locator(".frame img").first
        before = pg.locator(".frame img").count()
        pg.locator(".layers input[type=checkbox]").nth(1).uncheck()
        pg.wait_for_timeout(200)
        if pg.locator(".frame img").count() >= before:
            fails.append("scene preview checkbox does not hide the base image")
        pg.locator(".layers input[type=checkbox]").nth(1).check()

        # --- reply language follows the question --------------------------
        # A Punjabi question answered in English is the failure this guards.
        # Wait on the card COUNT rising, not on a timeout: .last otherwise reads
        # the previous answer and the assertion fails for the wrong reason.
        n_before = pg.locator(".card .narr").count()
        pg.fill(".askbox input", "ਹੜ੍ਹ ਦਾ ਖੇਤਰ ਕਿੰਨਾ ਹੈ")
        pg.click(".askbox button")
        pg.wait_for_function(
            "n => document.querySelectorAll('.card .narr').length > n",
            arg=n_before, timeout=30000)
        pa = pg.locator(".card .narr").last.inner_text()
        if "ਹੈਕਟੇਅਰ" not in pa:
            fails.append(f"Punjabi query not answered in Punjabi: {pa[:80]!r}")
        # The measured number must survive translation unchanged.
        if _fmt_ha(_truth()["bihar_post_flood"]["water_ha"]) not in pa:
            fails.append("Punjabi answer lost the measured figure")
        pg.screenshot(path=OUT / "06-punjabi.png")

        # --- out-of-coverage place is refused by name ---------------------
        n_before = pg.locator(".card .narr").count()
        pg.fill(".askbox input", "how much flooding in Assam")
        pg.click(".askbox button")
        pg.wait_for_function(
            "n => document.querySelectorAll('.card .narr').length > n",
            arg=n_before, timeout=30000)
        last = pg.locator(".card").last
        txt2 = last.inner_text()
        if "Assam" not in txt2:
            fails.append("out-of-coverage query did not name the place")
        if last.locator(".hero").count():
            fails.append("out-of-coverage query returned a number")
        pg.screenshot(path=OUT / "07-coverage.png")

        b.close()

    for e in errs: print("  JS ERROR:", e)
    for f in fails: print("  FAIL:", f)
    ok = not errs and not fails
    print(("ui: ok  " if ok else "ui: FAILED  ") + f"screenshots -> {OUT}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
