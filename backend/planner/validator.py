"""Numeral guard. Spec section 13.2.

Rejects any narration containing a number that the kernel did not compute. At
Tier C the templates are already safe, so this looks redundant -- it is not. It
is the safety net for Tiers A and B, where an LLM writes the prose and WILL
invent a plausible figure. Building it now means the model never ships without it.
"""

from __future__ import annotations

import re

# Numbers with optional thousands separators and decimals, incl. percentages.
NUMERAL = re.compile(r"\d[\d,]*\.?\d*")

# Numbers that are always allowed: they are structural, not measurements.
# Round numbers like 10, 100, 1000, 10000 were removed because an LLM can
# fabricate approximation figures (e.g. "nearly 1000 families", "10000 people").
ALWAYS_OK = {"0", "1", "2", "3", "4", "5"}

# Four-digit years, 1900-2099. A citation date is not a measured quantity, and
# blocking it was silently gutting the Tier B corpus path: 48 of the 85 corpus
# chunks mention a publication year (2008, 2013, 2015, 2018, 2020, 2022...),
# so any faithful composed answer lost its narration and fell back to dumping
# the raw chunk. The numeral guard exists to stop a MEASUREMENT being invented;
# "McFeeters 1996" is a reference, not a hectare count.
YEAR = re.compile(r"^(19|20)\d\d$")


