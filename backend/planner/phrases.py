"""Reply templates per language.

Tier C has no model, so replies are templates -- one set per supported language.
Every template takes its numbers as parameters; no template contains a numeral of
its own. That is what lets the numeral validator keep working unchanged across all
languages: the figures come from the kernel in every case, and the words around
them are the only thing that varies.

Tiers A/B replace this file with VLM prose in the same language. The numbers are
still passed in, and still validated, so a translation cannot alter a figure.
"""

from __future__ import annotations

# Languages we have reviewed templates for. Anything else falls back to English
# with an explicit note -- silently answering in the wrong language is worse than
# saying we do not speak it yet.
SUPPORTED = ("en", "hi", "hinglish", "pa", "bn", "ta", "te")

T = {
    "en": {
        "area": "{ha} hectares of {label} were measured in {scene}, covering {pct}% of the scene.",
        "change": "{delta} hectares of new {label} appeared in {scene}: {b_ha} ha on {b_date} rising to {a_ha} ha on {a_date}.",
        "absent": "No {label} was detected in {scene}. {reason}",
        "method": "Method: {index} computed per pixel, thresholded at {thr} by Otsu's method on this scene's own histogram, then converted to area at {px} m2 per pixel.",
        "arith": "Arithmetic: {arith}.",
        "sens": "Threshold sensitivity: moving the threshold by plus-or-minus {w} index units puts the area between {lo} and {hi} hectares.",
        "caveat": "Caveat: {reason}",
        "conf": "Confidence: {band} ({score}). {expl}",
        "cannot": "I cannot answer this from {scene}.",
        "rec": " Recommended instrument: {rec}.",
    },
    "hi": {
        "area": "{scene} में {label} का क्षेत्रफल {ha} हेक्टेयर मापा गया, जो दृश्य का {pct}% है।",
        "change": "{scene} में {delta} हेक्टेयर नया {label} दिखा: {b_date} को {b_ha} हेक्टेयर से बढ़कर {a_date} को {a_ha} हेक्टेयर।",
        "absent": "{scene} में कोई {label} नहीं मिला। {reason}",
        "method": "विधि: {index} प्रति पिक्सेल गणना, Otsu विधि से {thr} पर सीमा निर्धारित, फिर {px} वर्ग मीटर प्रति पिक्सेल की दर से क्षेत्रफल।",
        "arith": "गणना: {arith}।",
        "sens": "सीमा संवेदनशीलता: सीमा को {w} इकाई ऊपर-नीचे करने पर क्षेत्रफल {lo} से {hi} हेक्टेयर के बीच रहता है।",
        "caveat": "सावधानी: {reason}",
        "conf": "विश्वसनीयता: {band} ({score})। {expl}",
        "cannot": "मैं {scene} से इसका उत्तर नहीं दे सकता।",
        "rec": " सुझाया गया उपकरण: {rec}।",
    },
    "hinglish": {
        "area": "{scene} mein {label} ka area {ha} hectare measure hua, jo scene ka {pct}% hai.",
        "change": "{scene} mein {delta} hectare naya {label} aaya: {b_date} ko {b_ha} ha se badhkar {a_date} ko {a_ha} ha.",
        "absent": "{scene} mein koi {label} nahi mila. {reason}",
        "method": "Method: {index} har pixel par compute kiya, Otsu se {thr} par threshold, phir {px} m2 per pixel se area nikala.",
        "arith": "Calculation: {arith}.",
        "sens": "Threshold sensitivity: threshold ko {w} unit upar-neeche karne par area {lo} se {hi} hectare ke beech rehta hai.",
        "caveat": "Dhyan dein: {reason}",
        "conf": "Confidence: {band} ({score}). {expl}",
        "cannot": "Main {scene} se iska jawab nahi de sakta.",
        "rec": " Suggested instrument: {rec}.",
    },
    "pa": {
        "area": "{scene} ਵਿੱਚ {label} ਦਾ ਖੇਤਰਫਲ {ha} ਹੈਕਟੇਅਰ ਮਾਪਿਆ ਗਿਆ, ਜੋ ਦ੍ਰਿਸ਼ ਦਾ {pct}% ਹੈ।",
        "change": "{scene} ਵਿੱਚ {delta} ਹੈਕਟੇਅਰ ਨਵਾਂ {label} ਦਿਖਿਆ: {b_date} ਨੂੰ {b_ha} ਹੈਕਟੇਅਰ ਤੋਂ ਵਧ ਕੇ {a_date} ਨੂੰ {a_ha} ਹੈਕਟੇਅਰ।",
        "absent": "{scene} ਵਿੱਚ ਕੋਈ {label} ਨਹੀਂ ਮਿਲਿਆ। {reason}",
        "method": "ਵਿਧੀ: {index} ਹਰ ਪਿਕਸਲ ਲਈ ਗਿਣਿਆ, Otsu ਨਾਲ {thr} ਉੱਤੇ ਸੀਮਾ, ਫਿਰ {px} ਵਰਗ ਮੀਟਰ ਪ੍ਰਤੀ ਪਿਕਸਲ ਨਾਲ ਖੇਤਰਫਲ।",
        "arith": "ਗਣਨਾ: {arith}।",
        "sens": "ਸੀਮਾ ਸੰਵੇਦਨਸ਼ੀਲਤਾ: ਸੀਮਾ {w} ਇਕਾਈ ਬਦਲਣ ਤੇ ਖੇਤਰਫਲ {lo} ਤੋਂ {hi} ਹੈਕਟੇਅਰ ਵਿਚਕਾਰ ਰਹਿੰਦਾ ਹੈ।",
        "caveat": "ਧਿਆਨ: {reason}",
        "conf": "ਭਰੋਸਾ: {band} ({score})। {expl}",
        "cannot": "ਮੈਂ {scene} ਤੋਂ ਇਸਦਾ ਜਵਾਬ ਨਹੀਂ ਦੇ ਸਕਦਾ।",
        "rec": " ਸੁਝਾਇਆ ਯੰਤਰ: {rec}।",
    },
    "bn": {
        "area": "{scene}-এ {label}-এর ক্ষেত্রফল {ha} হেক্টর মাপা হয়েছে, যা দৃশ্যের {pct}%।",
        "change": "{scene}-এ {delta} হেক্টর নতুন {label} দেখা গেছে: {b_date}-এ {b_ha} হেক্টর থেকে বেড়ে {a_date}-এ {a_ha} হেক্টর।",
        "absent": "{scene}-এ কোনো {label} পাওয়া যায়নি। {reason}",
        "method": "পদ্ধতি: {index} প্রতি পিক্সেলে গণনা, Otsu দিয়ে {thr}-এ সীমা, তারপর {px} বর্গমিটার প্রতি পিক্সেল হারে ক্ষেত্রফল।",
        "arith": "গণনা: {arith}।",
        "sens": "সীমা সংবেদনশীলতা: সীমা {w} একক সরালে ক্ষেত্রফল {lo} থেকে {hi} হেক্টরের মধ্যে থাকে।",
        "caveat": "সতর্কতা: {reason}",
        "conf": "আস্থা: {band} ({score})। {expl}",
        "cannot": "আমি {scene} থেকে এর উত্তর দিতে পারি না।",
        "rec": " প্রস্তাবিত যন্ত্র: {rec}।",
    },
    "ta": {
        "area": "{scene} இல் {label} பரப்பளவு {ha} ஹெக்டேர் அளவிடப்பட்டது, இது காட்சியின் {pct}%.",
        "change": "{scene} இல் {delta} ஹெக்டேர் புதிய {label} தோன்றியது: {b_date} அன்று {b_ha} ஹெக்டேரிலிருந்து {a_date} அன்று {a_ha} ஹெக்டேராக.",
        "absent": "{scene} இல் {label} எதுவும் கண்டறியப்படவில்லை. {reason}",
        "method": "முறை: {index} ஒவ்வொரு பிக்சலுக்கும் கணக்கிடப்பட்டது, Otsu மூலம் {thr} இல் வரம்பு, பின்னர் ஒரு பிக்சலுக்கு {px} சதுர மீட்டர் வீதம் பரப்பளவு.",
        "arith": "கணக்கீடு: {arith}.",
        "sens": "வரம்பு உணர்திறன்: வரம்பை {w} அலகு நகர்த்தினால் பரப்பளவு {lo} முதல் {hi} ஹெக்டேர் வரை இருக்கும்.",
        "caveat": "எச்சரிக்கை: {reason}",
        "conf": "நம்பகத்தன்மை: {band} ({score}). {expl}",
        "cannot": "{scene} இலிருந்து இதற்கு பதிலளிக்க முடியவில்லை.",
        "rec": " பரிந்துரைக்கப்பட்ட கருவி: {rec}.",
    },
    "te": {
        "area": "{scene} లో {label} విస్తీర్ణం {ha} హెక్టార్లు కొలవబడింది, ఇది దృశ్యంలో {pct}%.",
        "change": "{scene} లో {delta} హెక్టార్ల కొత్త {label} కនిపించింది: {b_date} నాడు {b_ha} హెక్టార్ల నుండి {a_date} నాడు {a_ha} హెక్టార్లకు.",
        "absent": "{scene} లో {label} ఏమీ కనుగొనబడలేదు. {reason}",
        "method": "పద్ధతి: {index} ప్రతి పిక్సెల్‌కు లెక్కించబడింది, Otsu ద్వారా {thr} వద్ద పరిమితి, ఆపై పిక్సెల్‌కు {px} చదరపు మీటర్ల చొప్పున విస్తీర్ణం.",
        "arith": "గణన: {arith}.",
        "sens": "పరిమితి సున్నితత్వం: పరిమితిని {w} యూనిట్లు మార్చితే విస్తీర్ణం {lo} నుండి {hi} హెక్టార్ల మధ్య ఉంటుంది.",
        "caveat": "గమనిక: {reason}",
        "conf": "విశ్వసనీయత: {band} ({score}). {expl}",
        "cannot": "{scene} నుండి దీనికి సమాధానం ఇవ్వలేను.",
        "rec": " సూచించిన పరికరం: {rec}.",
    },
}

