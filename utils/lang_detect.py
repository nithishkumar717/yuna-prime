"""
YUNA Lightweight Language & Tanglish Detector
Zero external API calls. Uses script analysis + keyword matching for fast, accurate detection.

Supports:
- English, Tamil (Tanglish / Tamil script), Hindi (Hinglish / Devanagari),
  Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Urdu, Odia,
  Arabic, French, Spanish, Portuguese, German, Italian, Dutch, Russian, Ukrainian,
  Greek, Turkish, Persian, Hebrew, Chinese (Simplified & Traditional),
  Japanese, Korean, Thai, Vietnamese, Indonesian, Malay, Filipino, Swahili,
  Polish, Romanian, Czech, Hungarian, Swedish, Danish, Norwegian, Finnish, etc.
"""

import re
import unicodedata
from typing import Optional, Tuple

# ─── Unicode Script Ranges ────────────────────────────────────────────────────

_DEVANAGARI   = re.compile(r"[\u0900-\u097F]")
_TAMIL_SCRIPT = re.compile(r"[\u0B80-\u0BFF]")
_TELUGU       = re.compile(r"[\u0C00-\u0C7F]")
_KANNADA      = re.compile(r"[\u0C80-\u0CFF]")
_MALAYALAM    = re.compile(r"[\u0D00-\u0D7F]")
_BENGALI      = re.compile(r"[\u0980-\u09FF]")
_GUJARATI     = re.compile(r"[\u0A80-\u0AFF]")
_GURMUKHI     = re.compile(r"[\u0A00-\u0A7F]")   # Punjabi
_ORIYA        = re.compile(r"[\u0B00-\u0B7F]")   # Odia
_ARABIC       = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_HEBREW       = re.compile(r"[\u0590-\u05FF]")
_GREEK        = re.compile(r"[\u0370-\u03FF]")
_CYRILLIC     = re.compile(r"[\u0400-\u04FF]")
_THAI         = re.compile(r"[\u0E00-\u0E7F]")
_GEORGIAN     = re.compile(r"[\u10A0-\u10FF]")
_CJK          = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]")  # Chinese
_HIRAGANA     = re.compile(r"[\u3040-\u309F]")
_KATAKANA     = re.compile(r"[\u30A0-\u30FF]")
_HANGUL       = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")


# ─── Tanglish / Romanized Indian Language Keywords ───────────────────────────

# Core Tanglish markers (Tamil in English letters)
_TANGLISH_STRONG = {
    # Common question forms
    "enna", "epdi", "eppadi", "eppidi", "eppodhu", "eppo", "yenna",
    "saptiya", "saptu", "sapta", "saptinga", "saptingala",
    "iruka", "irukka", "iruke", "iruken", "irukom", "irukkinga",
    "panra", "panren", "panrom", "pannal", "panna", "panni",
    "soldra", "sollu", "sollunga", "solren", "solrom",
    "purila", "puriyala", "puriyuthu", "purinjucha",
    "konjam", "konjum", "romba", "semma", "machi", "macha",
    "theriyum", "therila", "theriyala", "therinjicha",
    "vaarunga", "vaa", "va", "vanthucha", "vanthutten",
    "povom", "poren", "poittu", "porom", "pogala",
    "nalla", "nalliruke", "nalliruka", "nallirukka",
    "aagala", "aayidhu", "aayiduchu", "aachu",
    "da", "di", "nga", "la", "ra", "pa",   # Tamil suffix particles (context sensitive)
    "tamizha", "tamizhan", "tamizh",
    "unga", "unna", "unnaku", "enakku", "enaku",
    "nee", "naan", "avan", "aval", "avar", "avanga",
    "enga", "inge", "anga", "vitta", "vita",
    "bore", "adikuthu", "adichu",
    "paravala", "paravalla",
    "vidu", "vidra", "vittu",
    "bro", "anna", "akka",  # Tamil social terms (bro used in Tanglish context)
    "thambi", "chella",
    "vaanga", "vaanghinga",
    "seri", "seri", "sari",  # Tamil for "okay"
    "illa", "illai", "illama",
    "ama", "aama", "aame",   # Tamil for "yes"
    "kadha", "kadhaya",
    "pesalam", "pesunga", "pesum", "pesuvom",
    "kuthu", "dance", "paadam", "padam",
    "varuma", "varuma", "varum",
    "irukinga", "irukkinga",
    "mudiyum", "mudiyathu", "mudila",
    "tryy", "try",
    "kandupidi", "kandupidikka",
    "explain", "panren", "panrom",
    "adhu", "ithu", "adha", "itha",
    "athuku", "ithuku", "athu",
    "modhalla", "appuram", "aprom",
    "ellam", "ellame",
    "kettiya", "kelu", "kelungga",
    "theliva", "therinja",
    "life", "pannuven",
    "intha", "antha", "indha", "andha",
    "yaru", "yaaru", "yarave",
}

