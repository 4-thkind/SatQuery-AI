"""Query language detection and reply-language selection.

The rule this module exists to enforce: an answer comes back in the language the
question was asked in. A Punjabi question answered in English is a worse failure
than it looks -- the person who most needs a flood figure in Punjabi is exactly
the person who cannot read the English one.

Detection is by Unicode script range, which is exact for the Indic scripts (they
occupy disjoint blocks), plus a romanised-marker pass for Hinglish, which shares
the Latin block with English and so cannot be detected by script alone.
"""

from __future__ import annotations

import unicodedata

# Unicode block ranges. These are disjoint by construction, so a single character
# in one of them identifies the script with no ambiguity.
SCRIPT_RANGES = {
    "hi": [(0x0900, 0x097F)],            # Devanagari -- Hindi, Marathi, Nepali
    "bn": [(0x0980, 0x09FF)],            # Bengali / Assamese
    "pa": [(0x0A00, 0x0A7F)],            # Gurmukhi -- Punjabi
    "gu": [(0x0A80, 0x0AFF)],            # Gujarati
    "or": [(0x0B00, 0x0B7F)],            # Odia
    "ta": [(0x0B80, 0x0BFF)],            # Tamil
    "te": [(0x0C00, 0x0C7F)],            # Telugu
    "kn": [(0x0C80, 0x0CFF)],            # Kannada
    "ml": [(0x0D00, 0x0D7F)],            # Malayalam
}

LANGUAGE_NAMES = {
    "en": "English", "hi": "हिन्दी", "bn": "বাংলা", "pa": "ਪੰਜਾਬੀ",
    "gu": "ગુજરાતી", "or": "ଓଡ଼ିଆ", "ta": "தமிழ்", "te": "తెలుగు",
    "kn": "ಕನ್ನಡ", "ml": "മലയാളം", "hinglish": "Hinglish",
}

# Romanised Hindi typed in Latin script. Detected by marker words rather than by
# script, since Hinglish and English are indistinguishable at the codepoint level.
# Only function words and very common nouns -- a marker that also reads as English
# would misclassify plain English queries.
HINGLISH_MARKERS = [
    "kitna", "kitne", "kitni", "hai", "hain", "kya", "kaisa", "kaisi", "mein",
    "me hai", "batao", "bata", "dikhao", "karo", "nahi", "nahin", "aur",
    "zyada", "kam", "pehle", "baad", "abhi", "yahan", "wahan", "paani",
    "baadh", "badh", "sheher", "shehar", "khet", "fasal", "hariyali", "jagah",
    "sukha", "aag", "jala", "nadi", "talab", "ilaka", "kitna area",
]


def detect(query: str) -> str:
    """Return a language code for `query`.

    Script wins over markers: a query containing Devanagari is Hindi even if it
    also contains English words, because the reply has to be readable by someone
    typing Devanagari.
    """
    counts: dict[str, int] = {}
    for ch in query:
        cp = ord(ch)
        for code, ranges in SCRIPT_RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[code] = counts.get(code, 0) + 1
                break
    if counts:
        return max(counts, key=counts.get)

    low = f" {unicodedata.normalize('NFKC', query.lower())} "
    if sum(1 for m in HINGLISH_MARKERS if f" {m} " in low or f" {m}" in low) >= 1:
        return "hinglish"
    return "en"


def label(code: str) -> str:
    """Human-readable name for the header badge."""
    return LANGUAGE_NAMES.get(code, code.upper())


def _demo() -> None:
    cases = [
        ("How much area is flooded?", "en"),
        ("kitna area baadh me hai", "hinglish"),
        ("paani kitna hai", "hinglish"),
        ("बाढ़ का क्षेत्र कितना है", "hi"),
        ("ਪਾਣੀ ਕਿੰਨਾ ਹੈ", "pa"),
        ("পানি কত আছে", "bn"),
        ("నీరు ఎంత", "te"),
        ("தண்ணீர் எவ்வளவு", "ta"),
        ("ಎಷ್ಟು ನೀರು", "kn"),
        ("show me the burn scar", "en"),
    ]
    for q, want in cases:
        got = detect(q)
        assert got == want, f"{q!r} -> {got}, want {want}"
    # Mixed script must follow the script, not the English words in it.
    assert detect("flood area कितना है") == "hi"
    print(f"language: ok  {len(cases)} queries across {len(SCRIPT_RANGES)} scripts")


if __name__ == "__main__":
    _demo()
