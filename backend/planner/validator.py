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
ALWAYS_OK = {"0", "1", "2", "3", "4", "5", "10", "100", "1000", "10000"}


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


def validate_narration(text: str, facts: dict, extra: list = ()) -> tuple[bool, list[str]]:
    """Return (ok, offending numerals)."""
    allowed = collect_facts(facts, extra)
    bad = [tok for tok in NUMERAL.findall(text) if _canon(tok) not in allowed]
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

    # A number that merely looks plausible is still caught.
    ok, bad = validate_narration("The area is 2,700.00 hectares.", facts)
    assert not ok and any(_canon(b) == "2700" for b in bad), bad

    # Facts reachable through nested structures count as computed.
    nested = {"sens": {"+0.05": {"hectares": 2599.4}}}
    ok, bad = validate_narration("as low as 2,599.4 ha", nested)
    assert ok, bad

    print("validator: ok  fabricated numerals rejected")


if __name__ == "__main__":
    _demo()
