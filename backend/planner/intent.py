"""Intent classification. Spec section 8.5.

Lexicon-based, bilingual EN / Hindi / Hinglish. At Tier A/B the VLM classifies
instead, but the intent VOCABULARY is shared, so a tier switch cannot change
which tools run -- only how the plan is phrased.
"""

from __future__ import annotations

import re
import unicodedata

# intent -> trigger terms. Hinglish is transliterated, not translated: people
# actually type "paani kitna hai", not "जल क्षेत्र".
INTENT_LEXICON = {
    "flood_extent": [
        "flood", "flooded", "inundation", "inundated", "submerged", "deluge",
        "baadh", "badh", "बाढ़", "जलमग्न", "flood extent", "flooding",
        "ਹੜ੍ਹ", "ਹੜ", "বন্যা", "வெள்ளம்", "వరద", "ಪ್ರವಾಹ", "വെള്ളപ്പൊക്കം",
    ],
    "water_extent": [
        "water", "waterbody", "water body", "lake", "reservoir", "river", "pond",
        "tank", "paani", "pani", "jal", "पानी", "जल", "झील", "नदी", "talab",
        "ਪਾਣੀ", "ਦਰਿਆ", "পানি", "জল", "নদী", "தண்ணீர்", "நீர்", "ஆறு",
        "నీరు", "నది", "ನೀರು", "ನದಿ", "വെള്ളം", "പുഴ",
    ],
    "vegetation_health": [
        "vegetation", "ndvi", "green", "greenery", "forest", "crop health",
        "vegetation health", "healthy", "canopy", "hariyali", "हरियाली",
        "वनस्पति", "फसल", "khet", "fasal",
        "ਫਸਲ", "ਹਰਿਆਲੀ", "ਬਨਸਪਤੀ", "ফসল", "গাছপালা", "সবুজ",
        "பயிர்", "தாவரம்", "పంట", "వృక్ష", "ಬೆಳೆ", "വിള",
    ],
    "crop_stress": [
        "crop stress", "stressed", "drought", "wilting", "yield", "sukha",
        "सूखा", "crop damage", "fasal nuksan",
    ],
    "builtup_extent": [
        "built", "built-up", "builtup", "urban", "settlement", "construction",
        "concrete", "city", "town", "sheher", "shehar", "शहर", "निर्माण",
        "encroachment", "development",
        "ਸ਼ਹਿਰ", "ਉਸਾਰੀ", "শহর", "নির্মাণ", "நகரம்", "கட்டிடம்",
        "నగరం", "నిర్మాణ", "ನಗರ", "നഗരം",
    ],
    "burn_severity": [
        "burn", "burnt", "burned", "fire", "wildfire", "scar", "nbr",
        "आग", "जला", "aag", "jala", "forest fire",
        "ਅੱਗ", "ਸੜਿਆ", "আগুন", "পোড়া", "தீ", "எரிந்த", "అగ్ని", "కాలిన",
        "ಬೆಂಕಿ", "തീ",
    ],
    "shoreline": ["shoreline", "coastline", "coast", "erosion", "तट", "तटरेखा"],
    "object_count": ["count", "how many", "number of", "kitne", "कितने", "ginti",
                     "ਕਿੰਨੇ", "কতগুলো", "எத்தனை", "ఎన్ని", "ಎಷ್ಟು"],
    "change_detect": [
        "change", "changed", "difference", "compare", "before and after",
        "increase", "decrease", "growth", "expanded", "shrunk", "since",
        "badla", "बदलाव", "अंतर", "tulna", "versus", " vs ",
        "ਬਦਲਾਅ", "ਤਬਦੀਲੀ", "পরিবর্তন", "மாற்றம்", "மாற்றம்", "మార్పు",
        "ಬದಲಾವಣೆ", "മാറ്റം",
    ],
    "scene_describe": [
        "describe", "what is", "what's in", "overview", "summary", "tell me about",
        "kya hai", "क्या है", "batao", "बताओ",
        "ਕੀ ਹੈ", "ਦੱਸੋ", "কি আছে", "বলুন", "என்ன", "ఏమి", "ಏನು", "എന്ത്",
    ],
    "method_explain": [
        "meaning of", "what is the meaning", "meaning", "definition of", "define",
        "explain", "explanation", "how does", "why do we", "why does",
        "what does", "formula", "algorithm", "otsu", "thresholding", "methodology",
        "ka matlab", "kya hota hai", "samjhao", "matlab", "मतलब", "परिभाषा", "समझाओ",
        "how is", "how are", "how do we", "how do you", "how to", "how works",
        "computed", "calculated", "measured", "working of", "architecture", "pipeline",
        "satquery", "ledger", "guardrail", "confidence score", "masking done",
        "index computed", "area measured", "change detection done",
    ],
}

# Terms that make a query comparative regardless of its subject. Change detection
# is an OVERLAY on a subject intent ("how much MORE water"), not a rival to it.
# Comparatives live here rather than in the lexicon: "more water than before" must
# stay a WATER question that is also a change question.
CHANGE_MARKERS = INTENT_LEXICON["change_detect"] + [
    "more ", "less ", "than before", "than last", "previously", "earlier",
    "over time", "trend", "pehle", "पहले", "zyada", "ज्यादा", "kam ",
]

