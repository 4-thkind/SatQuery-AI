"""Place-name recognition and coverage checking.

The problem this solves: a question about a place we hold no imagery for used to
be answered anyway, silently, using whichever scene happened to be selected. Ask
"how much flooding in Assam" while the Bihar scene is open and you got a Bihar
number under an Assam question. That is the exact failure mode this project
exists to prevent -- a plausible number attached to the wrong thing.

So: recognise the place, check it against what we actually hold, and refuse by
name when we do not hold it. Refusing is cheap; a wrong district in a flood
report is not.

Coverage here is deliberately small and local. Global coverage means a live
imagery API, which would put a network dependency in the request path and break
the offline guarantee the whole system is built on.
"""

from __future__ import annotations

import re
import unicodedata

# Districts and states we recognise by name, in the scripts people type them in.
# Recognising a place is NOT the same as covering it -- see COVERED below.
PLACE_ALIASES = {
    "supaul": ["supaul", "सुपौल", "ਸੁਪੌਲ", "সুপৌল"],
    "bihar": ["bihar", "बिहार", "ਬਿਹਾਰ", "বিহার"],
    "kosi": ["kosi", "koshi", "कोसी", "कोशी", "ਕੋਸੀ", "কোসী"],
    "assam": ["assam", "असम", "अस्साम", "ਅਸਾਮ", "অসম"],
    "kerala": ["kerala", "केरल", "ਕੇਰਲ", "কেরালা", "കേരളം"],
    "odisha": ["odisha", "orissa", "ओडिशा", "ଓଡ଼ିଶା", "ଓଡିଶା"],
    "punjab": ["punjab", "पंजाब", "ਪੰਜਾਬ", "পাঞ্জাব"],
    "gujarat": ["gujarat", "गुजरात", "ગુજરાત"],
    "maharashtra": ["maharashtra", "महाराष्ट्र"],
    "tamil nadu": ["tamil nadu", "tamilnadu", "तमिलनाडु", "தமிழ்நாடு"],
    "west bengal": ["west bengal", "पश्चिम बंगाल", "পশ্চিমবঙ্গ"],
    "uttarakhand": ["uttarakhand", "उत्तराखंड"],
    "delhi": ["delhi", "दिल्ली", "ਦਿੱਲੀ"],
    "mumbai": ["mumbai", "bombay", "मुंबई"],
    "chennai": ["chennai", "चेन्नई", "சென்னை"],
    "sundarbans": ["sundarban", "sundarbans", "सुंदरबन", "সুন্দরবন"],
    "brahmaputra": ["brahmaputra", "ब्रह्मपुत्र", "ব্রহ্মপুত্র"],
    "ganga": ["ganga", "ganges", "गंगा", "গঙ্গা"],
}

# What we actually hold imagery for. Everything else is recognised but refused.
# Keep this derived from the manifest in spirit: if a scene is added for a new
# district, its name belongs here too.
COVERED = {"supaul", "bihar", "kosi"}

# Human-readable names for the refusal message.
DISPLAY = {
    "supaul": "Supaul", "bihar": "Bihar", "kosi": "the Kosi basin",
    "assam": "Assam", "kerala": "Kerala", "odisha": "Odisha",
    "punjab": "Punjab", "gujarat": "Gujarat", "maharashtra": "Maharashtra",
    "tamil nadu": "Tamil Nadu", "west bengal": "West Bengal",
    "uttarakhand": "Uttarakhand", "delhi": "Delhi", "mumbai": "Mumbai",
    "chennai": "Chennai", "sundarbans": "the Sundarbans",
    "brahmaputra": "the Brahmaputra basin", "ganga": "the Ganga basin",
}


def detect_all(query: str) -> list[str]:
    """Return all canonical places named in `query`."""
    q = f" {unicodedata.normalize('NFKC', query.lower())} "
    found = []
    for canon, aliases in PLACE_ALIASES.items():
        for a in aliases:
            if re.search(rf"(?<![a-zA-Z0-9]){re.escape(a)}(?![a-zA-Z0-9])", q):
                if canon not in found:
                    found.append(canon)
                break
    return found


def detect(query: str) -> str | None:
    """Return the canonical place named in `query`, or None if none is named.

    Prioritises uncovered places so that compound queries mentioning an uncovered
    place (e.g. "Bihar and Assam") are caught and refused rather than answering from
    whichever scene happens to be loaded.
    """
    places = detect_all(query)
    if not places:
        return None
    uncovered = [p for p in places if p not in COVERED]
    if uncovered:
        return uncovered[0]
    return places[0]


def is_covered(place: str | None) -> bool:
    """True when we hold imagery for `place`. None means no place was named, in
    which case the selected scene is the subject and there is nothing to check."""
    return place is None or place in COVERED


def coverage_message(place: str, covered_places: list[str]) -> str:
    """Why we will not answer, and what we do hold. Named, not vague."""
    name = DISPLAY.get(place, place.title())
    have = ", ".join(sorted(covered_places))
    return (f"This deployment holds no imagery for {name}. Answering from the "
            f"currently selected scene would attach a number measured somewhere "
            f"else to a question about {name}, so it is refused. Imagery loaded: "
            f"{have}. Adding {name} needs the corresponding scene ingested -- the "
            f"analysis path itself is unchanged.")


def _demo() -> None:
    assert detect("how much flooding in Assam") == "assam"
    assert detect("असम में बाढ़") == "assam"
    assert detect("ਸੁਪੌਲ ਵਿੱਚ ਪਾਣੀ") == "supaul"
    assert detect("how much water here") is None
    # Longest alias must win, or "west bengal" resolves to plain "bengal".
    assert detect("flooding in west bengal") == "west bengal"

    # Language collision: "বাংলা" (Bengali language) must not trigger West Bengal
    assert detect("please answer in Bengali (বাংলায়)") is None
    assert detect("বাংলা ভাষায় উত্তর দাও") is None

    # Compound query: naming a covered and an uncovered place must catch the uncovered place
    assert detect("Compare the flooding in Bihar and Assam this monsoon") == "assam"

    assert is_covered("supaul") and is_covered(None)
    assert not is_covered("assam")

    m = coverage_message("assam", ["Supaul, Bihar"])
    assert "Assam" in m and "Supaul" in m and "refused" in m
    print(f"places: ok  {len(PLACE_ALIASES)} places, {len(COVERED)} covered")


if __name__ == "__main__":
    _demo()