def _canon(tok: str) -> str:
    """Canonical form for comparison. Sign is stripped: NUMERAL does not capture
    a leading minus, so a threshold of -0.2253 must match the "0.2253" found in
    the text. Magnitude is what needs verifying -- an invented sign on a real
    magnitude is not a failure mode worth false-positiving over."""
    t = tok.replace(",", "").lstrip("+-").rstrip(".")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def collect_facts(facts: dict, extra: list = ()) -> set[str]:
    """Every numeral the kernel produced, in canonical form.

    Rounded variants are included: narration may legitimately say "2,603" for
    2603.12, and forbidding that would make honest prose impossible.
    """
    out: set[str] = set(ALWAYS_OK)

    def add(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            f = float(v)
            out.add(_canon(f"{f:.4f}"))
            out.add(_canon(f"{f:.2f}"))
            out.add(_canon(f"{f:.1f}"))
            out.add(_canon(f"{round(f):d}"))
            # Only apply * 100 to true fractions/ratios (0.0 to 1.0), not arbitrary
            # negative thresholds (e.g. -0.2253) which would silently legitimize "23".
            if 0.0 <= f <= 1.0:
                out.add(_canon(f"{f * 100:.1f}"))     # fraction rendered as percent
                out.add(_canon(f"{round(f * 100):d}"))
        elif isinstance(v, str):
            for m in NUMERAL.findall(v):
                out.add(_canon(m))
        elif isinstance(v, dict):
            for x in v.values():
                add(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                add(x)

    add(facts)
    for e in extra:
        add(e)
    return out


def validate_numerals(text: str, facts: dict, extra: list = ()) -> tuple[bool, list[str]]:
    """Return (ok, offending numerals). Numbers only, no claim checking.

    Kept separate because the two guards have different scopes: every number
    in an answer must trace to the kernel, but only text describing THIS
    SCENE may be held to what the kernel observed. A methodology answer
    quoting literature is the case that needs numerals fenced and claims free.
    """
    allowed = collect_facts(facts, extra)
    bad = [tok for tok in NUMERAL.findall(text)
           if _canon(tok) not in allowed and not YEAR.match(_canon(tok))]
    return (not bad), bad


def validate_against_sources(text: str, sources: list) -> tuple[bool, list[str]]:
    """Return (ok, invented numerals) for text composed from retrieved sources.

    A methodology answer's numbers belong to the literature, not the kernel:
    LISS-III really is 23.5 m at a 24-day revisit, and dNBR thresholds really
    start at 0.10. Checking those against the kernel's fact set rejected 46 of
    85 corpus chunks, so every faithful composed answer lost its narration and
    fell back to dumping the raw chunk.

    The guarantee that matters here is different and narrower: the model may
    quote its sources but must not invent figures. So a numeral is allowed when
    it appears in the source text the model was given, and rejected otherwise.
    """
    pool = " ".join(
        str(s.get("text", "")) + " " + str(s.get("excerpt", ""))
        for s in sources if isinstance(s, dict)
    )
    allowed = {_canon(tok) for tok in NUMERAL.findall(pool)} | set(ALWAYS_OK)
    bad = [tok for tok in NUMERAL.findall(text)
           if _canon(tok) not in allowed and not YEAR.match(_canon(tok))]
    return (not bad), bad


def validate_narration(text: str, facts: dict, extra: list = ()) -> tuple[bool, list[str]]:
    """Return (ok, offending items): invented numerals AND invented claims.

    Use this for text describing a measured scene. For text explaining a
    method, use validate_numerals -- see its docstring.
    """
    num_ok, num_bad = validate_numerals(text, facts, extra)
    claim_ok, claim_bad = validate_claims(text, facts)
    return (num_ok and claim_ok), (num_bad + claim_bad)


# Words asserting something the kernel never computes. It measures HOW MUCH of
# a class is present; it has no notion of where a region sits in the frame, of
# compass direction, or of what kind of waterbody it is.
#
# This exists because Tier B failed in exactly that way. Given
# hectares=2603.12 for water in the Kosi basin, the model wrote:
#
#     "The water in the left of the image is in the sea."
#
# Inland flood described as sea, a spatial claim from nothing, and both
# measured values dropped. validate_narration passed it because it contains no
# digits -- the numeral guard blocks invented NUMBERS, never invented FACTS.
# At Tier C templates made this impossible; at Tier B prose it is the main
# failure mode, so it needs its own guard.
# Bare "upper"/"lower" were here and were wrong: the Tier C cloud caveat says
# "treat it as a lower bound on the flooded area", which is a statistical
# qualifier, not a claim about where something sits. Same trap as "upper
# limit" and "lower reaches". Only the compound forms assert a position.
SPATIAL_CLAIMS = (
    "left of", "right of", "top of", "bottom of", "centre of", "center of",
    "upper left", "upper right", "lower left", "lower right",
    "upper half", "lower half", "top left", "top right",
    "bottom left", "bottom right",
    "north", "south", "east", "west", "corner",
    "foreground", "background", "middle of the image",
)

# Naming a waterbody type is a geographic claim, not a measurement. "Water" is
# what the index detects; whether it is sea, lake or river is not.
FEATURE_CLAIMS = (
    "sea", "ocean", "lake", "pond", "reservoir", "bay", "coast", "coastal",
    "beach", "shoreline", "river bank", "mountain", "hill", "valley",
    "city", "town", "village", "road", "building",
)


def validate_claims(text: str, facts: dict) -> tuple[bool, list[str]]:
    """Return (ok, offending phrases) for claims the kernel cannot support.

    A phrase is allowed when it appears in the facts themselves -- a scene
    genuinely about a shoreline may say shoreline, and the class label is
    whatever the kernel measured. Everything else is the model narrating the
    picture it imagines rather than the numbers it was given.
    """
    low = text.lower()
    # Anything already present in the kernel's own facts is legitimate: a scene
    # whose measured label IS "coastal wetlands" may say coastal wetlands.
    supported = " ".join(
        str(v).lower() for v in facts.values() if isinstance(v, str)
    )
    bad = []
    for p in SPATIAL_CLAIMS + FEATURE_CLAIMS:
        if p in supported:
            continue
        # Whole-word (or whole-phrase) match. Substring matching was wrong:
        # it flagged "north" and "west" inside "Northwest", and "coast"
        # inside "coastal", blocking honest text over a spelling accident.
        if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", low):
            bad.append(p)
    return (not bad), bad


def _demo() -> None:
    facts = {"hectares": 2603.12, "threshold": -0.2253, "scene_fraction": 0.2481,
             "arithmetic": "260,312 px x 100.0000 m2/px = 26,031,200.0 m2"}

    ok, bad = validate_narration(
        "2,603.12 hectares were measured, covering 24.8% of the scene, "
        "thresholded at -0.2253.", facts)
    assert ok, bad

    # Rounded restatement of a real fact is fine.
    ok, bad = validate_narration("About 2,603 hectares.", facts)
    assert ok, bad

    # A fabricated number is caught -- this is the whole point.
    ok, bad = validate_narration(
        "2,603.12 hectares were flooded, affecting 47,000 people.", facts)
    assert not ok and any(_canon(b) == "47000" for b in bad), bad

    # Round-number approximation hallucinations must be caught (no ALWAYS_OK leak)
    ok_1000, bad_1000 = validate_narration(
        "About 2,603 hectares were flooded, displacing nearly 1000 families.", facts)
    assert not ok_1000 and any(_canon(b) == "1000" for b in bad_1000), bad_1000

    ok_10000, bad_10000 = validate_narration(
        "About 2,603 hectares were flooded, and roughly 10000 people were affected.", facts)
    assert not ok_10000 and any(_canon(b) == "10000" for b in bad_10000), bad_10000

    # Negative threshold must not whitelist "23" via blind *100
    ok_23, bad_23 = validate_narration("Found 23 distinct zones.", facts)
    assert not ok_23 and any(_canon(b) == "23" for b in bad_23), bad_23

    # A number that merely looks plausible is still caught.
    ok, bad = validate_narration("The area is 2,700.00 hectares.", facts)
    assert not ok and any(_canon(b) == "2700" for b in bad), bad

    # Facts reachable through nested structures count as computed.
    nested = {"sens": {"+0.05": {"hectares": 2599.4}}}
    ok, bad = validate_narration("as low as 2,599.4 ha", nested)
    assert ok, bad

    # --- claim guard: invented geography, not just invented numbers -------
    # Tier B produced exactly this, given hectares for water in the Kosi
    # basin: an inland flood called sea, plus a spatial claim from nothing.
    # The numeral guard passed it because it contains no digits.
    scene = {"hectares": 2603.12, "label": "water", "index": "mndwi"}
    ok, bad = validate_narration(
        "The water in the left of the image is in the sea.", scene)
    assert not ok and "sea" in bad and "left of" in bad, bad

    # Honest prose over the same facts survives.
    ok, bad = validate_narration(
        "Measured 2,603.12 hectares of water.", scene)
    assert ok, bad

    # Whole-word matching: substring matching flagged "north" and "west"
    # inside "Northwest", and "coast" inside "coastal", blocking honest text
    # over a spelling accident.
    ok, bad = validate_narration("The Northwest monsoon drives this.",
                                 {"hectares": 1.0})
    assert ok, bad

    # A claim word IS allowed when the kernel measured that very class.
    ok, bad = validate_narration(
        "Measured 2,603.12 hectares of coastal wetlands.",
        {"hectares": 2603.12, "label": "coastal wetlands"})
    assert ok, bad

    # --- source guard: literature figures vs invented ones ----------------
    # A methodology answer's numbers come from its sources, so checking them
    # against the kernel's facts rejected 46 of 85 corpus chunks and sent
    # every faithful answer back to dumping raw text. Check the sources.
    srcs = [{"text": "LISS-III images at 23.5 m resolution, 24-day revisit."}]
    ok, bad = validate_against_sources(
        "LISS-III images at 23.5 m with a 24-day revisit.", srcs)
    assert ok, bad

    # An invented measurement is still caught, even with sources present.
    ok, bad = validate_against_sources(
        "LISS-III measured 4,120.50 hectares of flooding.", srcs)
    assert not ok and any(_canon(b) == "4120.5" for b in bad), bad

    # A citation year is a reference, not a measured quantity.
    ok, bad = validate_against_sources("Xu (2006) introduced MNDWI.", srcs)
    assert ok, bad

    print("validator: ok  fabricated numerals, claims and figures rejected")


if __name__ == "__main__":
    _demo()