# Class labels, translated. Kept apart from the sentence templates because the
# same label appears in several of them.
LABELS = {
    "en": {},
    "hi": {"flood water": "बाढ़ का पानी", "water": "पानी",
           "healthy vegetation": "स्वस्थ वनस्पति", "stressed vegetation": "प्रभावित फसल",
           "built-up land": "निर्मित क्षेत्र", "burn scar": "जला हुआ क्षेत्र"},
    "hinglish": {"flood water": "flood ka paani", "water": "paani",
                 "healthy vegetation": "healthy hariyali", "stressed vegetation": "kharab fasal",
                 "built-up land": "built-up ilaka", "burn scar": "jala hua ilaka"},
    "pa": {"flood water": "ਹੜ੍ਹ ਦਾ ਪਾਣੀ", "water": "ਪਾਣੀ",
           "healthy vegetation": "ਸਿਹਤਮੰਦ ਬਨਸਪਤੀ", "stressed vegetation": "ਖਰਾਬ ਫਸਲ",
           "built-up land": "ਉਸਾਰੀ ਖੇਤਰ", "burn scar": "ਸੜਿਆ ਖੇਤਰ"},
    "bn": {"flood water": "বন্যার জল", "water": "জল",
           "healthy vegetation": "সুস্থ গাছপালা", "stressed vegetation": "ক্ষতিগ্রস্ত ফসল",
           "built-up land": "নির্মিত এলাকা", "burn scar": "পোড়া এলাকা"},
    "ta": {"flood water": "வெள்ள நீர்", "water": "நீர்",
           "healthy vegetation": "ஆரோக்கிய தாவரம்", "stressed vegetation": "பாதிக்கப்பட்ட பயிர்",
           "built-up land": "கட்டிட பகுதி", "burn scar": "எரிந்த பகுதி"},
    "te": {"flood water": "వరద నీరు", "water": "నీరు",
           "healthy vegetation": "ఆరోగ్యకరమైన వృక్షసంపద", "stressed vegetation": "దెబ్బతిన్న పంట",
           "built-up land": "నిర్మిత ప్రాంతం", "burn scar": "కాలిన ప్రాంతం"},
}