# Terms that indicate the user wants a pixel / area measurement on the active scene
MEASURE_MARKERS = [
    "how much", "how many", "kitna", "kitne", "in this scene", "this scene",
    "hectares", " ha ", "show me", "detect ", "calculate the", "measure the",
]

EXPLAIN_MARKERS = [
    "how is", "how are", "how does", "how do we", "how do you", "how to",
    "how works", "explain", "meaning of", "definition", "define",
    "ka matlab", "kya hota hai", "samjhao", "what is satquery", "architecture",
    "how satquery", "pipeline", "ledger", "guardrail", "formula", "algorithm",
    "methodology", "how area is measured", "how index is computed", "how masking done",
]

# Checked in order; the first match wins when scores tie. Specific before generic.
PRIORITY = ["flood_extent", "burn_severity", "builtup_extent", "crop_stress",
            "vegetation_health", "shoreline", "water_extent", "object_count",
            "change_detect", "method_explain", "scene_describe"]


def _norm(q: str) -> str:
    q = unicodedata.normalize("NFKC", q.lower())
    return re.sub(r"\s+", " ", f" {q} ")


def _term_matches(t: str, q: str) -> bool:
    # Ensure word boundaries for alphanumeric characters so that e.g.
    # "count" does not match inside "discount" or "countryside", and
    # "aag" does not match inside "aage".
    # Non-alphanumeric lookaround works across both ASCII and Indic scripts.
    return bool(re.search(rf"(?<![a-zA-Z0-9]){re.escape(t)}(?![a-zA-Z0-9])", q))


def classify(query: str) -> tuple[str, bool, dict]:
    """Return (intent, is_change_query, scores).

    is_change_query is separate because "how much more water than last year" is a
    water question AND a change question. Collapsing them loses the subject.
    """
    q = _norm(query)
    scores: dict[str, int] = {}
    for intent, terms in INTENT_LEXICON.items():
        hits = sum(1 for t in terms if _term_matches(t, q))
        if hits:
            scores[intent] = hits

    is_change = any(_term_matches(t, q) for t in CHANGE_MARKERS)
    is_measure = any(_term_matches(m, q) for m in MEASURE_MARKERS)
    is_explain = any(_term_matches(e, q) for e in EXPLAIN_MARKERS)

    # Explanatory / conceptual query: definition, meaning, or algorithm without scene measurement
    if (is_explain or "method_explain" in scores) and not is_measure:
        return "method_explain", False, scores

    subject = {k: v for k, v in scores.items()
               if k not in ("change_detect", "scene_describe", "method_explain")}
    if subject:
        best = max(subject.values())
        for intent in PRIORITY:
            if subject.get(intent) == best:
                return intent, is_change, scores
    if is_change:
        return "change_detect", True, scores
    if "method_explain" in scores:
        return "method_explain", False, scores
    return "scene_describe", False, scores


def _demo() -> None:
    cases = [
        ("How much area is flooded in this scene?", "flood_extent", False),
        ("kitna area baadh me hai", "flood_extent", False),
        ("बाढ़ का क्षेत्रफल कितना है", "flood_extent", False),
        ("What is the water extent?", "water_extent", False),
        ("paani kitna hai", "water_extent", False),
        ("How much more water than before?", "water_extent", True),
        ("Compare built-up area between the two dates", "builtup_extent", True),
        ("show me vegetation health", "vegetation_health", False),
        ("hariyali kaisi hai", "vegetation_health", False),
        ("burnt forest area", "burn_severity", False),
        ("describe this scene", "scene_describe", False),
        ("what changed since last year", "change_detect", True),
        ("what id the meaning of otsu", "method_explain", False),
        ("what is otsu", "method_explain", False),
        ("explain ndvi", "method_explain", False),
        ("otsu ka matlab kya hai", "method_explain", False),
        ("how does masking done", "method_explain", False),
        ("how index is computed", "method_explain", False),
        ("how area is measured", "method_explain", False),
        ("how do we compute ndvi", "method_explain", False),
        ("how is change detection done", "method_explain", False),
        ("what is the evidence ledger", "method_explain", False),
        ("how does satquery work", "method_explain", False),
    ]
    for q, want_intent, want_change in cases:
        got, change, scores = classify(q)
        assert got == want_intent, f"{q!r} -> {got}, want {want_intent} ({scores})"
        assert change == want_change, f"{q!r} change={change}, want {want_change}"

    # Word boundary guard: substrings must not trigger false intents
    disc_intent, _, disc_scores = classify("What is the current discount on satellite imagery licensing?")
    assert disc_intent != "object_count" and "object_count" not in disc_scores, f"discount matched: {disc_scores}"

    aage_intent, _, aage_scores = classify("Aage kya dikhna chahiye is scene mein?")
    assert aage_intent != "burn_severity" and "burn_severity" not in aage_scores, f"aage matched: {aage_scores}"

    count_intent, _, count_scores = classify("Tell me about the countryside around this village")
    assert count_intent != "object_count" and "object_count" not in count_scores, f"countryside matched: {count_scores}"

    print(f"intent: ok  {len(cases)} queries incl. Hindi and Hinglish")


if __name__ == "__main__":
    _demo()
