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
        "overview": "{scene} — scene overview from {n} spectral {word}:",
        "index_one": "index",
        "index_many": "indices",
        "index_line": "{index} averages {mean} across the scene (range {lo} to {hi})",
        "ledger_note": "Per-pixel statistics for each index are in the evidence ledger. Ask for a specific class (water, vegetation, built-up) to get a measured area in hectares.",
        "done": "{scene}: analysis completed.",
        "cited_en": "[Note: Methodological corpus text is cited in English from published literature.]",
        "conf_expl": "Product of five measured components; the limiting factor is {weakest} at {value}.",
        "conf_floored": " That component is unusable here, so the score is reported against a {floor} floor rather than collapsing to zero; treat the measurement as indicative only.",
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
        "overview": "{scene} — {n} स्पेक्ट्रल {word} से दृश्य का सारांश:",
        "index_one": "सूचकांक",
        "index_many": "सूचकांकों",
        "index_line": "{index} का औसत पूरे दृश्य में {mean} है (सीमा {lo} से {hi})",
        "ledger_note": "हर सूचकांक के प्रति-पिक्सेल आँकड़े साक्ष्य बही में दर्ज हैं। हेक्टेयर में मापा गया क्षेत्रफल पाने के लिए कोई विशेष श्रेणी पूछें (पानी, वनस्पति, निर्मित क्षेत्र)।",
        "done": "{scene}: विश्लेषण पूरा हुआ।",
        "cited_en": "[सूचना: पद्धति से जुड़ा संदर्भ पाठ प्रकाशित साहित्य से अंग्रेज़ी में उद्धृत है।]",
        "conf_expl": "पाँच मापे गए घटकों का गुणनफल; सबसे कमज़ोर घटक {weakest} है, जिसका मान {value} है।",
        "conf_floored": " यह घटक यहाँ अनुपयोगी है, इसलिए स्कोर शून्य होने के बजाय {floor} की न्यूनतम सीमा पर दिया गया है; माप को केवल संकेतात्मक मानें।",
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
        "overview": "{scene} — {n} spectral {word} se scene ka overview:",
        "index_one": "index",
        "index_many": "indices",
        "index_line": "{index} ka average pure scene mein {mean} hai (range {lo} se {hi})",
        "ledger_note": "Har index ke per-pixel statistics evidence ledger mein hain. Hectare mein measured area ke liye koi specific class poochein (paani, vegetation, built-up).",
        "done": "{scene}: analysis complete ho gaya.",
        "cited_en": "[Note: Methodology ka reference text published literature se English mein cite kiya gaya hai.]",
        "conf_expl": "Paanch measured components ka product; sabse weak component {weakest} hai, value {value}.",
        "conf_floored": " Ye component yahan unusable hai, isliye score zero hone ke bajay {floor} ke floor par diya gaya hai; measurement ko sirf indicative maanein.",
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
        "overview": "{scene} — {n} ਸਪੈਕਟਰਲ {word} ਤੋਂ ਦ੍ਰਿਸ਼ ਦਾ ਸਾਰ:",
        "index_one": "ਸੂਚਕਾਂਕ",
        "index_many": "ਸੂਚਕਾਂਕਾਂ",
        "index_line": "{index} ਦਾ ਔਸਤ ਪੂਰੇ ਦ੍ਰਿਸ਼ ਵਿੱਚ {mean} ਹੈ (ਸੀਮਾ {lo} ਤੋਂ {hi})",
        "ledger_note": "ਹਰ ਸੂਚਕਾਂਕ ਦੇ ਪ੍ਰਤੀ-ਪਿਕਸਲ ਅੰਕੜੇ ਸਬੂਤ ਬਹੀ ਵਿੱਚ ਹਨ। ਹੈਕਟੇਅਰ ਵਿੱਚ ਮਾਪਿਆ ਖੇਤਰਫਲ ਲੈਣ ਲਈ ਕੋਈ ਖਾਸ ਸ਼੍ਰੇਣੀ ਪੁੱਛੋ (ਪਾਣੀ, ਬਨਸਪਤੀ, ਉਸਾਰੀ)।",
        "done": "{scene}: ਵਿਸ਼ਲੇਸ਼ਣ ਪੂਰਾ ਹੋਇਆ।",
        "cited_en": "[ਸੂਚਨਾ: ਵਿਧੀ ਨਾਲ ਜੁੜਿਆ ਹਵਾਲਾ ਪਾਠ ਪ੍ਰਕਾਸ਼ਿਤ ਸਾਹਿਤ ਤੋਂ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਦਿੱਤਾ ਗਿਆ ਹੈ।]",
        "conf_expl": "ਪੰਜ ਮਾਪੇ ਗਏ ਹਿੱਸਿਆਂ ਦਾ ਗੁਣਨਫਲ; ਸਭ ਤੋਂ ਕਮਜ਼ੋਰ ਹਿੱਸਾ {weakest} ਹੈ, ਜਿਸਦਾ ਮੁੱਲ {value} ਹੈ।",
        "conf_floored": " ਇਹ ਹਿੱਸਾ ਇੱਥੇ ਵਰਤੋਂਯੋਗ ਨਹੀਂ, ਇਸ ਲਈ ਸਕੋਰ ਸਿਫ਼ਰ ਹੋਣ ਦੀ ਥਾਂ {floor} ਦੀ ਹੇਠਲੀ ਸੀਮਾ ਉੱਤੇ ਦਿੱਤਾ ਗਿਆ ਹੈ; ਮਾਪ ਨੂੰ ਸਿਰਫ਼ ਸੰਕੇਤਕ ਮੰਨੋ।",
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
        "overview": "{scene} — {n}টি স্পেকট্রাল {word} থেকে দৃশ্যের সারসংক্ষেপ:",
        "index_one": "সূচক",
        "index_many": "সূচক",
        "index_line": "{index}-এর গড় পুরো দৃশ্যে {mean} (পরিসর {lo} থেকে {hi})",
        "ledger_note": "প্রতিটি সূচকের প্রতি-পিক্সেল পরিসংখ্যান প্রমাণ খাতায় আছে। হেক্টরে মাপা ক্ষেত্রফল পেতে নির্দিষ্ট শ্রেণি জিজ্ঞাসা করুন (জল, গাছপালা, নির্মিত এলাকা)।",
        "done": "{scene}: বিশ্লেষণ সম্পন্ন হয়েছে।",
        "cited_en": "[দ্রষ্টব্য: পদ্ধতি সংক্রান্ত উদ্ধৃত পাঠ প্রকাশিত সাহিত্য থেকে ইংরেজিতে দেওয়া হয়েছে।]",
        "conf_expl": "পাঁচটি মাপা উপাদানের গুণফল; সবচেয়ে দুর্বল উপাদান {weakest}, যার মান {value}।",
        "conf_floored": " এই উপাদানটি এখানে অব্যবহারযোগ্য, তাই স্কোর শূন্য না হয়ে {floor} সীমায় দেওয়া হয়েছে; মাপটিকে কেবল ইঙ্গিতমূলক ধরুন।",
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
        "overview": "{scene} — {n} நிறமாலை {word} மூலம் காட்சியின் சுருக்கம்:",
        "index_one": "குறியீடு",
        "index_many": "குறியீடுகள்",
        "index_line": "{index} இன் சராசரி காட்சி முழுவதும் {mean} ஆகும் (வரம்பு {lo} முதல் {hi})",
        "ledger_note": "ஒவ்வொரு குறியீட்டின் பிக்சல் வாரியான புள்ளிவிவரங்கள் சான்று பதிவேட்டில் உள்ளன. ஹெக்டேரில் அளவிடப்பட்ட பரப்பளவு பெற ஒரு குறிப்பிட்ட வகையைக் கேளுங்கள் (நீர், தாவரம், கட்டிடப் பகுதி).",
        "done": "{scene}: பகுப்பாய்வு நிறைவடைந்தது.",
        "cited_en": "[குறிப்பு: முறை சார்ந்த மேற்கோள் உரை வெளியிடப்பட்ட இலக்கியத்திலிருந்து ஆங்கிலத்தில் தரப்பட்டுள்ளது.]",
        "conf_expl": "ஐந்து அளவிடப்பட்ட கூறுகளின் பெருக்கல்; மிகவும் பலவீனமான கூறு {weakest}, அதன் மதிப்பு {value}.",
        "conf_floored": " இந்தக் கூறு இங்கு பயன்படுத்த முடியாதது, எனவே மதிப்பெண் பூஜ்ஜியமாகாமல் {floor} என்ற கீழ் வரம்பில் தரப்பட்டுள்ளது; அளவீட்டை சுட்டிக்காட்டும் அளவில் மட்டுமே கருதவும்.",
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
        "overview": "{scene} — {n} స్పెక్ట్రల్ {word} ఆధారంగా దృశ్య సారాంశం:",
        "index_one": "సూచిక",
        "index_many": "సూచికలు",
        "index_line": "{index} సగటు మొత్తం దృశ్యంలో {mean} (పరిధి {lo} నుండి {hi})",
        "ledger_note": "ప్రతి సూచిక యొక్క పిక్సెల్‌వారీ గణాంకాలు సాక్ష్య పట్టికలో ఉన్నాయి. హెక్టార్లలో కొలిచిన విస్తీర్ణం కోసం ఒక నిర్దిష్ట వర్గాన్ని అడగండి (నీరు, వృక్షసంపద, నిర్మిత ప్రాంతం).",
        "done": "{scene}: విశ్లేషణ పూర్తయింది.",
        "cited_en": "[గమనిక: పద్ధతికి సంబంధించిన ఉల్లేఖన పాఠ్యం ప్రచురితమైన సాహిత్యం నుండి ఆంగ్లంలో ఇవ్వబడింది.]",
        "conf_expl": "ఐదు కొలిచిన భాగాల లబ్ధం; అత్యంత బలహీన భాగం {weakest}, దాని విలువ {value}.",
        "conf_floored": " ఈ భాగం ఇక్కడ ఉపయోగపడదు, కాబట్టి స్కోరు సున్నా కాకుండా {floor} కనిష్ఠ పరిమితి వద్ద ఇవ్వబడింది; కొలతను సూచనాత్మకంగా మాత్రమే పరిగణించండి.",
    },
}