def get(lang: str) -> dict:
    """Template set for `lang`, falling back to English."""
    return T.get(lang, T["en"])


def label_for(lang: str, label: str) -> str:
    """Translate a class label, leaving it in English when we have no term."""
    return LABELS.get(lang, {}).get(label, label)


def _demo() -> None:
    # Every language must define every key -- a missing one would KeyError at
    # request time rather than at import, which is the worst place to find it.
    keys = set(T["en"])
    for lang, t in T.items():
        assert set(t) == keys, f"{lang} missing {keys - set(t)}"
    # No template may contain a measured quantity as a literal: numbers arrive as
    # parameters from the kernel, and a literal here would be a figure nobody
    # measured. Unit tokens ("m2") are exempt -- they name a unit, not a value.
    UNIT_TOKENS = ("m2", "km2")
    for lang, t in T.items():
        for k, v in t.items():
            stripped = v
            for u in UNIT_TOKENS:
                stripped = stripped.replace(u, "")
            assert not any(c.isdigit() for c in stripped), \
                f"{lang}.{k} has a literal digit"
    assert set(SUPPORTED) == set(T), "SUPPORTED and T disagree"
    # Every label set must cover the same classes English does, or a query in
    # that language silently falls back to an English noun mid-sentence.
    for lang, m in LABELS.items():
        if lang == "en":
            continue
        assert set(m) == set(LABELS["hi"]), f"{lang} label set differs"
    print(f"phrases: ok  {len(T)} languages x {len(keys)} templates, no literal numerals")


if __name__ == "__main__":
    _demo()