# Hinglish markers (Hindi in English letters)
_HINGLISH_STRONG = {
    "kya", "kaise", "kaisa", "kahan", "kab", "kyun", "kyunki",
    "mujhe", "mujhko", "mera", "meri", "mere", "hamara", "hamari",
    "tum", "aap", "mai", "mein", "hum",
    "hai", "hain", "tha", "thi", "the",
    "karo", "karna", "karoge", "karunga",
    "bhai", "yaar", "dost",
    "bol", "bolo", "batao",
    "acha", "accha", "theek", "thik",
    "bahut", "bohot", "zyada",
    "nahi", "nahin", "nai",
    "haan", "han", "ha",
    "lekin", "par", "aur", "ya",
    "matlab", "iska", "uska",
    "woh", "wo", "yeh", "ye",
    "phir", "fir", "toh", "to",
    "abhi", "kuch", "sab",
    "ek", "dum", "baat", "batana",
    "samajh", "samjha", "samajhna",
    "dekho", "dekh", "dekhte",
    "padh", "likh", "sun",
    "chalo", "chale", "chal",
    "raho", "reh", "rehna",
    "pata", "pataa", "pta",
    "lag", "lagta", "lagti",
}

# Mixed: words shared but stronger with context
_SHARED_LATIN_INDIAN = {
    "da", "na", "la", "ra",  # suffix particles — need other context
    "ok", "okay", "haha", "lol",  # universal
}

# ─── European language keyword spotters (lightweight) ─────────────────────────
# Used when text is purely Latin and not clearly Tanglish/Hinglish