# Plain-language readings of an index mean, translated.
#
# These sit here rather than in tier_c._read_index because that function built
# them with English f-strings, so a Hindi scene overview came back with every
# index line in English and only the confidence line translated. Each entry is
# (positive clause, negative clause, zero clause); "strong" is the intensifier
# prepended when |mean| >= 0.30.
#
# The three families match the index's documented zero crossing: positive means
# more of the thing it detects. No land-cover label, no position, no waterbody
# type -- validator.validate_claims rejects those and it is right to.
READINGS = {
    "en": {
        "strong": "strongly ",
        "veg": ("a {s}positive vegetation response on average",
                "on average negative, so vegetation is sparse or absent",
                "on average at the zero crossing for vegetation response"),
        "water": ("a {s}positive open-water response on average",
                  "on average negative, so most of the scene is not open water",
                  "on average at the zero crossing for open-water response"),
        "built": ("a {s}positive built-up/bare response on average",
                  "on average negative, so little built-up or bare surface",
                  "on average at the zero crossing for built-up/bare response"),
    },
    "hi": {
        "strong": "प्रबल ",
        "veg": ("औसतन {s}सकारात्मक वनस्पति प्रतिक्रिया",
                "औसतन ऋणात्मक, यानी वनस्पति विरल या अनुपस्थित है",
                "औसतन वनस्पति प्रतिक्रिया के शून्य बिंदु पर"),
        "water": ("औसतन {s}सकारात्मक खुले-जल की प्रतिक्रिया",
                  "औसतन ऋणात्मक, यानी अधिकांश दृश्य खुला जल नहीं है",
                  "औसतन खुले-जल प्रतिक्रिया के शून्य बिंदु पर"),
        "built": ("औसतन {s}सकारात्मक निर्मित/खुली सतह की प्रतिक्रिया",
                  "औसतन ऋणात्मक, यानी निर्मित या खुली सतह बहुत कम है",
                  "औसतन निर्मित/खुली सतह प्रतिक्रिया के शून्य बिंदु पर"),
    },
    "hinglish": {
        "strong": "strongly ",
        "veg": ("average mein {s}positive vegetation response",
                "average mein negative, matlab vegetation kam ya nahi hai",
                "average mein vegetation response ke zero crossing par"),
        "water": ("average mein {s}positive open-water response",
                  "average mein negative, matlab zyadatar scene open water nahi hai",
                  "average mein open-water response ke zero crossing par"),
        "built": ("average mein {s}positive built-up/bare response",
                  "average mein negative, matlab built-up ya bare surface kam hai",
                  "average mein built-up/bare response ke zero crossing par"),
    },
    "pa": {
        "strong": "ਪ੍ਰਬਲ ",
        "veg": ("ਔਸਤਨ {s}ਸਕਾਰਾਤਮਕ ਬਨਸਪਤੀ ਪ੍ਰਤੀਕਿਰਿਆ",
                "ਔਸਤਨ ਨਕਾਰਾਤਮਕ, ਯਾਨੀ ਬਨਸਪਤੀ ਘੱਟ ਜਾਂ ਗੈਰਹਾਜ਼ਰ ਹੈ",
                "ਔਸਤਨ ਬਨਸਪਤੀ ਪ੍ਰਤੀਕਿਰਿਆ ਦੇ ਸਿਫ਼ਰ ਬਿੰਦੂ ਉੱਤੇ"),
        "water": ("ਔਸਤਨ {s}ਸਕਾਰਾਤਮਕ ਖੁੱਲ੍ਹੇ-ਪਾਣੀ ਦੀ ਪ੍ਰਤੀਕਿਰਿਆ",
                  "ਔਸਤਨ ਨਕਾਰਾਤਮਕ, ਯਾਨੀ ਬਹੁਤਾ ਦ੍ਰਿਸ਼ ਖੁੱਲ੍ਹਾ ਪਾਣੀ ਨਹੀਂ ਹੈ",
                  "ਔਸਤਨ ਖੁੱਲ੍ਹੇ-ਪਾਣੀ ਪ੍ਰਤੀਕਿਰਿਆ ਦੇ ਸਿਫ਼ਰ ਬਿੰਦੂ ਉੱਤੇ"),
        "built": ("ਔਸਤਨ {s}ਸਕਾਰਾਤਮਕ ਉਸਾਰੀ/ਨੰਗੀ ਸਤ੍ਹਾ ਦੀ ਪ੍ਰਤੀਕਿਰਿਆ",
                  "ਔਸਤਨ ਨਕਾਰਾਤਮਕ, ਯਾਨੀ ਉਸਾਰੀ ਜਾਂ ਨੰਗੀ ਸਤ੍ਹਾ ਬਹੁਤ ਘੱਟ ਹੈ",
                  "ਔਸਤਨ ਉਸਾਰੀ/ਨੰਗੀ ਸਤ੍ਹਾ ਪ੍ਰਤੀਕਿਰਿਆ ਦੇ ਸਿਫ਼ਰ ਬਿੰਦੂ ਉੱਤੇ"),
    },
    "bn": {
        "strong": "প্রবল ",
        "veg": ("গড়ে {s}ধনাত্মক গাছপালার সাড়া",
                "গড়ে ঋণাত্মক, অর্থাৎ গাছপালা কম বা নেই",
                "গড়ে গাছপালার সাড়ার শূন্য বিন্দুতে"),
        "water": ("গড়ে {s}ধনাত্মক খোলা-জলের সাড়া",
                  "গড়ে ঋণাত্মক, অর্থাৎ দৃশ্যের বেশিরভাগ খোলা জল নয়",
                  "গড়ে খোলা-জলের সাড়ার শূন্য বিন্দুতে"),
        "built": ("গড়ে {s}ধনাত্মক নির্মিত/উন্মুক্ত পৃষ্ঠের সাড়া",
                  "গড়ে ঋণাত্মক, অর্থাৎ নির্মিত বা উন্মুক্ত পৃষ্ঠ খুব কম",
                  "গড়ে নির্মিত/উন্মুক্ত পৃষ্ঠের সাড়ার শূন্য বিন্দুতে"),
    },
    "ta": {
        "strong": "வலுவான ",
        "veg": ("சராசரியாக {s}நேர்மறை தாவர பதில்",
                "சராசரியாக எதிர்மறை, அதாவது தாவரம் குறைவு அல்லது இல்லை",
                "சராசரியாக தாவர பதிலின் பூஜ்ஜிய புள்ளியில்"),
        "water": ("சராசரியாக {s}நேர்மறை திறந்த-நீர் பதில்",
                  "சராசரியாக எதிர்மறை, அதாவது காட்சியின் பெரும்பகுதி திறந்த நீர் அல்ல",
                  "சராசரியாக திறந்த-நீர் பதிலின் பூஜ்ஜிய புள்ளியில்"),
        "built": ("சராசரியாக {s}நேர்மறை கட்டிட/வெற்று மேற்பரப்பு பதில்",
                  "சராசரியாக எதிர்மறை, அதாவது கட்டிடம் அல்லது வெற்று மேற்பரப்பு மிகக் குறைவு",
                  "சராசரியாக கட்டிட/வெற்று மேற்பரப்பு பதிலின் பூஜ்ஜிய புள்ளியில்"),
    },
    "te": {
        "strong": "బలమైన ",
        "veg": ("సగటున {s}ధనాత్మక వృక్ష స్పందన",
                "సగటున ఋణాత్మకం, అంటే వృక్షసంపద తక్కువ లేదా లేదు",
                "సగటున వృక్ష స్పందన శూన్య బిందువు వద్ద"),
        "water": ("సగటున {s}ధనాత్మక బహిరంగ-నీటి స్పందన",
                  "సగటున ఋణాత్మకం, అంటే దృశ్యంలో ఎక్కువ భాగం బహిరంగ నీరు కాదు",
                  "సగటున బహిరంగ-నీటి స్పందన శూన్య బిందువు వద్ద"),
        "built": ("సగటున {s}ధనాత్మక నిర్మిత/ఖాళీ ఉపరితల స్పందన",
                  "సగటున ఋణాత్మకం, అంటే నిర్మిత లేదా ఖాళీ ఉపరితలం చాలా తక్కువ",
                  "సగటున నిర్మిత/ఖాళీ ఉపరితల స్పందన శూన్య బిందువు వద్ద"),
    },
}

