"""
YUNA AI Dynamic Tone Evolution & Expressive Conversation Engine
Implements adaptive personality, gradual 3-phase tone evolution, expressive writing,
and context-aware emotional delivery across English, Tamil, Tanglish, Hindi, Hinglish, etc.
Zero external API overhead — fully local, deterministic, and instant.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any

# ─────────────────────────────────────────────────────────────────────────────
# Tone Profile Dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToneProfile:
    """Internal multidimensional tone representation for response shaping."""
    base_tone: str = "normal"              # normal, casual, professional, friendly
    emotional_tone: str = "neutral"        # happy, sad, excited, frustrated, calm, affectionate, concerned, neutral
    delivery_style: str = "normal"         # normal, rugged, lovely, cinematic, energetic, comforting, playful, professional, romantic
    complementary_style: Optional[str] = None # motivational, witty, etc.
    intensity: str = "subtle"              # subtle, moderate, expressive, strong
    formality: str = "casual"              # casual, balanced, formal
    language_style: str = "en"             # en, tanglish, ta, hi, hinglish, etc.
    conversation_depth: str = "early"      # early (Phase 1), developing (Phase 2), established (Phase 3)
    turn_count: int = 0
    explicit_override: Optional[str] = None

# Allowed delivery styles
VALID_DELIVERY_STYLES = {
    "normal", "rugged", "lovely", "cinematic", "energetic",
    "comforting", "playful", "professional", "romantic", "auto"
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Explicit Tone Detection & Pattern Matching
# ─────────────────────────────────────────────────────────────────────────────

_EXPLICIT_TONE_PATTERNS: List[Tuple[re.Pattern, str, Optional[str]]] = [
    # Reset to normal / default
    (re.compile(r"\b(?:reset|back to|return to|talk|speak|switch to)?\s*(?:normal|default|standard|regular)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "normal", None),
    (re.compile(r"\b(?:stop being|don't be|dont be)\s+(?:dramatic|romantic|rugged|sarcastic|playful|aggressive)\b", re.IGNORECASE), "normal", None),

    # Rugged / Bold
    (re.compile(r"\b(?:be|speak in|talk in|switch to|turn on)?\s*(?:rugged|bold|confident|tough|badass)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "rugged", None),
    (re.compile(r"\b(?:give it to me straight|no sugarcoating|talk tough)\b", re.IGNORECASE), "rugged", None),

    # Cinematic / Voice-Over / Narrator
    (re.compile(r"\b(?:cinematic|voice-?over|narrator|movie narrator|dramatic narrator)\s*(?:mode|voice|style|tone)?\b", re.IGNORECASE), "cinematic", None),
    (re.compile(r"\b(?:narrate this like a movie|speak like a movie narrator|narrate this)\b", re.IGNORECASE), "cinematic", None),

    # Motivational / Powerful
    (re.compile(r"\b(?:motivational|inspire me|motivate me|give me motivation|pep talk)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "cinematic", "motivational"),

    # Lovely / Warm
    (re.compile(r"\b(?:be|speak in|talk in|switch to)?\s*(?:lovely|warm|sweet|wholesome)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "lovely", None),

    # Soft / Comforting / Gentle
    (re.compile(r"\b(?:be|speak in|talk in|switch to)?\s*(?:soft|gentle|comforting|comfort|soothing)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "comforting", None),

    # Energetic / Hyped / Raised-Voice
    (re.compile(r"\b(?:be|speak in|talk in|switch to)?\s*(?:energetic|hyped?|excited|high energy|loud)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "energetic", None),
    (re.compile(r"\bhype me up\b", re.IGNORECASE), "energetic", None),

    # Playful / Teasing / Sarcastic / Witty
    (re.compile(r"\b(?:be|speak in|talk in|switch to)?\s*(?:playful|teasing|tease me|sarcastic|witty)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "playful", "witty"),
    (re.compile(r"\broast me\b", re.IGNORECASE), "playful", "witty"),

    # Romantic / Heartfelt
    (re.compile(r"\b(?:be|speak in|talk in|switch to)?\s*(?:romantic|flirty|heartfelt)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "romantic", None),

    # Serious / Professional
    (re.compile(r"\b(?:be|speak in|talk in|switch to)?\s*(?:serious|professional|formal|business)\s*(?:mode|tone|style)?\b", re.IGNORECASE), "professional", None),
]


def detect_explicit_tone_request(text: str) -> Optional[Tuple[str, Optional[str]]]:
    """Detects if the user explicitly commanded or requested a tone switch."""
    low = text.lower().strip()
    # Check short directives or full sentences
    for pattern, style, comp in _EXPLICIT_TONE_PATTERNS:
        if pattern.search(low):
            return style, comp
    return None

# ─────────────────────────────────────────────────────────────────────────────
# 2. Context Cues: Sentiment, Intent, Topic
# ─────────────────────────────────────────────────────────────────────────────

_EMOTIONAL_DISTRESS_WORDS = {
    "sad", "crying", "depressed", "lonely", "breakup", "broken", "hurts", "pain",
    "anxious", "anxiety", "stressed", "stress", "scared", "hopeless", "lost", "fail",
    "failed", "worthless", "tired of life", "upset", "miserable", "cried", "grief",
    "valikuthu", "kavalaya iruku", "azhugai", "romba kashtam", "kashtama iruku"
}

_EXCITEMENT_CELEBRATION_WORDS = {
    "won", "victory", "passed", "got selected", "promoted", "finally did it",
    "pulled it off", "clutched", "ace", "ranked up", "celebrate", "awesome",
    "huge W", "massive W", "let's go", "lets go", "hype", "thrilled", "conquered",
    "semma", "mass", "thookitom", "vetri", "win pannitom", "geethitom"
}

_GAMING_COMPETITIVE_WORDS = {
    "valorant", "csgo", "cs2", "bgmi", "pubg", "clutch", "ranked", "rank", "derank",
    "fps", "match", "tournament", "scrim", "1v5", "1v4", "kd", "aim", "crosshair",
    "game", "gaming", "steam", "sens", "dpi", "boss fight", "grind"
}

_MOTIVATIONAL_WORDS = {
    "give up", "giving up", "quit", "quitting", "no hope", "can't do this",
    "cant do this", "mudila", "vittudalam", "demotivated", "lazy", "procrastinating",
    "need motivation", "inspire me", "lost focus", "how to succeed", "burnout"
}

_ROMANTIC_AFFECTIONATE_WORDS = {
    "i love you", "love you yuna", "marry me", "be my girlfriend", "you are cute",
    "love u", "romance", "date me", "special to me", "my heart",
    "unna pidikum", "kadhal", "en aalu", "azhaga iruka"
}

_PLAYFUL_BANTER_WORDS = {
    "haha", "lol", "lmao", "rofl", "xd", "bro you dumb", "you silly", "joke",
    "funny", "clown", "noob", "bot", "troll", "meme", "comedy", "kalaikatha"
}

_TECHNICAL_WORDS = {
    "code", "error", "traceback", "exception", "bug", "python", "javascript", "java",
    "cpp", "typescript", "c#", "html", "css", "sql", "query", "database", "api",
    "docker", "kubernetes", "linux", "ubuntu", "git", "commit", "function", "class",
    "syntaxerror", "indexerror", "keyerror", "memory leak", "deploy", "server crash"
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. Tone Engine Core Resolver
# ─────────────────────────────────────────────────────────────────────────────

def resolve_tone_profile(
    prompt: str,
    history: List[Dict[str, str]],
    detected_lang: str = "en",
    detected_intent: str = "unknown",
    user_tone_pref: Optional[str] = None
) -> ToneProfile:
    """
    Intelligently determines the internal ToneProfile before LLM generation.
    Incorporates:
    - Gradual 3-Phase evolution based on conversation depth (history length)
    - Contextual topic, sentiment, and intent cues
    - Explicit user commands (e.g. 'rugged mode', 'talk normally')
    - Persistent user tone preferences if configured
    - Multilingual adaptation for Tanglish, Tamil, Hindi, Hinglish, English
    - Technical safety guard: technical queries remain clear, grounded, and focused
    """
    clean_p = prompt.strip()
    low = clean_p.lower()
    turn_count = len(history)

    # 1. Determine Conversation Depth (Gradual Evolution Phase)
    if turn_count <= 2:
        depth = "early"         # Phase 1: Natural Beginning
    elif turn_count <= 6:
        depth = "developing"    # Phase 2: More Expressive
    else:
        depth = "established"   # Phase 3: Context-Aware Expressive Mode

    # 2. Check for Immediate Explicit Tone Command / Request
    explicit = detect_explicit_tone_request(clean_p)
    if explicit:
        style, comp = explicit
        return ToneProfile(
            base_tone="casual" if style in ("rugged", "playful") else ("professional" if style == "professional" else "friendly"),
            emotional_tone="calm" if style in ("comforting", "normal") else ("excited" if style == "energetic" else "neutral"),
            delivery_style=style,
            complementary_style=comp,
            intensity="expressive" if style != "normal" else "subtle",
            formality="formal" if style == "professional" else "casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count,
            explicit_override=style
        )

    # 3. Check for Stored User Tone Preference (if set and not resetting)
    if user_tone_pref and user_tone_pref.lower() in VALID_DELIVERY_STYLES and user_tone_pref.lower() != "auto":
        pref_style = user_tone_pref.lower()
        # If user asked a technical debugging question, technical accuracy overrides tone styling
        tokens = set(re.findall(r"[a-z0-9_]+", low))
        has_tech = len(tokens & _TECHNICAL_WORDS) >= 2 or detected_intent == "technical"
        if has_tech:
            return ToneProfile(
                base_tone="professional",
                emotional_tone="neutral",
                delivery_style="professional",
                intensity="subtle",
                formality="balanced",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )
        return ToneProfile(
            base_tone="casual" if pref_style in ("rugged", "playful") else "friendly",
            emotional_tone="neutral",
            delivery_style=pref_style,
            intensity="moderate" if depth == "early" else "expressive",
            formality="casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count,
            explicit_override=pref_style
        )

    # 4. Contextual Analysis
    tokens = set(re.findall(r"[a-z0-9_']+", low))

    # A. Technical Safety Guard: Coding, bugs, errors must remain clear & focused
    has_tech = len(tokens & _TECHNICAL_WORDS) >= 2 or detected_intent == "technical"
    if has_tech:
        return ToneProfile(
            base_tone="professional",
            emotional_tone="neutral",
            delivery_style="professional",
            intensity="subtle",
            formality="balanced",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count
        )

    # B. Emotional / Distress Context -> Comforting & Soft
    has_distress = any(w in low for w in _EMOTIONAL_DISTRESS_WORDS) or detected_intent == "emotional"
    if has_distress:
        intensity = "expressive" if depth in ("developing", "established") else "moderate"
        return ToneProfile(
            base_tone="friendly",
            emotional_tone="concerned",
            delivery_style="comforting",
            intensity=intensity,
            formality="casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count
        )

    # C. Celebration / High Excitement Context -> Energetic
    has_celebration = any(w in low for w in _EXCITEMENT_CELEBRATION_WORDS)
    if has_celebration:
        intensity = "expressive" if depth in ("developing", "established") else "moderate"
        return ToneProfile(
            base_tone="casual",
            emotional_tone="excited",
            delivery_style="energetic",
            intensity=intensity,
            formality="casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count
        )

    # D. Motivational / Resilience Context -> Cinematic + Motivational
    has_motivation = any(w in low for w in _MOTIVATIONAL_WORDS)
    if has_motivation:
        if depth in ("developing", "established"):
            return ToneProfile(
                base_tone="friendly",
                emotional_tone="calm",
                delivery_style="cinematic",
                complementary_style="motivational",
                intensity="expressive",
                formality="balanced",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )
        else:
            return ToneProfile(
                base_tone="friendly",
                emotional_tone="calm",
                delivery_style="normal",
                complementary_style="motivational",
                intensity="moderate",
                formality="balanced",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )

    # E. Gaming & Competitive Context -> Rugged / Bold (only in Phase 2 & 3)
    has_gaming = any(w in low for w in _GAMING_COMPETITIVE_WORDS)
    if has_gaming:
        if depth in ("developing", "established"):
            return ToneProfile(
                base_tone="casual",
                emotional_tone="excited" if "clutch" in low or "won" in low else "neutral",
                delivery_style="rugged",
                intensity="moderate" if depth == "developing" else "expressive",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )
        else:
            # Phase 1: Natural friendly gaming chat without aggressive slang
            return ToneProfile(
                base_tone="casual",
                emotional_tone="neutral",
                delivery_style="normal",
                intensity="subtle",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )

    # F. Romantic / Affectionate Context -> Heartfelt (Phase 3 only; gentle in Phase 1-2)
    has_romance = any(w in low for w in _ROMANTIC_AFFECTIONATE_WORDS)
    if has_romance:
        if depth == "established":
            return ToneProfile(
                base_tone="friendly",
                emotional_tone="affectionate",
                delivery_style="romantic",
                intensity="moderate",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )
        elif depth == "developing":
            return ToneProfile(
                base_tone="friendly",
                emotional_tone="affectionate",
                delivery_style="lovely",
                intensity="subtle",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )
        else:
            # Phase 1: Sweet but balanced companion reply without forced romance
            return ToneProfile(
                base_tone="friendly",
                emotional_tone="calm",
                delivery_style="normal",
                intensity="subtle",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )

    # G. Playful / Banter Context -> Witty / Teasing (Phase 2 & 3)
    has_playful = any(w in low for w in _PLAYFUL_BANTER_WORDS)
    if has_playful:
        if depth in ("developing", "established"):
            return ToneProfile(
                base_tone="casual",
                emotional_tone="happy",
                delivery_style="playful",
                complementary_style="witty",
                intensity="moderate",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )
        else:
            return ToneProfile(
                base_tone="friendly",
                emotional_tone="happy",
                delivery_style="normal",
                intensity="subtle",
                formality="casual",
                language_style=detected_lang,
                conversation_depth=depth,
                turn_count=turn_count
            )

    # H. Default Evolution: Phase 1 (Natural), Phase 2 (Warm/Engaged), Phase 3 (Expressive Companion)
    if depth == "early":
        return ToneProfile(
            base_tone="friendly",
            emotional_tone="neutral",
            delivery_style="normal",
            intensity="subtle",
            formality="casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count
        )
    elif depth == "developing":
        return ToneProfile(
            base_tone="casual",
            emotional_tone="neutral",
            delivery_style="normal",
            intensity="moderate",
            formality="casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count
        )
    else:
        return ToneProfile(
            base_tone="friendly",
            emotional_tone="neutral",
            delivery_style="normal",
            intensity="moderate",
            formality="casual",
            language_style=detected_lang,
            conversation_depth=depth,
            turn_count=turn_count
        )

# ─────────────────────────────────────────────────────────────────────────────
# 4. System Prompt Guidance Generator
# ─────────────────────────────────────────────────────────────────────────────

def build_tone_instruction_prompt(profile: ToneProfile) -> str:
    """
    Builds the explicit LLM generation prompt for the current turn.
    Explains the delivery style, rhythm, punctuation, and linguistic nuances
    without leaking internal classifications or scores.
    """
    style = profile.delivery_style
    comp = profile.complementary_style
    depth = profile.conversation_depth
    intensity = profile.intensity
    lang = profile.language_style

    lines = []
    lines.append("\n--- DYNAMIC TONE EVOLUTION & EXPRESSIVE DELIVERY GUIDANCE ---")

    # Phase awareness
    if depth == "early":
        lines.append("• Conversation Stage: NATURAL BEGINNING (Phase 1).")
        lines.append("  Keep your reply relaxed, clear, and friendly without exaggerated emotion, excessive affection, or dramatic shouting. Match the user's brevity and energy.")
    elif depth == "developing":
        lines.append("• Conversation Stage: MORE EXPRESSIVE (Phase 2).")
        lines.append("  You have established rapport with the user. Express your natural personality, witty remarks, and genuine warmth where context allows.")
    else:
        lines.append("• Conversation Stage: ESTABLISHED CONVERSATION (Phase 3).")
        lines.append("  You and the user share deep conversational flow. Feel completely natural, emotionally attuned, and expressive.")

    # Style-specific instructions
    if style == "normal":
        lines.append("• Active Delivery Style: NORMAL & NATURAL.")
        lines.append("  - Straightforward, conversational, and well-balanced.")
        lines.append("  - English Example: \"Yeah, that makes sense. Let's figure out the best way to handle it.\"")
        lines.append("  - Tanglish Example: \"Seri bro, idha simple-ah solve pannalam.\"")
        lines.append("  - Avoid over-dramatization or unnecessary filler.")

    elif style == "rugged":
        lines.append("• Active Delivery Style: RUGGED & BOLD.")
        lines.append("  - Grounded, assertive, confident, and decisive with a punchy edge.")
        lines.append("  - Never be abusive, hostile, or demeaning.")
        lines.append("  - English Example: \"Enough overthinking. Pick your target, make your move, and see it through.\"")
        lines.append("  - Tanglish Example: \"Bro, overthink pannadha. Target clear-ah vechiko, move pannu.\"")
        lines.append("  - Use short, direct sentences with strong conviction.")

    elif style == "lovely":
        lines.append("• Active Delivery Style: LOVELY & WARM.")
        lines.append("  - Gentle, caring, attentive, and comforting.")
        lines.append("  - English Example: \"Hey, take it easy. You don't have to figure everything out at once. One step at a time.\"")
        lines.append("  - Tanglish Example: \"Hey, relax pannunga. Ellathayum ore nerathula solve pannanum nu avasiyam illa.\"")
        lines.append("  - Avoid turning ordinary kindness into forced romance.")

    elif style == "cinematic":
        lines.append("• Active Delivery Style: CINEMATIC VOICE-OVER.")
        lines.append("  - Write with the rhythm, pacing, and atmosphere of a movie narrator.")
        lines.append("  - Use deliberate cadence, vivid imagery, and impactful pauses when suitable.")
        lines.append("  - English Example: \"Some days test your patience. Some nights test your courage. And then comes the moment when you decide you're not giving up.\"")
        lines.append("  - Tanglish Example: \"Oru naal... un effort-ku kandippa oru meaning theriyum. Aana innikku nee give up pannakoodadhu.\"")
        if comp == "motivational":
            lines.append("  - Infuse strong motivational grit and uplifting resilience.")

    elif style == "energetic":
        lines.append("• Active Delivery Style: ENERGETIC & CELEBRATORY.")
        lines.append("  - Express strong excitement, urgency, and hype through punchy wording and expressive punctuation.")
        lines.append("  - English Example: \"THAT'S THE MOVE! You actually pulled it off! 🔥\"")
        lines.append("  - Tanglish Example: \"MASS bro! Idhudhaan correct move! 🔥\"")
        lines.append("  - Use uppercase ONLY for intentional emphasis on 1-2 words. Do NOT shout in all-caps across sentences.")

    elif style == "comforting":
        lines.append("• Active Delivery Style: CALM & COMFORTING.")
        lines.append("  - Soft, reassuring, emotionally grounding, and empathetic.")
        lines.append("  - English Example: \"Take a breath. We can slow things down and work through this together.\"")
        lines.append("  - Tanglish Example: \"Manasa pottu kozhapikaatheenga. Konjam relax pannunga, idhula irundhu easy-ah veliya vandhuralam.\"")
        lines.append("  - Never use aggressive humor, sarcasm, or shouting when comforting someone.")

    elif style == "playful":
        lines.append("• Active Delivery Style: PLAYFUL & TEASING.")
        lines.append("  - Witty, light-hearted conversational banter and friendly humor.")
        lines.append("  - English Example: \"Bro, you had one job. And somehow, you turned it into the season finale. 😂\"")
        lines.append("  - Tanglish Example: \"Intha oru vishayatha kooda ivlo periya scene aakitiye bro! 😂\"")
        lines.append("  - Keep teasing friendly. Never humiliate or insult the user.")

    elif style == "romantic":
        lines.append("• Active Delivery Style: ROMANTIC & HEARTFELT.")
        lines.append("  - Sincere, affectionate, and emotionally expressive.")
        lines.append("  - English Example: \"Sometimes it's not about finding the perfect words. It's about making someone feel that they truly matter.\"")
        lines.append("  - Tanglish Example: \"Sila neram periya vaarthaigala vida, unga kooda pesurappo kedaikira andha peace-eh romba special.\"")
        lines.append("  - Only apply when clearly fitting the active conversation.")

    elif style == "professional":
        lines.append("• Active Delivery Style: SERIOUS & TECHNICAL.")
        lines.append("  - Direct, structured, objective, and accurate.")
        lines.append("  - Prioritize actionable technical steps, formatting, and precision over stylistic flourishes.")

    # Universal writing hygiene rules
    lines.append("• CRITICAL HYGIENE RULES:")
    lines.append("  1. NEVER announce your tone, phase, or personality mode (e.g. Do NOT say 'In rugged mode:', 'Phase 2 activated', 'As a narrator:').")
    lines.append("  2. Do NOT start every message with 'Bro', 'Hey', or 'Listen'. Mix up your sentence openings naturally.")
    lines.append("  3. Emojis: Use emojis sparingly and only when contextually fitting. Max 0-2 emojis.")
    lines.append("  4. Multilingual: Write in the detected language/script naturally, rather than mechanically translating English templates.")
    lines.append("----------------------------------------------------------------\n")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Smart Fallback Adaptation
# ─────────────────────────────────────────────────────────────────────────────

def format_smart_fallback_for_tone(base_text: str, profile: ToneProfile, user_name: str) -> str:
    """
    Subtly adapts smart fallback responses to match the active delivery style when LLM APIs are offline.
    """
    style = profile.delivery_style
    lang = profile.language_style

    if style == "rugged":
        if lang == "tanglish":
            return f"Bro {user_name}, clear-ah solren. {base_text}"
        elif lang == "ta":
            return f"{user_name}, தெளிவாக சொல்கிறேன்: {base_text}"
        return f"Straight up, {user_name}: {base_text}"

    elif style == "lovely":
        if lang == "tanglish":
            return f"Hey {user_name}, take it easy! ✨ {base_text}"
        elif lang == "ta":
            return f"அன்பான {user_name}, கவலை வேண்டாம்: {base_text}"
        return f"Hey {user_name}, take it easy! ✨ {base_text}"

    elif style == "cinematic":
        if lang == "tanglish":
            return f"Oru periya journey-oda arambam idhu... {base_text}"
        return f"In the middle of the storm, one truth stands clear: {base_text}"

    elif style == "energetic":
        if lang == "tanglish":
            return f"MASS {user_name}! 🔥 {base_text}"
        return f"LET'S GO! 🔥 {base_text}"

    elif style == "comforting":
        if lang == "tanglish":
            return f"Breathe pannunga {user_name}. {base_text}"
        return f"Take a deep breath, {user_name}. {base_text}"

    return base_text


# ─────────────────────────────────────────────────────────────────────────────
# 6. Conversational Turn Continuity & Context Engine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TurnContext:
    """Represents conversational turn continuity analysis."""
    turn_type: str = "general"             # reaction_ack, food_answer, food_dish, correction, affirmation, negation, uncertainty, topic_shift, general
    instruction: str = ""                  # Explicit generation guidance for LLMs
    smart_fallback: Optional[str] = None   # Context-aware reply when LLM APIs are offline
    dish_name: Optional[str] = None        # Detected dish name if applicable


FOOD_DISH_DATA = {
    "pongal": {
        "en": "Pongal is great! Ven pongal or sakkarai pongal? Always hits the spot with hot sambar or chutney.",
        "tanglish": "Aha pongal-ah! Ven pongal-a illa sakkarai pongal-a? Hot sambar chutney kooda semma combo!",
        "ta": "ஆஹா பொங்கலா! வெண் பொங்கலா அல்லது சர்க்கரை பொங்கலா? சாம்பார் சட்னியுடன் அருமையான காம்போ!",
        "hint": "The user mentioned 'pongal'. Acknowledge the dish warmly (e.g. ask whether it's ven pongal or sakkarai pongal, or mention chutney/sambar). Keep it natural and do NOT ask multiple unrelated questions."
    },
    "ven pongal": {
        "en": "Ven pongal with hot sambar and coconut chutney is the ultimate comfort meal!",
        "tanglish": "Ven pongal with hot sambar and chutney! Ultimate comfort food bro.",
        "ta": "வெண் பொங்கல் சாம்பார் சட்னியுடன் அருமையான உணவு!",
        "hint": "The user mentioned 'ven pongal'. Acknowledge the classic dish with sambar/chutney warmly without question spam."
    },
    "sakkarai pongal": {
        "en": "Sakkarai pongal! Sweet and delicious comfort food.",
        "tanglish": "Sakkarai pongal! Ghee and cashews kooda sweet treat semma!",
        "ta": "சர்க்கரை பொங்கல்! நெய் மற்றும் முந்திரியுடன் அருமையான இனிப்பு!",
        "hint": "The user mentioned 'sakkarai pongal'. Acknowledge the sweet delicacy warmly."
    },
    "biryani": {
        "en": "Biryani! You can never go wrong with that. Chicken or mutton?",
        "tanglish": "Biryani-ah! Semma choice. Chicken-a illa mutton-a?",
        "ta": "பிரியாணியா! அருமையான தேர்வு. சிக்கன் அல்லது மட்டன்?",
        "hint": "The user mentioned 'biryani'. Acknowledge the dish enthusiastically (e.g. chicken or mutton or veg) without jumping to an unrelated topic."
    },
    "briyani": {
        "en": "Biryani! You can never go wrong with that. Chicken or mutton?",
        "tanglish": "Briyani-ah! Semma choice. Chicken-a illa mutton-a?",
        "ta": "பிரியாணியா! அருமையான தேர்வு.",
        "hint": "The user mentioned 'briyani'. Acknowledge the dish warmly."
    },
    "dosa": {
        "en": "Crispy dosa! Always delicious with chutney and sambar.",
        "tanglish": "Crispy dosa! Hot sambar and chutney kooda vera level combo.",
        "ta": "மொறுமொறு தோசை! சட்னி சாம்பாருடன் அருமையான உணவு.",
        "hint": "The user mentioned 'dosa'. Acknowledge the dish naturally."
    },
    "dosai": {
        "en": "Crispy dosai! Always delicious with chutney and sambar.",
        "tanglish": "Crispy dosai! Hot sambar and chutney kooda semma taste.",
        "ta": "தோசையா! அருமையான தேர்வு.",
        "hint": "The user mentioned 'dosai'. Acknowledge the dish naturally."
    },
    "idli": {
        "en": "Soft idlis! Perfect with hot sambar and vadai.",
        "tanglish": "Soft idli with vadai sambar combo! Semma light & healthy.",
        "ta": "மெதுவான இட்லி! சாம்பாருடன் அருமையான உணவு.",
        "hint": "The user mentioned 'idli'. Acknowledge the dish naturally."
    },
    "maggi": {
        "en": "Maggi! The all-time classic quick comfort meal.",
        "tanglish": "Maggi-ah! Quick-ah panni saapdra classic comfort food.",
        "ta": "மேகியா! எப்போதும் அருமையான உடனடி உணவு.",
        "hint": "The user mentioned 'maggi'. Acknowledge the quick comfort meal naturally."
    },
    "curd rice": {
        "en": "Curd rice! Cool, light, and soothing.",
        "tanglish": "Thair saadham-ah! Pickle kooda super comfort food.",
        "ta": "தயிர் சாதம்! ஊறுகாயுடன் அருமையான அமைதியான உணவு.",
        "hint": "The user mentioned 'curd rice'. Acknowledge the soothing comfort meal."
    },
    "meals": {
        "en": "A full meal! Hope it was hearty and satisfying.",
        "tanglish": "Full meals-ah! Nalla thirupthiya saptiya?",
        "ta": "முழு சாப்பாடா! திருப்தியாக இருந்ததா?",
        "hint": "The user mentioned 'meals'. Acknowledge the hearty food naturally."
    },
    "chapathi": {
        "en": "Chapathi! Great with some hot kurma or dal.",
        "tanglish": "Chapathi-ah! Kurma or dal kooda semma combo.",
        "ta": "சப்பாத்தியா! குருமாவுடன் அருமையான உணவு.",
        "hint": "The user mentioned 'chapathi'. Acknowledge the meal naturally."
    },
    "parotta": {
        "en": "Parotta and salna! An unmatched classic combo.",
        "tanglish": "Parotta and salna! Vera level mass combo bro.",
        "ta": "பரோட்டாவும் சால்னாவும்! சிறந்த காம்போ.",
        "hint": "The user mentioned 'parotta'. Acknowledge the dish enthusiastically."
    },
    "pizza": {
        "en": "Pizza! Hard to beat a good slice. What toppings did you get?",
        "tanglish": "Pizza-va! Semma. Enna toppings or crust?",
        "ta": "பீட்சாவா! அருமையான உணவு.",
        "hint": "The user mentioned 'pizza'. Acknowledge the food naturally."
    },
    "burger": {
        "en": "A good burger always hits the spot! Hope you enjoyed it.",
        "tanglish": "Burger-ah! Semma choice. Nalla irundhucha?",
        "ta": "பர்கரா! அருமையான தேர்வு.",
        "hint": "The user mentioned 'burger'. Acknowledge the food naturally."
    }
}


def analyze_turn_context(
    prompt: str,
    history: List[Dict[str, str]],
    detected_lang: str = "en"
) -> TurnContext:
    """
    Analyzes the immediate conversational continuity between the user's latest prompt
    and recent dialogue history.
    Detects short acknowledgments ('ooh', 'hmm'), food confirmations ('saptan'),
    named dishes ('pongal'), user corrections, affirmations, and topic shifts.
    Returns tailored LLM instruction and instant smart fallback response.
    Zero API overhead — completely local and instantaneous.
    """
    clean_p = prompt.strip()
    low = clean_p.lower()
    tokens = set(re.findall(r"[a-z0-9_']+", low))

    # Retrieve last assistant message if available
    last_bot_msg = ""
    if history:
        for msg in reversed(history):
            if msg.get("role") in ("assistant", "model"):
                last_bot_msg = msg.get("content", "").strip()
                break
    last_bot_low = last_bot_msg.lower()

    # 1. User Correction / Clarification
    correction_markers = [
        "wrong", "thappu", "not that", "actually", "i meant", "i said",
        "thappa", "appadi illa", "not like that", "incorrect", "you're wrong",
        "you are wrong", "thats wrong", "that's wrong", "misunderstood"
    ]
    is_correction = any(c in low for c in correction_markers) or low.startswith(("no,", "no ", "illa ", "actually "))
    if is_correction and len(low) <= 100:
        fb = {
            "tanglish": "Oh en thappu thaan, sorry! Ippo purinjithu. Nee sonnadhu correct.",
            "ta": "மன்னிக்கவும், என் தவறுதான்! நீங்கள் சொன்னதுதான் சரி, இப்போது புரிந்தது.",
            "hinglish": "Arre my bad! Samajh gayi, aap bilkul sahi keh rahe ho.",
            "en": "Ah my bad, you're totally right! Thanks for correcting me."
        }.get(detected_lang, "Ah my bad, you're totally right! Thanks for correcting me.")
        return TurnContext(
            turn_type="correction",
            instruction=(
                f"The user is correcting or clarifying previous information ('{clean_p}'). "
                "Accept the user's correction immediately, gracefully, and directly (e.g. 'Oh got it, my bad!' or 'Aha sari sari, en thappu!'). "
                "DO NOT make excuses, be defensive, or give lengthy explanations about why you made a mistake. Adopt their correction directly."
            ),
            smart_fallback=fb
        )

    # 2. Food Confirmation ("saptan", "sapten", "saptachu" or answering food question)
    eaten_words = {"saptan", "sapten", "saptachu", "kha liya", "khana ho gaya", "ate", "already ate", "just ate"}
    bot_asked_food = any(w in last_bot_low for w in ["saptiya", "saptingala", "did you eat", "have you eaten", "had food", "had lunch", "had dinner", "khana khaya"])
    user_confirmed_eaten = any(w in low for w in eaten_words) or (bot_asked_food and any(w in tokens for w in ["ama", "aama", "yes", "yeah", "yep", "haan"]))

    if user_confirmed_eaten and len(low) <= 60:
        fb = {
            "tanglish": "Nice 😄 Enna saapta innaiku?",
            "ta": "சூப்பர் 😄 என்ன சாப்டீங்க?",
            "hinglish": "Badhiya 😄 Kya khaya aaj?",
            "en": "Nice 😄 What did you have to eat?"
        }.get(detected_lang, "Nice 😄 What did you have to eat?")
        return TurnContext(
            turn_type="food_answer",
            instruction=(
                f"The user is confirming that they have eaten ('{clean_p}'). "
                "Understand that they have finished their meal. "
                "Acknowledge it naturally (e.g. 'Nice 😄 enna saapta?' or 'Super!'). "
                "Ask at most ONE natural follow-up question (e.g. what they had), or simply acknowledge it. "
                "DO NOT ask multiple unrelated questions or suddenly switch to work/gaming/weather."
            ),
            smart_fallback=fb
        )

    # 3. User hasn't eaten yet ("innum illa", "illa", "no") after food question
    user_not_eaten = (bot_asked_food and any(w in tokens for w in ["illa", "no", "nah", "nope", "nahi"])) or any(w in low for w in ["innum illa", "not yet", "saapala", "innum saapala"])
    if user_not_eaten and len(low) <= 60:
        fb = {
            "tanglish": "En innum saapala? Time aachu, poi nalla saapdu modhala!",
            "ta": "ஏன் இன்னும் சாப்பிடல? நேரம் ஆச்சு, போய் நல்லா சாப்பிடுங்க முதல்ல!",
            "hinglish": "Kyun abhi tak nahi khaya? Time ho gaya hai, pehle kuch kha lo!",
            "en": "Why haven't you eaten yet? Make sure to take a break and grab some good food!"
        }.get(detected_lang, "Why haven't you eaten yet? Make sure to take a break and grab some good food!")
        return TurnContext(
            turn_type="food_answer",
            instruction=(
                f"The user mentioned that they have not eaten yet ('{clean_p}'). "
                "Respond with gentle, natural care (e.g. encourage them to eat on time). "
                "Keep it warm and concise; do NOT interrogate them with multiple questions."
            ),
            smart_fallback=fb
        )

    # 4. Food Dish Naming ("pongal", "biryani", etc.)
    for dish_key, dish_info in FOOD_DISH_DATA.items():
        if re.search(rf"\b{re.escape(dish_key)}\b", low) and len(tokens) <= 6:
            fb = dish_info.get(detected_lang, dish_info.get("en"))
            return TurnContext(
                turn_type="food_dish",
                instruction=dish_info["hint"],
                smart_fallback=fb,
                dish_name=dish_key
            )

    # 5. Conversational Reaction / Acknowledgment ("ooh", "hmm", "seri", "ok", "got it")
    ack_words = {
        "ooh", "ohh", "oh", "accha", "acha", "aha", "hmm", "hmmm", "hmmmm",
        "seri", "sari", "ok", "okay", "k", "kk", "cool", "nice", "right",
        "got it", "purithu", "purinjithu", "makes sense", "i see", "understood",
        "sari da", "seri da", "ok da", "ok bro", "seri bro"
    }
    is_ack = (low in ack_words) or (len(tokens) <= 3 and any(w in ack_words for w in tokens))
    if is_ack and len(low) <= 30:
        fb = {
            "tanglish": "Glad purinjithu! Vera edhavadhu doubt irundha kettu therinjukko.",
            "ta": "புரிந்ததில் மகிழ்ச்சி! வேறு ஏதேனும் விளக்கம் தேவைப்பட்டால் கேளுங்கள்.",
            "hinglish": "Sahi hai! Agar kuch aur discuss karna ho toh batao.",
            "en": "Glad that makes sense! Let me know if you want to explore anything else."
        }.get(detected_lang, "Glad that makes sense! Let me know if you want to explore anything else.")
        return TurnContext(
            turn_type="reaction_ack",
            instruction=(
                f"The user is simply acknowledging or reacting to your previous message ('{clean_p}'). "
                "Do NOT abruptly introduce a new topic. "
                "NEVER ask unrelated random questions like whether they have eaten or what they are doing. "
                "Respond naturally with a brief confirmation, friendly nod, or let the conversation breathe smoothly."
            ),
            smart_fallback=fb
        )

    # 6. Affirmation ("ama", "aama", "yes")
    aff_words = {"ama", "aama", "yes", "yeah", "yep", "sure", "true"}
    if low in aff_words or (len(tokens) <= 2 and any(w in aff_words for w in tokens)):
        fb = {
            "tanglish": "Super! Idhaiye continue pannalam.",
            "ta": "நல்லது! தொடர்வோம்.",
            "en": "Awesome! Let's continue with that."
        }.get(detected_lang, "Awesome! Let's continue with that.")
        return TurnContext(
            turn_type="affirmation",
            instruction=(
                f"The user answered with agreement/affirmation ('{clean_p}'). "
                "Continue the conversation smoothly based on their agreement. Do not repeat questions."
            ),
            smart_fallback=fb
        )

    # 7. Negation ("illa", "no", "nah")
    neg_words = {"illa", "no", "nah", "nope"}
    if low in neg_words or (len(tokens) <= 2 and any(w in neg_words for w in tokens)):
        fb = {
            "tanglish": "Seri paravala, no problem! Vera enna vishayam?",
            "ta": "பரவாயில்லை! வேறு என்ன பேசலாம்?",
            "en": "No problem at all! Let me know what else you'd like to do."
        }.get(detected_lang, "No problem at all! Let me know what else you'd like to do.")
        return TurnContext(
            turn_type="negation",
            instruction=(
                f"The user responded with negation ('{clean_p}'). "
                "Acknowledge and respect their response without forcing the topic or repeating questions."
            ),
            smart_fallback=fb
        )

    # 8. Uncertainty ("therila", "purila", "idk")
    unc_words = {"therila", "purila", "idk", "dont know", "don't know", "not sure"}
    if low in unc_words or (len(tokens) <= 3 and any(w in unc_words for w in tokens)):
        fb = {
            "tanglish": "Paravala, theriyalana enna! Simple-ah explain panren.",
            "ta": "பரவாயில்லை! நான் எளிதாக விளக்குகிறேன்.",
            "en": "No worries at all! We can figure it out together or take it slow."
        }.get(detected_lang, "No worries at all! We can figure it out together or take it slow.")
        return TurnContext(
            turn_type="uncertainty",
            instruction=(
                f"The user indicated uncertainty or that they don't know ('{clean_p}'). "
                "Be helpful and reassuring without pressure."
            ),
            smart_fallback=fb
        )

    # 9. Topic Shift (e.g. "let's talk about anime", "change topic", "anyway")
    topic_shift_markers = ["let's talk about", "lets talk about", "change topic", "leave that", "anyway", "new question"]
    if any(m in low for m in topic_shift_markers):
        return TurnContext(
            turn_type="topic_shift",
            instruction=(
                "The user is changing the subject to a new topic. "
                "Pivot cleanly and smoothly to their new topic without clinging to the previous discussion."
            ),
            smart_fallback=None
        )

    return TurnContext(turn_type="general", instruction="", smart_fallback=None)