_FRENCH_WORDS    = {"je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "est", "sont", "bonjour", "salut", "merci", "oui", "non", "avec", "dans", "sur", "pour", "mais", "comme", "pas", "les", "des", "une", "un", "que", "qui", "comment", "ca", "va", "bien", "ami", "pourquoi", "tres"}
_SPANISH_WORDS   = {"yo", "tu", "el", "ella", "nosotros", "ellos", "soy", "es", "son", "gracias", "hola", "por", "con", "para", "pero", "como", "no", "las", "los", "una", "un", "que", "quien", "bien", "aqui", "estas", "amigo", "buenos", "dias", "noches", "tardes", "muy"}
_PORTUGUESE_WORDS= {"eu", "voce", "ele", "ela", "nos", "eles", "obrigado", "ola", "por", "com", "para", "mas", "como", "nao", "as", "os", "uma", "que", "sim", "bom", "aqui", "muito", "tudo", "bem", "amigo", "dia", "noite"}
_GERMAN_WORDS    = {"ich", "du", "er", "sie", "wir", "ihr", "ist", "sind", "danke", "bitte", "mit", "für", "fuer", "aber", "und", "oder", "nicht", "das", "der", "die", "ein", "eine", "wie", "was", "wer", "geht", "dir", "hallo", "guten", "morgen", "tag", "abend", "gut", "sehr", "ja", "nein"}
_ITALIAN_WORDS   = {"io", "tu", "lui", "lei", "noi", "voi", "loro", "grazie", "ciao", "con", "per", "ma", "come", "non", "le", "un", "una", "che", "chi", "bene", "si", "stai", "buongiorno", "buonasera", "amico", "prego", "molto"}
_DUTCH_WORDS     = {"ik", "jij", "hij", "zij", "wij", "jullie", "zijn", "bedankt", "hallo", "met", "voor", "maar", "en", "of", "niet", "de", "het", "een", "wat", "wie", "goed", "ook", "dag", "morgen"}
_INDONESIAN_WORDS= {"aku", "kamu", "dia", "kami", "kita", "mereka", "adalah", "dengan", "untuk", "tapi", "dan", "atau", "tidak", "yang", "ini", "itu", "di", "ke", "dari", "ya", "baik", "selamat", "pagi", "siang", "malam", "terima", "kasih"}
_MALAY_WORDS     = {"saya", "awak", "dia", "kami", "kita", "mereka", "ialah", "dengan", "untuk", "tetapi", "dan", "atau", "tidak", "yang", "ini", "itu", "di", "ke", "dari", "ya", "baik", "terima", "kasih", "selamat", "pagi", "malam"}
_FILIPINO_WORDS  = {"ako", "ikaw", "siya", "kami", "tayo", "sila", "ang", "ng", "na", "ay", "at", "pero", "kung", "para", "hindi", "oo", "salamat", "po", "opo", "naman", "ba", "dito", "diyan", "kamusta", "kumusta", "magandang", "umaga"}
_TURKISH_WORDS   = {"ben", "sen", "o", "biz", "siz", "onlar", "tesekkur", "merhaba", "ile", "icin", "ama", "ve", "veya", "degil", "bu", "su", "bir", "ne", "kim", "iyi", "evet", "hayir", "nasılsın", "nasilsin", "gunaydin", "iyi"}
_SWAHILI_WORDS   = {"mimi", "wewe", "yeye", "sisi", "ninyi", "wao", "asante", "habari", "na", "kwa", "lakini", "au", "hapana", "ndio", "hii", "hiyo", "ni", "si", "nini", "nzuri", "jambo", "rafiki"}
_VIETNAMESE_WORDS= {"toi", "ban", "anh", "chi", "chung", "la", "va", "nhung", "khong", "co", "duoc", "voi", "cho", "nhu", "roi", "gi", "sao", "cam", "on", "xin", "chao", "khoe"}
_POLISH_WORDS    = {"ja", "ty", "on", "ona", "my", "wy", "oni", "nie", "tak", "ale", "i", "lub", "z", "dla", "jak", "co", "kto", "dobrze", "prosze", "dziekuje", "cześć", "czesc", "dzien", "dobry"}


# ─── Main Detection Functions ─────────────────────────────────────────────────

def _script_lang(text: str) -> Optional[str]:
    """Identify language from Unicode script blocks. Returns lang code or None."""
    if _TAMIL_SCRIPT.search(text):
        return "ta"  # Tamil
    if _DEVANAGARI.search(text):
        return "hi"  # Hindi / Marathi / Nepali — best guess hi
    if _TELUGU.search(text):
        return "te"
    if _KANNADA.search(text):
        return "kn"
    if _MALAYALAM.search(text):
        return "ml"
    if _BENGALI.search(text):
        return "bn"
    if _GUJARATI.search(text):
        return "gu"
    if _GURMUKHI.search(text):
        return "pa"
    if _ORIYA.search(text):
        return "or"
    if _ARABIC.search(text):
        return "ar"
    if _HEBREW.search(text):
        return "he"
    if _GREEK.search(text):
        return "el"
    if _CYRILLIC.search(text):
        return "ru"
    if _THAI.search(text):
        return "th"
    if _HIRAGANA.search(text) or _KATAKANA.search(text):
        return "ja"
    if _HANGUL.search(text):
        return "ko"
    if _CJK.search(text):
        return "zh"  # Chinese — simplified/traditional guess
    return None


def _count_matches(words: set, tokens: list) -> int:
    return sum(1 for t in tokens if t in words)


def detect_language(text: str, session_lang: Optional[str] = None) -> Tuple[str, float]:
    """
    Detects the language of a message. Returns (lang_code, confidence 0.0-1.0).

    Priority:
    1. Unicode script detection (highest precision)
    2. Tanglish detection (Latin Tamil)
    3. Hinglish detection (Latin Hindi)
    4. European / SEA language keyword matching
    5. Explicit langdetect library (if available)
    6. Fallback: 'en' (English)

    lang_code examples: 'ta', 'hi', 'te', 'kn', 'ml', 'bn', 'gu', 'pa',
                         'ar', 'he', 'el', 'ru', 'th', 'ja', 'ko', 'zh',
                         'tanglish', 'hinglish',
                         'en', 'fr', 'es', 'pt', 'de', 'it', 'nl',
                         'id', 'ms', 'tl', 'tr', 'sw', 'vi', 'pl'
    """
    if not text or not text.strip():
        return ("en", 0.5)

    raw = text.strip()

    # ── 1. Unicode script detection ──────────────────────────────────────────
    script_lang = _script_lang(raw)
    if script_lang:
        return (script_lang, 0.95)

    # ── 2. Purely Latin text below this point ────────────────────────────────
    tokens = re.findall(r"[a-zA-Z']+", raw.lower())
    if not tokens:
        return ("en", 0.5)

    # ── 3. Calculate scores for languages across candidate groups ───────────
    # First check European / World language keywords
    lang_scores = [
        ("fr", _count_matches(_FRENCH_WORDS, tokens)),
        ("es", _count_matches(_SPANISH_WORDS, tokens)),
        ("pt", _count_matches(_PORTUGUESE_WORDS, tokens)),
        ("de", _count_matches(_GERMAN_WORDS, tokens)),
        ("it", _count_matches(_ITALIAN_WORDS, tokens)),
        ("nl", _count_matches(_DUTCH_WORDS, tokens)),
        ("id", _count_matches(_INDONESIAN_WORDS, tokens)),
        ("ms", _count_matches(_MALAY_WORDS, tokens)),
        ("tl", _count_matches(_FILIPINO_WORDS, tokens)),
        ("tr", _count_matches(_TURKISH_WORDS, tokens)),
        ("sw", _count_matches(_SWAHILI_WORDS, tokens)),
        ("vi", _count_matches(_VIETNAMESE_WORDS, tokens)),
        ("pl", _count_matches(_POLISH_WORDS, tokens)),
    ]
    lang_scores.sort(key=lambda x: x[1], reverse=True)
    best_euro_lang, best_euro_score = lang_scores[0]

    # Tanglish detection
    tanglish_hits = _count_matches(_TANGLISH_STRONG, tokens)
    # Check for short particle presence only if there's already at least 1 strong marker
    if tanglish_hits > 0:
        tanglish_hits += _count_matches(_SHARED_LATIN_INDIAN, tokens)

    # Hinglish detection
    hinglish_hits = _count_matches(_HINGLISH_STRONG, tokens)

    # If European language has strong evidence and beats Tanglish/Hinglish
    if best_euro_score >= 1 and best_euro_score > tanglish_hits and best_euro_score > hinglish_hits:
        # Check if ratio is significant
        if best_euro_score >= 2 or len(tokens) <= 5:
            conf = min(0.60 + (best_euro_score / max(len(tokens), 1)) * 0.4, 0.95)
            return (best_euro_lang, conf)

    # Now evaluate Tanglish
    tanglish_ratio = tanglish_hits / max(len(tokens), 1)
    if tanglish_hits >= 2 or (tanglish_hits >= 1 and tanglish_ratio >= 0.30):
        conf = min(0.5 + tanglish_ratio * 1.5, 0.97)
        return ("tanglish", conf)

    # Single strong Tanglish word (short message case: e.g. "Saptiya?", "Epdi iruka?")
    strong_solo = {"enna", "epdi", "eppadi", "saptiya", "iruka", "irukka",
                   "purila", "puriyala", "konjam", "romba", "semma", "seri",
                   "illa", "ama", "paravala", "nalla", "pesalam", "iruken",
                   "panra", "panren", "theriyum", "therila", "bore", "nadakuthu",
                   "machi", "macha", "thambi", "mudiyathu", "mudila"}
    if any(t in strong_solo for t in tokens):
        return ("tanglish", 0.90)

    # Evaluate Hinglish
    hinglish_ratio = hinglish_hits / max(len(tokens), 1)
    if hinglish_hits >= 2 or (hinglish_hits >= 1 and hinglish_ratio >= 0.30):
        conf = min(0.5 + hinglish_ratio * 1.5, 0.95)
        return ("hinglish", conf)

    strong_hinglish_solo = {"kaise", "kaisa", "kahan", "kyun", "kyunki", "bhai",
                            "theek", "bohot", "samajh", "batao", "accha", "karna"}
    if any(t in strong_hinglish_solo for t in tokens):
        return ("hinglish", 0.88)

    # European language with lower score
    if best_euro_score >= 2 and best_euro_score / max(len(tokens), 1) >= 0.15:
        conf = min(0.45 + (best_euro_score / max(len(tokens), 1)) * 1.5, 0.90)
        return (best_euro_lang, conf)

    # ── 6. langdetect library (optional, graceful degradation) ───────────────
    try:
        from langdetect import detect as ld_detect  # type: ignore
        if len(raw) >= 8:
            detected = ld_detect(raw)
            if detected and detected != "en":
                return (detected, 0.70)
    except Exception:
        pass

    # ── 7. Fallback: session language or English ──────────────────────────────
    if session_lang and session_lang not in ("en", "unknown"):
        return (session_lang, 0.40)

    return ("en", 0.80)


def is_explicit_language_request(text: str) -> Optional[str]:
    """
    Detects explicit user requests to switch response language.
    Returns the target language code string (e.g. 'ta', 'tanglish', 'hi', 'en')
    or None if no explicit request found.
    """
    low = text.lower().strip()

    patterns = [
        # Tamil / Tanglish
        (r"\b(?:tamil|tamizh)\s*(?:la|il|le|ule|ul)?\s*(?:pesu|reply|respond|answer|talk|sollu|solu)\b", "ta"),
        (r"\b(?:reply|respond|answer|talk|pesu)\s+(?:in|la|il)?\s*(?:tamil|tamizh)\b", "ta"),
        (r"\btamil\s*(?:la|il)?\s*paesu\b", "ta"),
        # Tanglish
        (r"\b(?:tanglish|english\s+la\s+tamil|tamil\s+english)\b", "tanglish"),
        (r"\btanglish\s*(?:la|il|le)?\s*(?:pesu|reply|respond|answer)?\b", "tanglish"),
        (r"\b(?:reply|respond|talk|pesu)\s+(?:in\s+)?tanglish\b", "tanglish"),
        # English
        (r"\b(?:english|eng)\s*(?:la|il|le)?\s*(?:pesu|reply|respond|answer|talk)\b", "en"),
        (r"\b(?:reply|respond|answer|talk)\s+in\s+english\b", "en"),
        (r"\bexplain\s+(?:this\s+)?in\s+english\b", "en"),
        (r"\bspeak\s+in\s+english\b", "en"),
        # Hindi / Hinglish
        (r"\b(?:hindi|hinglish)\s*(?:mein|me|mein|mai)?\s*(?:bolo|batao|reply|respond|answer|bol)\b", "hi"),
        (r"\b(?:reply|respond|answer)\s+in\s+(?:hindi|hinglish)\b", "hi"),
        # Telugu
        (r"\b(?:reply|respond|answer|talk)\s+in\s+telugu\b", "te"),
        # Kannada
        (r"\b(?:reply|respond|answer|talk)\s+in\s+kannada\b", "kn"),
        # Malayalam
        (r"\b(?:reply|respond|answer|talk)\s+in\s+malayalam\b", "ml"),
        # Bengali
        (r"\b(?:reply|respond|answer|talk)\s+in\s+(?:bengali|bangla)\b", "bn"),
        # Arabic
        (r"\b(?:reply|respond|answer|talk)\s+in\s+arabic\b", "ar"),
        # French
        (r"\b(?:reply|respond|answer|talk)\s+in\s+french\b", "fr"),
        (r"\ben\s+fran[cç]ais\b", "fr"),
        # Spanish
        (r"\b(?:reply|respond|answer|talk)\s+in\s+spanish\b", "es"),
        (r"\ben\s+espa[nñ]ol\b", "es"),
        # German
        (r"\b(?:reply|respond|answer|talk)\s+in\s+german\b", "de"),
        (r"\bauf\s+deutsch\b", "de"),
        # Japanese
        (r"\b(?:reply|respond|answer|talk)\s+in\s+japanese\b", "ja"),
        # Korean
        (r"\b(?:reply|respond|answer|talk)\s+in\s+korean\b", "ko"),
        # Chinese
        (r"\b(?:reply|respond|answer|talk)\s+in\s+(?:chinese|mandarin)\b", "zh"),
        # Generic pattern: "reply in <language>"
        (r"\b(?:reply|respond|speak|answer|talk)\s+in\s+([a-z]+)\b", "__capture__"),
    ]

    for pattern, lang_code in patterns:
        m = re.search(pattern, low)
        if m:
            if lang_code == "__capture__":
                captured = m.group(1).strip()
                return _resolve_language_name(captured)
            return lang_code

    return None


def _resolve_language_name(name: str) -> Optional[str]:
    """Maps a spoken language name to a BCP-47-ish code."""
    mapping = {
        "tamil": "ta", "tamizh": "ta", "tanglish": "tanglish",
        "hindi": "hi", "hinglish": "hinglish",
        "telugu": "te", "kannada": "kn", "malayalam": "ml",
        "bengali": "bn", "bangla": "bn",
        "marathi": "mr", "gujarati": "gu", "punjabi": "pa",
        "urdu": "ur", "odia": "or", "assamese": "as",
        "nepali": "ne", "sinhala": "si",
        "arabic": "ar", "french": "fr", "spanish": "es",
        "portuguese": "pt", "german": "de", "italian": "it",
        "dutch": "nl", "russian": "ru", "ukrainian": "uk",
        "greek": "el", "turkish": "tr", "persian": "fa",
        "hebrew": "he", "chinese": "zh", "mandarin": "zh",
        "japanese": "ja", "korean": "ko", "thai": "th",
        "vietnamese": "vi", "indonesian": "id", "malay": "ms",
        "filipino": "tl", "tagalog": "tl",
        "swahili": "sw", "polish": "pl", "romanian": "ro",
        "czech": "cs", "hungarian": "hu", "swedish": "sv",
        "danish": "da", "norwegian": "no", "finnish": "fi",
        "english": "en",
    }
    return mapping.get(name.lower())


# Language display names for prompt construction
LANG_DISPLAY_NAMES: dict = {
    "en":       "English",
    "ta":       "Tamil (Tamil script)",
    "tanglish": "Tanglish (Tamil written in English/Latin characters)",
    "hi":       "Hindi",
    "hinglish": "Hinglish (Hindi written in English/Latin characters)",
    "te":       "Telugu",
    "kn":       "Kannada",
    "ml":       "Malayalam",
    "bn":       "Bengali",
    "mr":       "Marathi",
    "gu":       "Gujarati",
    "pa":       "Punjabi",
    "ur":       "Urdu",
    "or":       "Odia",
    "as":       "Assamese",
    "ne":       "Nepali",
    "si":       "Sinhala",
    "ar":       "Arabic",
    "fr":       "French",
    "es":       "Spanish",
    "pt":       "Portuguese",
    "de":       "German",
    "it":       "Italian",
    "nl":       "Dutch",
    "ru":       "Russian",
    "uk":       "Ukrainian",
    "el":       "Greek",
    "tr":       "Turkish",
    "fa":       "Persian",
    "he":       "Hebrew",
    "zh":       "Chinese",
    "ja":       "Japanese",
    "ko":       "Korean",
    "th":       "Thai",
    "vi":       "Vietnamese",
    "id":       "Indonesian",
    "ms":       "Malay",
    "tl":       "Filipino/Tagalog",
    "sw":       "Swahili",
    "pl":       "Polish",
    "ro":       "Romanian",
    "cs":       "Czech",
    "hu":       "Hungarian",
    "sv":       "Swedish",
    "da":       "Danish",
    "no":       "Norwegian",
    "fi":       "Finnish",
}


def get_lang_display(lang_code: str) -> str:
    """Returns a human-readable language name for a lang code."""
    return LANG_DISPLAY_NAMES.get(lang_code, lang_code.upper())


# ─── Intent Classification ────────────────────────────────────────────────────

def classify_intent(text: str) -> str:
    """
    Lightweight keyword-based intent classifier. No API calls.
    Returns one of: greeting, farewell, casual, factual, technical,
                    emotional, creative, help, memory, unknown
    """
    low = text.lower().strip()
    tokens = set(re.findall(r"[a-z']+", low))

    # 0. Conversational Correction (user clarifying or correcting)
    corrections = {
        "wrong", "thappu", "not that", "actually", "i meant", "i said",
        "thappa", "appadi illa", "not like that", "incorrect", "you're wrong",
        "thats wrong", "that's wrong", "misunderstood"
    }
    if any(c in low for c in corrections) and len(low) <= 80:
        return "correction"

    # 1. Greeting & Farewell
    greetings = {
        "hi", "hello", "hey", "helo", "hii", "hiii",
        "sup", "whatsup", "wassup", "yo", "howdy",
        "vanakkam", "namaste", "namasthe", "salaam", "salam",
        "bonjour", "hola", "hallo", "ciao", "ola",
        "good morning", "good evening", "good afternoon",
        "gm", "gn", "goodnight", "good night",
    }
    farewell = {"bye", "goodbye", "see you", "cya", "later", "ttyl", "take care"}
    if any(g in low for g in greetings) and len(low) <= 30:
        return "greeting"
    if any(f in low for f in farewell) and len(low) <= 30:
        return "farewell"

    # 2. Food & Meal Talk ("saptan", "pongal", "biryani", etc.)
    food_markers = {
        "saptan", "sapten", "saptachu", "saptiya", "saptingala", "saapadu",
        "pongal", "biryani", "briyani", "dosa", "dosai", "idli", "maggi",
        "chapathi", "parotta", "curd rice", "sambar", "khana", "lunch", "dinner",
        "breakfast", "meals", "pizza", "burger"
    }
    if any(w in tokens or w in low for w in food_markers) and len(low) <= 80:
        return "food_talk"

    # 3. Conversational Reaction / Acknowledgment ("ooh", "hmm", "seri", "ok", "got it")
    reactions = {
        "ooh", "ohh", "oh", "accha", "acha", "aha", "hmm", "hmmm", "hmmmm",
        "seri", "sari", "ok", "okay", "k", "kk", "cool", "nice", "right",
        "got it", "purithu", "purinjithu", "makes sense", "i see", "understood"
    }
    if low in reactions or (len(tokens) <= 3 and any(r in tokens for r in reactions)):
        return "reaction_ack"

    # 4. Affirmation / Negation / Uncertainty
    affirmations = {"ama", "aama", "yes", "yeah", "yep", "sure", "true", "correct"}
    if low in affirmations or (len(tokens) <= 2 and any(a in tokens for a in affirmations)):
        return "affirmation"

    negations = {"illa", "no", "nah", "nope", "not really", "innum illa"}
    if low in negations or (len(tokens) <= 2 and any(n in tokens for n in negations)):
        return "negation"

    uncertainties = {"therila", "purila", "idk", "dont know", "don't know", "not sure"}
    if low in uncertainties or any(u in low for u in uncertainties) and len(low) <= 40:
        return "uncertainty"

    # 5. Emotional
    emotional_words = {
        "sad", "happy", "angry", "frustrated", "stressed", "anxious",
        "depressed", "lonely", "excited", "scared", "worried", "bored",
        "bore", "adikuthu", "romba", "feel", "feeling",
        "miss", "missing", "hurt", "pain", "crying", "upset",
        "hate", "love", "jealous", "hopeless",
    }
    if _count_matches(emotional_words, list(tokens)) >= 1 and len(low) <= 80:
        return "emotional"

    # 6. Technical
    tech_words = {
        "code", "error", "bug", "fix", "python", "javascript", "java", "cpp",
        "react", "html", "css", "api", "server", "database", "sql", "git",
        "install", "debug", "crash", "exception", "traceback", "import",
        "function", "class", "variable", "loop", "array", "object", "json",
        "terminal", "command", "script", "module", "library", "framework",
        "discord", "bot", "deploy", "docker", "linux",
        "windows", "mac", "setup", "configure", "config",
    }
    if _count_matches(tech_words, list(tokens)) >= 2:
        return "technical"

    # 7. Help / Feature request
    help_words = {"help", "how", "what can", "feature", "command", "prefix", "work", "use", "usage"}
    if any(w in low for w in help_words) and len(low) <= 60:
        return "help"

    # 8. Factual questions
    factual = {"what", "who", "when", "where", "why", "which", "how many", "how much",
               "explain", "define", "meaning", "tell me", "describe"}
    if any(w in low for w in factual):
        return "factual"

    # 9. Creative
    creative = {"story", "poem", "write", "create", "imagine", "roleplay", "generate", "draw", "rap", "song", "lyrics"}
    if _count_matches(creative, list(tokens)) >= 1:
        return "creative"

    # 10. Memory commands
    memory_words = {"remember", "forget", "memory", "setname", "my name"}
    if any(w in low for w in memory_words):
        return "memory"

    # 11. Casual conversation
    casual = {"lol", "haha", "um", "uh", "wow", "omg", "bruh", "bro", "da", "same"}
    if _count_matches(casual, list(tokens)) >= 1 and len(low) <= 50:
        return "casual"

    return "unknown"