# Which reading family an index belongs to. An index absent from here has no
# documented sign convention, so it gets no reading rather than an invented one.
INDEX_FAMILY = {
    "ndvi": "veg", "evi": "veg", "savi": "veg",
    "ndwi": "water", "mndwi": "water",
    "ndbi": "built",
}


# Confidence component names, translated. The explanation sentence names the
# weakest component, so leaving these in English put "cloud_penalty" in the
# middle of an otherwise-Hindi sentence.
COMPONENTS = {
    "en": {"feasibility_prior": "feasibility prior",
           "cloud_penalty": "cloud penalty",
           "threshold_stability": "threshold stability",
           "radiometry_penalty": "radiometry penalty",
           "grounding_quality": "grounding quality"},
    "hi": {"feasibility_prior": "व्यवहार्यता पूर्वानुमान",
           "cloud_penalty": "बादल दंड",
           "threshold_stability": "सीमा स्थिरता",
           "radiometry_penalty": "रेडियोमेट्री दंड",
           "grounding_quality": "आधार गुणवत्ता"},
    "hinglish": {"feasibility_prior": "feasibility prior",
                 "cloud_penalty": "cloud penalty",
                 "threshold_stability": "threshold stability",
                 "radiometry_penalty": "radiometry penalty",
                 "grounding_quality": "grounding quality"},
    "pa": {"feasibility_prior": "ਵਿਹਾਰਕਤਾ ਅਨੁਮਾਨ",
           "cloud_penalty": "ਬੱਦਲ ਜੁਰਮਾਨਾ",
           "threshold_stability": "ਸੀਮਾ ਸਥਿਰਤਾ",
           "radiometry_penalty": "ਰੇਡੀਓਮੈਟਰੀ ਜੁਰਮਾਨਾ",
           "grounding_quality": "ਆਧਾਰ ਗੁਣਵੱਤਾ"},
    "bn": {"feasibility_prior": "সম্ভাব্যতা পূর্বানুমান",
           "cloud_penalty": "মেঘ জরিমানা",
           "threshold_stability": "সীমা স্থিতিশীলতা",
           "radiometry_penalty": "রেডিওমেট্রি জরিমানা",
           "grounding_quality": "ভিত্তি গুণমান"},
    "ta": {"feasibility_prior": "சாத்தியக்கூறு முன்னனுமானம்",
           "cloud_penalty": "மேக அபராதம்",
           "threshold_stability": "வரம்பு நிலைத்தன்மை",
           "radiometry_penalty": "கதிரளவை அபராதம்",
           "grounding_quality": "ஆதார தரம்"},
    "te": {"feasibility_prior": "సాధ్యత పూర్వానుమానం",
           "cloud_penalty": "మేఘ జరిమానా",
           "threshold_stability": "పరిమితి స్థిరత్వం",
           "radiometry_penalty": "రేడియోమెట్రీ జరిమానా",
           "grounding_quality": "ఆధార నాణ్యత"},
}


def component_name(lang: str, key: str) -> str:
    """Translated confidence-component name, falling back to the readable key."""
    return COMPONENTS.get(lang, COMPONENTS["en"]).get(
        key, key.replace("_", " "))


def reading(lang: str, index: str, mean: float) -> str:
    """Translated plain-language reading of an index mean. "" when unknown."""
    fam = INDEX_FAMILY.get(index.lower())
    if not fam:
        return ""
    tbl = READINGS.get(lang, READINGS["en"])
    positive, negative, zero = tbl[fam]
    if mean > 0:
        return positive.format(s=tbl["strong"] if abs(mean) >= 0.30 else "")
    if mean < 0:
        return negative
    return zero


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


def fallback_note(code: str) -> str | None:
    """Explicit notice when a detected script falls back to English."""
    if code in SUPPORTED:
        return None
    from .language import label
    lang_name = label(code)
    return f"[Note: Verified reply templates for {lang_name} are in development; responding in English.]"


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
