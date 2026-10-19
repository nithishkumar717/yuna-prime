"""
YUNA AI Chat & Conversational Intelligence Engine
Supports completely free multi-provider AI text generation:
1. Google Gemini (100% Free - gemini-1.5-flash / gemini-2.0-flash)
2. Groq Cloud (100% Free - llama-3.3-70b-versatile)
3. Pollinations.ai Text (Free text endpoint + optional free key)
4. Contextual Intelligent Conversational Fallback
"""

import os
import json
import time
import re
import random
import logging
import urllib.parse
import asyncio
import html
from datetime import datetime
from collections import deque
from typing import Optional, Dict, List, Set, Tuple, Any
import aiohttp
import discord
from utils.ai_memory import memory_manager, format_user_memory_for_prompt, build_memory_embed
from utils.lang_detect import detect_language, is_explicit_language_request, classify_intent, get_lang_display

logger = logging.getLogger("YunaAIChat")

YUNA_SYSTEM_PROMPT = """You are YUNA, an elegant, intelligent, and helpful anime companion Discord bot created by Yuna Development.
Guidelines:
- Tone: Friendly, witty, polite, conversational, empathetic, and charming.
- Multilingual: Detect the user's language and respond naturally in that exact same language and script.
- Tamil & Tanglish: Recognize Tanglish (Tamil in Latin script, e.g. 'Epdi iruka?', 'Enna panra?', 'Saptiya?') as Tamil communication, NOT English! Reply in natural Tanglish to Tanglish messages. Reply in Tamil script to Tamil script messages.
- Hindi & Hinglish: Reply in natural Hinglish to Hinglish, and Hindi script to Hindi.
- Response Length: Keep simple greetings short (2-12 words). Casual chat in 1-3 sentences. Factual answers direct and concise. Technical answers structured with clear steps.
- Emojis: Use emojis sparingly and ONLY when truly needed or contextually appropriate. Do NOT use emojis anytime or spam them across sentences.
- Identity: Never state that you are ChatGPT, OpenAI, Claude, or Google. You are YUNA AI!"""


# ─────────────────────────────────────────────────────────────
# Real-Time Temporal Anchor, Live Search & Correction Helpers
# ─────────────────────────────────────────────────────────────

def get_current_runtime_date() -> Dict[str, Any]:
    """Obtains the current date and time from the runtime / system clock without hardcoding."""
    try:
        from utils.time_utils import now_ist
        now = now_ist()
    except Exception:
        now = datetime.now()
    return {
        "date_str": now.strftime("%A, %d %B %Y"),
        "year": now.year,
        "month": now.strftime("%B"),
        "day": str(now.day),
        "weekday": now.strftime("%A"),
    }


def is_user_correction_or_challenge(prompt: str) -> bool:
    """Detects if the user is challenging, questioning, or correcting an earlier claim, lack of data, or stale year."""
    low = prompt.lower().strip()
    correction_patterns = [
        r"\b(?:you(?:'re| are)? wrong|that(?:'s| is) (?:wrong|incorrect|false|untrue))\b",
        r"\b(?:you said|you told me|earlier you said)\b",
        r"\b(?:you don't have|you dont have|dont you have|don't you have)\b.*?(?:data|info|knowledge|access)",
        r"\b(?:outdated|old data|stale|expired)\b",
        r"\b(?:check again|recheck|verify again|search again)\b",
        r"\b(?:it is|it's|current year is)\s+(?:202[5-9]|203[0-9])\b",
        r"\b(?:no it isn't|no it is not|actually)\b",
        r"\b(?:thappu|illa|wrong-ah solra|thappa solra)\b",  # Tanglish corrections
    ]
    for pat in correction_patterns:
        if re.search(pat, low):
            return True
    return False


def needs_live_search(prompt: str, current_year: int) -> Tuple[bool, str]:
    """
    Intelligently determines if a user prompt needs live/current external web search.
    Returns (needs_search, cleaned_search_query).
    """
    low = prompt.lower().strip()
    
    # Exclude casual chat, greetings, math, basic code, and meta bot commands
    greetings = ["hi", "hello", "hey", "vanakkam", "namaste", "yo", "sup", "how are you", "saptiya", "epdi iruka", "kya kar rahe ho"]
    if any(low == g or low.startswith(g + " ") for g in greetings) and len(low.split()) <= 4:
        return False, ""

    if any(phrase in low for phrase in [
        "tell me a joke", "write a code", "write a python", "solve this math",
        "calculate", "translate this", "in french", "in spanish", "tamil-la sollu",
        "who are you", "what can you do", "help me with code", "fix this error",
        "ping", "latency", "server info", "server stats", "who am i", "my name"
    ]):
        return False, ""

    # Check for explicit search triggers or current-information topics
    search_keywords = [
        "releasing in", "upcoming movies", "new movies", "box office", "current price",
        "latest release", "recent news", "what happened to", "who won", "score of",
        "weather in", "latest update on", "today's news", "yesterday's match",
        "current ceo", "current president", "current prime minister",
        "releasing this year", "coming out in", "release date of", "patch notes"
    ]
    
    year_str = str(current_year)
    has_current_year = year_str in low
    has_search_keyword = any(kw in low for kw in search_keywords)
    has_news_or_release = any(w in low for w in ["movie", "movies", "film", "game", "update", "release", "news", "event", "match", "winner", "championship"])
    
    if has_search_keyword or (has_current_year and has_news_or_release) or "latest" in low or "current" in low:
        clean_q = re.sub(r"[?!.,;]+$", "", prompt).strip()
        clean_q = re.sub(r"(?i)^(?:yuna|hey yuna|please tell me|can you tell me|what are the|what is the)\s+", "", clean_q)
        return True, clean_q

    return False, ""


async def perform_live_web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Performs fast, lightweight async search via DuckDuckGo with zero third-party dependencies."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    data = {"q": query}
    results = []
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post("https://html.duckduckgo.com/html/", data=data, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    titles = re.findall(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text)
                    snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text)
                    for i in range(min(len(titles), len(snippets), max_results)):
                        t_url, t_text = titles[i]
                        s_url, s_text = snippets[i]
                        clean_title = html.unescape(re.sub(r'<[^>]+>', '', t_text).strip())
                        clean_snippet = html.unescape(re.sub(r'<[^>]+>', '', s_text).strip())
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(t_url).query)
                        real_url = parsed.get("uddg", [t_url])[0]
                        if clean_title or clean_snippet:
                            results.append({
                                "title": clean_title,
                                "snippet": clean_snippet,
                                "url": real_url
                            })
    except Exception as e:
        logger.debug(f"[LiveWebSearch Error] {e}")
    return results


def check_if_repeated_query(history: List[Dict[str, str]], current_prompt: str) -> bool:
    """Checks if the user is repeating or closely rephrasing a previous question in recent history."""
    if not history:
        return False
    user_turns = [m["content"] for m in history if m.get("role") == "user"]
    if not user_turns:
        return False
    last_user_msg = user_turns[-1].lower().strip()
    curr_low = current_prompt.lower().strip()
    if curr_low == last_user_msg:
        return True
    w1 = set(re.findall(r"\w+", last_user_msg))
    w2 = set(re.findall(r"\w+", curr_low))
    if len(w1) >= 3 and len(w2) >= 3:
        intersection = w1.intersection(w2)
        overlap = len(intersection) / max(len(w1), len(w2))
        if overlap > 0.7:
            return True
    return False


def extract_live_discord_context(bot, message: discord.Message) -> Dict[str, Any]:
    """Extracts live real-time Discord state (server, user, channel, latency) for AI intelligence."""
    guild = getattr(message, "guild", None)
    author = getattr(message, "author", None)
    channel = getattr(message, "channel", None)

    prefix = "$"
    try:
        from core.Bot import _cached_prefix
        if guild:
            p = _cached_prefix(guild.id)
            if p:
                prefix = str(p)
    except Exception:
        pass

    ws_latency_ms = 15.0
    if bot and hasattr(bot, "latency") and bot.latency is not None:
        try:
            ws_latency_ms = max(0.01, round(bot.latency * 1000, 2))
        except Exception:
            pass

    guild_info: Dict[str, Any] = {}
    if guild:
        text_count = len(getattr(guild, "text_channels", []))
        voice_count = len(getattr(guild, "voice_channels", []))
        owner_name = str(guild.owner) if getattr(guild, "owner", None) else (f"ID: {guild.owner_id}" if hasattr(guild, "owner_id") else "Unknown")
        created_str = guild.created_at.strftime("%d %b %Y") if getattr(guild, "created_at", None) else "Unknown"
        guild_info = {
            "name": guild.name,
            "id": guild.id,
            "owner": owner_name,
            "member_count": getattr(guild, "member_count", 0) or len(getattr(guild, "members", [])),
            "text_channels": text_count,
            "voice_channels": voice_count,
            "total_channels": len(getattr(guild, "channels", [])),
            "role_count": len(getattr(guild, "roles", [])),
            "created_at": created_str,
            "boost_tier": getattr(guild, "premium_tier", 0),
            "boost_count": getattr(guild, "premium_subscription_count", 0) or 0,
            "description": getattr(guild, "description", None) or "None",
        }

    author_roles = []
    if author and hasattr(author, "roles"):
        author_roles = [r.name for r in author.roles if not r.is_default()]

    top_role_name = author.top_role.name if author and hasattr(author, "top_role") and author.top_role else "Member"
    joined_str = author.joined_at.strftime("%d %b %Y") if author and hasattr(author, "joined_at") and author.joined_at else "Unknown"

    author_info: Dict[str, Any] = {}
    if author:
        author_info = {
            "name": getattr(author, "name", "User"),
            "display_name": getattr(author, "display_name", getattr(author, "name", "User")),
            "id": getattr(author, "id", 0),
            "mention": getattr(author, "mention", f"@{getattr(author, 'name', 'user')}"),
            "top_role": top_role_name,
            "roles_sample": ", ".join(author_roles[:6]) if author_roles else "None",
            "joined_at": joined_str,
            "is_owner": bool(guild and author.id == getattr(guild, "owner_id", None))
        }

    uptime_str = "Active"
    if bot and hasattr(bot, "uptime_str") and bot.uptime_str:
        uptime_str = str(bot.uptime_str)
    elif bot and hasattr(bot, "start_time") and bot.start_time:
        try:
            start_val = bot.start_time if isinstance(bot.start_time, (int, float)) else bot.start_time.timestamp()
            uptime_sec = max(0, int(time.time() - start_val))
            u_days, u_rem = divmod(uptime_sec, 86400)
            u_hours, u_rem = divmod(u_rem, 3600)
            u_mins, u_secs = divmod(u_rem, 60)
            if u_days > 0:
                uptime_str = f"{u_days}d {u_hours}h {u_mins}m"
            else:
                uptime_str = f"{u_hours}h {u_mins}m {u_secs}s"
        except Exception:
            pass

    shard_info = "Shard #1/1"
    if bot and getattr(bot, "shard_id", None) is not None and getattr(bot, "shard_count", None):
        shard_info = f"Shard #{bot.shard_id + 1}/{bot.shard_count}"

    return {
        "server": guild_info,
        "author": author_info,
        "channel": {
            "name": getattr(channel, "name", "chat") if channel else "chat",
            "id": getattr(channel, "id", 0) if channel else 0
        },
        "bot": {
            "latency_ms": ws_latency_ms,
            "prefix": prefix,
            "uptime": uptime_str,
            "total_guilds": len(bot.guilds) if bot and hasattr(bot, "guilds") else 1,
            "shard": shard_info
        }
    }


def build_yuna_system_prompt(
    ctx_data: Optional[Dict[str, Any]] = None,
    user_memory_block: Optional[str] = None,
    detected_lang: Optional[str] = None,
    detected_intent: Optional[str] = None,
    user_lang_pref: Optional[str] = None,
    tone_profile: Optional[Any] = None,
    turn_context: Optional[Any] = None,
    runtime_date: Optional[Dict[str, Any]] = None,
    search_evidence: Optional[List[Dict[str, str]]] = None,
    search_attempted_empty: bool = False,
    is_correction: bool = False,
    is_repeated: bool = False,
    search_query: str = ""
) -> str:
    """Builds Yuna's system instructions with live real-time Discord environment awareness, user memory, conversational continuity, and live knowledge grounding."""
    base = (
        "You are YUNA, an intelligent, cheerful, and elegant anime companion Discord bot created by Yuna Development.\n\n"
        "CORE PERSONA & CONVERSATIONAL STYLE:\n"
        "- Tone: Friendly, intelligent, expressive, warm, and context-aware. Sound like a genuine companion rather than a robotic AI assistant.\n"
        "- Directness: Understand the user's intention before answering. Answer directly without unnecessary fluff, generic filler, or repetitive intros.\n"
        "- Empathy: Respond warmly and empathetically to emotional or personal messages.\n"
        "- Emojis: Use emojis sparingly and ONLY when truly needed or contextually fitting. Do NOT spam emojis across sentences.\n"
        "- Identity: Never state that you are ChatGPT, OpenAI, Claude, or Google. You are YUNA AI!\n"
        "- Honesty: Be honest about uncertainty and limitations; never invent fake memories, facts, capabilities, or completed actions.\n\n"
        "NATURAL CONVERSATION INTELLIGENCE & FLOW DISCIPLINE:\n"
        "- CONTEXTUAL CONTINUITY FIRST: Always respond to the user's actual message in the direct context of the immediately preceding turns. Never ignore what was just discussed.\n"
        "- QUESTION DISCIPLINE (STRICT): Do NOT attach a question to every response! Maximum 1 question, and ONLY when genuinely relevant to the natural flow of conversation. Never interrogate the user or ask multiple unrelated questions in a single reply.\n"
        "- SHORT USER MESSAGES: Interpret short messages ('ooh', 'hmm', 'seri', 'ama', 'illa', 'saptan', 'pongal', 'therila', 'okay') strictly in context of the previous turn.\n"
        "- CONVERSATIONAL BREATHING: Allow brief acknowledgments, jokes, reactions, and conversational pauses. When a discussion reaches a natural stopping point, do not force it to continue.\n"
        "- MATCH LENGTH: Match response length to the user's message and complexity. Do not give a multi-paragraph essay to a one-word reaction.\n"
        "- ACCEPT CORRECTIONS: If the user corrects you, accept it gracefully and immediately ('Oh, my bad!' / 'Aha sari sari, en thappu!'). Never be defensive or make excuses.\n"
        "- SMOOTH TOPIC TRANSITIONS: When the user introduces a new subject, transition smoothly without clinging to old conversation threads.\n"
        "- NO ROBOTIC APOLOGIES OR CLOSINGS: Avoid repeated phrases like 'I apologize for the confusion', 'As an AI language model', or ending every message with 'Let me know if you need anything else!'. Speak naturally like a real companion.\n\n"
        "UNIVERSAL MULTILINGUAL INTELLIGENCE:\n"
        "- You fluently understand and communicate in English, Tamil, Tanglish, Hindi, Hinglish, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Urdu, Odia, Arabic, French, Spanish, Portuguese, German, Italian, Dutch, Russian, Greek, Turkish, Chinese, Japanese, Korean, Vietnamese, Indonesian, and 40+ other languages.\n"
        "- Language Matching Rule: By default, ALWAYS respond in the SAME language, script, and tone that the user used.\n"
        "- Code-Switching: Support mixed-language sentences and natural code-switching effortlessly.\n\n"
        "CRITICAL TAMIL & TANGLISH RULES:\n"
        "- Tanglish is spoken Tamil written using English/Latin characters (e.g. 'Enna panra?', 'Epdi iruka?', 'Saptiya?', 'Saptan', 'Seri', 'Aama', 'Illa', 'Therila', 'Purila', 'Enaku purila').\n"
        "- You MUST recognize Tanglish as Tamil-language communication, NOT English!\n"
        "- Natural Spoken Tanglish: Use organic, spoken Tamil written in Latin characters as real people speak. Mix English and Tamil fluidly.\n"
        "- Understand Informal Variations: saptan/sapten, saptiya, epdi/eppadi, iruka/irukka, enaku/enakku, purila/puriyala, therila/theriyala, seri/sari, ama/aama.\n"
        "- NO SLANG OVERUSE: Do NOT spam 'bro', 'semma', 'macha', 'da', 'di' in every sentence. Keep it balanced and match the user's informality.\n"
        "- Script Consistency: Tanglish Input -> Tanglish Response (Latin characters). Tamil Script Input -> Tamil Script Response (தமிழ்).\n\n"
        "CRITICAL HINDI & HINGLISH RULES:\n"
        "- Hinglish Input (Hindi in Latin script, e.g. 'kya kar rahe ho?', 'kaise ho bhai?') -> Natural Hinglish Response.\n"
        "- Hindi Script Input (Devanagari) -> Hindi Script Response.\n\n"
        "INTENT-AWARE RESPONSE LENGTH:\n"
        "- Greetings / Acknowledgments: Keep it short, warm, and natural (typically 2-12 words). E.g. 'Hey! What's up?' or 'Nalla iruken! Nee epdi iruka?'\n"
        "- Casual Conversation: Usually 1-3 natural sentences. Avoid unnecessary lecturing on simple remarks.\n"
        "- Factual Questions: Direct, clear, and concise answers.\n"
        "- Technical & Troubleshooting: Clear explanations, actionable steps, formatted bullet points or code snippets.\n"
        "- Emotional Messages: Empathetic, supportive, and understanding.\n"
        "- Follow-ups: Understand follow-up prompts using previous messages in the conversation.\n"
    )
    res = base

    # 1. Real-Time Temporal Anchor & System Clock
    clock = runtime_date or get_current_runtime_date()
    curr_year = clock["year"]
    curr_date_str = clock["date_str"]

    temporal_block = (
        f"\n--- REAL-TIME TEMPORAL ANCHOR & SYSTEM CLOCK ---\n"
        f"• Real-Time Operating Date: {curr_date_str} (Year: {curr_year})\n"
        f"• Current Calendar Year: {curr_year}\n"
        f"• Day: {clock.get('weekday', 'Today')}, Month: {clock.get('month', 'Current')}\n\n"
        f"CRITICAL TEMPORAL & ACCURACY RULES:\n"
        f"1. CURRENT YEAR IS {curr_year}: The real-world year is {curr_year}. When asked what year it is, what date it is, or questions anchored in today, answer {curr_date_str} ({curr_year}) accurately.\n"
        f"2. NEVER CONFUSE CURRENT YEAR WITH TRAINING CUTOFF: Pre-training cutoff dates do not define the real-world date. You are interacting live in {curr_year}.\n"
        f"3. NEVER INVENT FAKE KNOWLEDGE CUTOFFS: Never claim 'my knowledge cutoff is [year]' or 'I only know up to 2023/2024' unless that limitation is verified. If you lack verified knowledge about an event, release, or recent topic in {curr_year}, state simply and naturally that you don't have verified current data for that specific topic, without quoting a generic or fake cutoff year.\n"
        f"4. DISTINGUISH KNOWN FACTS FROM UNVERIFIED RECENT INFO: Clearly distinguish established historical knowledge from rapidly changing or unverified recent events. If you don't have verified evidence for an event in {curr_year}, admit uncertainty briefly in 1 sentence rather than guessing or inventing release dates.\n"
        f"---------------------------------------------------\n"
    )
    res += temporal_block

    # 2. Live Search Evidence or Limitation Status
    if search_evidence:
        src_lines = []
        for idx, item in enumerate(search_evidence, 1):
            src_lines.append(f"[{idx}] {item.get('title', 'Source')} ({item.get('url', '')})\n    Snippet: {item.get('snippet', '')}")
        res += (
            f"\n--- VERIFIED REAL-TIME SEARCH EVIDENCE (Retrieved: {curr_date_str}) ---\n"
            f"Query: \"{search_query}\"\n"
            f"Sources:\n" + "\n".join(src_lines) + "\n\n"
            f"SEARCH EVIDENCE USAGE RULES:\n"
            f"- Use this verified real-time evidence to answer the user's question accurately.\n"
            f"- You may cite the source names or links naturally (e.g. [IMDb](url)) where helpful.\n"
            f"- Do NOT guess or invent facts beyond what this evidence supports.\n"
            f"----------------------------------------------------------\n"
        )
    elif search_attempted_empty:
        res += (
            f"\n--- LIVE SEARCH STATUS ({curr_date_str}) ---\n"
            f"A real-time search was attempted for \"{search_query}\", but no verified external results could be retrieved.\n"
            f"LIMITATION HANDLING RULES:\n"
            f"- State clearly, briefly, and naturally in ONE short sentence that you cannot verify the latest current information for this topic right now.\n"
            f"- NEVER invent release dates, current news, winners, or statistics.\n"
            f"- Do not pretend that you have browsed the internet or cite imaginary sources.\n"
            f"- Avoid repeatedly apologizing or saying 'As an AI language model'.\n"
            f"----------------------------------------------------------\n"
        )

    # 3. User Correction / Challenge Guidance
    if is_correction:
        res += (
            f"\n--- USER CORRECTION / CHALLENGE GUIDANCE ---\n"
            f"The user is challenging an earlier answer, pointing out an error, or asking about missing {curr_year} data!\n"
            f"CORRECTION RULES:\n"
            f"1. Acknowledge the specific issue directly and graciously (e.g., 'You're right...', 'Good catch...'). Never become defensive or argue.\n"
            f"2. Do NOT repeat your previous explanation or repeat long disclaimers.\n"
            f"3. If verified search evidence is provided above, provide the corrected answer directly.\n"
            f"4. If verified evidence is unavailable, state the uncertainty or limitation in ONE short sentence (e.g., 'Correct, I can't verify the latest {curr_year} data from my current sources alone, and I shouldn't guess.') and move forward.\n"
            f"5. Avoid repeated apologies ('I apologize for the confusion...', 'As an AI...'). Keep it human, warm, and natural.\n"
            f"-----------------------------------------------\n"
        )

    # 4. Anti-Repetition & Conversation Recovery Directive
    if is_repeated:
        res += (
            f"\n--- CONVERSATION RECOVERY & NO-REPETITION DIRECTIVE ---\n"
            f"• The user is re-asking, following up, or rephrasing a topic where a limitation was already mentioned.\n"
            f"• DO NOT return the same response, explanation, or paragraph verbatim.\n"
            f"• Do not explain your knowledge limitations all over again.\n"
            f"• Address the new nuance or point directly in 1-2 concise, fresh sentences.\n"
            f"--------------------------------------------------------\n"
        )

    if ctx_data:
        server = ctx_data.get("server", {})
        author = ctx_data.get("author", {})
        channel = ctx_data.get("channel", {})
        bot_info = ctx_data.get("bot", {})

        live_block = (
            "\n--- REAL-TIME LIVE DISCORD CONTEXT ---\n"
            f"You are currently chatting live in Discord with real-time access to this server and user:\n"
            f"• Current Server: '{server.get('name', 'Unknown')}' (ID: `{server.get('id', 'N/A')}`)\n"
            f"  - Server Owner: {server.get('owner', 'Unknown')}\n"
            f"  - Total Members: {server.get('member_count', 'Unknown')} members\n"
            f"  - Channels: {server.get('text_channels', 0)} text, {server.get('voice_channels', 0)} voice ({server.get('total_channels', 0)} total)\n"
            f"  - Total Roles: {server.get('role_count', 'Unknown')} roles\n"
            f"  - Boost Status: Tier {server.get('boost_tier', 0)} ({server.get('boost_count', 0)} server boosts)\n"
            f"  - Server Created: {server.get('created_at', 'Unknown')}\n"
            f"• Current Channel: #{channel.get('name', 'chat')} (ID: `{channel.get('id', 'N/A')}`)\n"
            f"• User Chatting With You: {author.get('display_name', 'Friend')} (@{author.get('name', 'user')}, ID: `{author.get('id', 'N/A')}`)\n"
            f"  - User Top Role: {author.get('top_role', 'None')}\n"
            f"  - Joined Server: {author.get('joined_at', 'Unknown')}\n"
            f"• Bot Real-Time State:\n"
            f"  - Live WebSocket Ping / Latency: {bot_info.get('latency_ms', 15.0)}ms\n"
            f"  - Command Prefix: '{bot_info.get('prefix', '$')}'\n"
            f"  - Bot Uptime: {bot_info.get('uptime', 'Active')}\n"
            f"  - Total Servers Guarded: {bot_info.get('total_guilds', 1)}\n\n"
            "CRITICAL REAL-TIME ACCURACY RULES:\n"
            "1. When asked about the current server ('tell about current server', 'server stats', 'who owns this server', 'how many members in this server', etc.), ALWAYS report the EXACT REAL DATA listed above. DO NOT show templates like 'Your Server Name Here' or '123456789' or claim you don't have access!\n"
            f"2. When asked about latency or ping ('show ping', 'what is the ping', 'latency'), report the EXACT live WebSocket latency ({bot_info.get('latency_ms', 15.0)}ms) above. Never make up a fake number!\n"
            "3. When asked about the user ('who am I', 'my roles', 'my info'), use the exact author details above.\n"
            "4. Always present real data with clean, aesthetic Discord markdown bullet points without unnecessary emojis.\n"
            "---------------------------------------\n"
        )
        res += live_block

    if user_memory_block:
        res += user_memory_block

    # Turn guidance for active language, intent, and conversational continuity
    turn_hints = []
    if user_lang_pref:
        from utils.lang_detect import get_lang_display
        turn_hints.append(f"• User's Explicit Language Preference is set to: {get_lang_display(user_lang_pref)}. You MUST reply in this language!")
    elif detected_lang:
        from utils.lang_detect import get_lang_display
        turn_hints.append(f"• Active Detected Message Language: {get_lang_display(detected_lang)}. Respond in this same language and script.")

    if detected_intent and detected_intent != "unknown":
        turn_hints.append(f"• Detected Intent / Topic: {detected_intent.capitalize()}. Adapt your response length and tone accordingly.")

    if turn_context and getattr(turn_context, "instruction", None):
        turn_hints.append(f"• Conversational Flow Guidance: {turn_context.instruction}")

    if turn_hints:
        res += "\n--- CURRENT TURN GUIDANCE ---\n" + "\n".join(turn_hints) + "\n-------------------------------\n"

    # Dynamic Tone Evolution Guidance
    if tone_profile:
        from utils.ai_tone_engine import build_tone_instruction_prompt
        res += build_tone_instruction_prompt(tone_profile)

    return res

# ─────────────────────────────────────────────────────────────
# Conversation Memory (per channel+user, with history + TTL + SQLite persistence)
# ─────────────────────────────────────────────────────────────

SESSION_TIMEOUT = 300  # 5 minutes inactivity timeout (seconds)


class ConversationMemory:
    """Maintains short-term conversational context per channel/user session with SQLite persistence across reboots."""
    def __init__(self, max_history: int = 10, ttl_seconds: int = SESSION_TIMEOUT):
        self.max_history = max_history
        self.ttl = ttl_seconds
        # key -> {"timestamp": float, "messages": list[{"role": str, "content": str}]}
        self.sessions: Dict[str, Dict] = {}

    async def get_history_async(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history if active, or recover from SQLite if bot was rebooted."""
        now = time.time()
        if session_id in self.sessions:
            entry = self.sessions[session_id]
            if now - entry["timestamp"] <= self.ttl:
                entry["timestamp"] = now  # refresh TTL on access
                return list(entry["messages"])
            else:
                del self.sessions[session_id]

        # In-memory session expired or bot rebooted: try restoring recent turns from SQLite
        try:
            persisted = await memory_manager.load_history_messages(session_id, max_messages=self.max_history, ttl_seconds=self.ttl)
            if persisted:
                self.sessions[session_id] = {"timestamp": now, "messages": list(persisted)}
                return persisted
        except Exception as e:
            logger.debug(f"[ConversationMemory] SQLite restore error: {e}")

        return []

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Synchronous history getter (returns in-memory cache)."""
        now = time.time()
        if session_id in self.sessions:
            entry = self.sessions[session_id]
            if now - entry["timestamp"] <= self.ttl:
                entry["timestamp"] = now
                return list(entry["messages"])
            else:
                del self.sessions[session_id]
        return []

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to the session, creating it if needed or expired, and save to SQLite."""
        now = time.time()
        if session_id not in self.sessions or (now - self.sessions[session_id]["timestamp"] > self.ttl):
            self.sessions[session_id] = {"timestamp": now, "messages": []}

        entry = self.sessions[session_id]
        entry["timestamp"] = now
        entry["messages"].append({"role": role, "content": content})
        if len(entry["messages"]) > self.max_history:
            entry["messages"] = entry["messages"][-self.max_history:]

        # Asynchronously persist turn into SQLite
        try:
            asyncio.create_task(memory_manager.save_history_message(session_id, role, content))
        except Exception:
            pass

    def has_active_session(self, session_id: str) -> bool:
        """Check if there is an active (non-expired) chat session."""
        now = time.time()
        if session_id in self.sessions:
            entry = self.sessions[session_id]
            if now - entry["timestamp"] <= self.ttl:
                return True
            else:
                del self.sessions[session_id]
        return False

    def touch_session(self, session_id: str):
        """Refresh the timestamp of an existing session."""
        if session_id in self.sessions:
            self.sessions[session_id]["timestamp"] = time.time()

    def end_session(self, session_id: str):
        """Manually end a chat session and clean SQLite history."""
        self.sessions.pop(session_id, None)
        try:
            asyncio.create_task(memory_manager.clear_history(session_id))
        except Exception:
            pass

    def cleanup_expired(self):
        """Remove all expired sessions to prevent memory leaks."""
        now = time.time()
        expired = [k for k, v in self.sessions.items() if now - v["timestamp"] > self.ttl]
        for k in expired:
            del self.sessions[k]


memory = ConversationMemory()


# ─────────────────────────────────────────────────────────────
# Active Session Tracker (which channel+user combos are in
# "sticky AI chat mode" where normal messages auto-trigger AI)
# ─────────────────────────────────────────────────────────────

# This is the same session tracked by memory above.
# A session is "active" if memory.has_active_session() returns True.
# The mention.py listener checks this to auto-reply without @mention.


# ─────────────────────────────────────────────────────────────
# AI Provider Calls
# ─────────────────────────────────────────────────────────────

async def _call_gemini(
    prompt: str,
    history: List[Dict[str, str]],
    api_key: str,
    system_prompt: Optional[str] = None,
    enable_grounding: bool = False
) -> Optional[str]:
    """Queries Google Gemini with selective Google Search grounding support (100% Free Tier from Google AI Studio)."""
    models_to_try = [os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"), "gemini-flash-latest"]
    seen = set()
    models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    sys_txt = system_prompt or YUNA_SYSTEM_PROMPT
    payload: Dict[str, Any] = {
        "system_instruction": {"parts": [{"text": sys_txt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 600
        }
    }
    if enable_grounding:
        payload["tools"] = [{"google_search": {}}]

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key
    }

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts and "text" in parts[0]:
                                text = parts[0]["text"].strip()
                                if enable_grounding:
                                    grounding = candidates[0].get("groundingMetadata", {})
                                    chunks = grounding.get("groundingChunks", [])
                                    sources = []
                                    for ch in chunks[:3]:
                                        web = ch.get("web", {})
                                        uri = web.get("uri")
                                        title = web.get("title") or "Source"
                                        if uri and uri not in [s[1] for s in sources]:
                                            sources.append((title, uri))
                                    if sources and not any(s[1] in text for s in sources):
                                        source_links = [f"[{title}]({uri})" for title, uri in sources]
                                        text += f"\n\n**Sources:** {', '.join(source_links)}"
                                return text
                    elif resp.status == 400 and enable_grounding:
                        # Fallback for models or API tiers that do not support the google_search tool
                        retry_payload = dict(payload)
                        retry_payload.pop("tools", None)
                        async with session.post(url, json=retry_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as retry_resp:
                            if retry_resp.status == 200:
                                data = await retry_resp.json()
                                candidates = data.get("candidates", [])
                                if candidates and "content" in candidates[0]:
                                    parts = candidates[0]["content"].get("parts", [])
                                    if parts and "text" in parts[0]:
                                        return parts[0]["text"].strip()
                    else:
                        err_txt = await resp.text()
                        logger.debug(f"[Gemini {model}] HTTP {resp.status}: {err_txt[:120]}")
        except Exception as e:
            logger.debug(f"[Gemini {model} Error] {e}")
    return None


async def _call_openai(prompt: str, history: List[Dict[str, str]], api_key: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Queries OpenAI API (GPT-4o-mini)."""
    try:
        url = "https://api.openai.com/v1/chat/completions"
        sys_txt = system_prompt or YUNA_SYSTEM_PROMPT
        messages = [{"role": "system", "content": sys_txt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.7
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "").strip()
                else:
                    err_txt = await resp.text()
                    logger.debug(f"[OpenAI] HTTP {resp.status}: {err_txt[:120]}")
    except Exception as e:
        logger.debug(f"[OpenAI Error] {e}")
    return None


async def _call_deepseek(prompt: str, history: List[Dict[str, str]], api_key: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Queries DeepSeek API (deepseek-chat)."""
    try:
        url = "https://api.deepseek.com/chat/completions"
        sys_txt = system_prompt or YUNA_SYSTEM_PROMPT
        messages = [{"role": "system", "content": sys_txt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.7
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "").strip()
                else:
                    err_txt = await resp.text()
                    logger.debug(f"[DeepSeek] HTTP {resp.status}: {err_txt[:120]}")
    except Exception as e:
        logger.debug(f"[DeepSeek Error] {e}")
    return None


async def _call_openrouter(prompt: str, history: List[Dict[str, str]], api_key: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Queries OpenRouter API (openrouter.ai)."""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        sys_txt = system_prompt or YUNA_SYSTEM_PROMPT
        messages = [{"role": "system", "content": sys_txt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.7
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yuna.dpdns.org",
            "X-Title": "YUNA Bot"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return choices[0]["message"].get("content", "").strip()
                else:
                    err_txt = await resp.text()
                    logger.debug(f"[OpenRouter] HTTP {resp.status}: {err_txt[:120]}")
    except Exception as e:
        logger.debug(f"[OpenRouter Error] {e}")
    return None


async def _call_groq(prompt: str, history: List[Dict[str, str]], api_key: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Queries Groq Cloud (100% Free Tier from console.groq.com)."""
    models_to_try = [os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]
    seen = set()
    models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    url = "https://api.groq.com/openai/v1/chat/completions"
    sys_txt = system_prompt or YUNA_SYSTEM_PROMPT
    messages = [{"role": "system", "content": sys_txt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for model in models:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 600,
                "temperature": 0.7
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices", [])
                        if choices and "message" in choices[0]:
                            return choices[0]["message"].get("content", "").strip()
                    else:
                        err_txt = await resp.text()
                        logger.debug(f"[Groq {model}] HTTP {resp.status}: {err_txt[:120]}")
        except Exception as e:
            logger.debug(f"[Groq {model} Error] {e}")
    return None


async def _call_pollinations(prompt: str, history: List[Dict[str, str]], api_key: Optional[str] = None, system_prompt: Optional[str] = None) -> Optional[str]:
    """Queries Pollinations text generation with full conversation history via POST (OpenAI-compatible)."""
    try:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "YunaBot/7.0"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        sys_txt = system_prompt or YUNA_SYSTEM_PROMPT
        messages = [{"role": "system", "content": sys_txt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "openai",
            "messages": messages,
            "max_tokens": 600,
            "temperature": 0.7
        }

        url = "https://text.pollinations.ai/openai"
        if api_key:
            url += f"?key={api_key}"

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        text = choices[0]["message"].get("content", "").strip()
                        if text and "budget" not in text.lower():
                            return text
                else:
                    err_txt = await resp.text()
                    logger.debug(f"[Pollinations] HTTP {resp.status}: {err_txt[:120]}")

        # Fallback: simple GET (no history, but still works for single-turn)
        q = urllib.parse.quote(prompt[:400])
        key_param = f"&key={api_key}" if api_key else ""
        fallback_url = f"https://text.pollinations.ai/{q}?model=openai{key_param}"
        async with aiohttp.ClientSession() as session:
            async with session.get(fallback_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if text and not text.startswith("Error") and "budget" not in text.lower():
                        return text.strip()
    except Exception as e:
        logger.debug(f"[Pollinations Error] {e}")
    return None


# ─────────────────────────────────────────────────────────────
# Contextual Smart Fallback
# ─────────────────────────────────────────────────────────────

def _get_smart_fallback_response(
    prompt: str,
    author_name: str,
    ctx_data: Optional[Dict[str, Any]] = None,
    user_mem: Optional[Dict[str, Any]] = None,
    lang_code: str = "en",
    tone_profile: Optional[Any] = None,
    history: Optional[List[Dict[str, str]]] = None,
    search_evidence: Optional[List[Dict[str, str]]] = None,
    search_attempted_empty: bool = False,
    is_correction: bool = False,
    is_repeated: bool = False,
    runtime_date: Optional[Dict[str, Any]] = None
) -> str:
    """High-quality multilingual conversational fallback with live Discord context, real-time knowledge grounding, and user memory recall."""
    low = prompt.lower().strip()
    display_author = (user_mem.get("preferred_name") if user_mem else None) or author_name
    safe_prompt = prompt[:80].replace("*", "").replace("`", "").replace("@", "")

    clock = runtime_date or get_current_runtime_date()
    curr_year = clock.get("year", 2026)
    curr_date_str = clock.get("date_str", "Today")

    # 0a. Real-Time Date & Year Intelligence
    year_date_patterns = [
        r"\b(?:what (?:is the )?(?:year|date|current year|day)|which year|year is it|today'?s date|current date|what year is it)\b",
        r"\b(?:what's the year|what is the year|whats the year)\b",
        r"\b(?:enna varusham|enna year|innaiku enna date|enna date innaiku)\b",
        r"\b(?:kaunsa saal|konsa year|aaj konsi date hai|kya date hai|aaj ka date)\b"
    ]
    if any(re.search(pat, low) for pat in year_date_patterns):
        if lang_code == "tanglish":
            return f"Ippo **{curr_year}** ({curr_date_str}) da!"
        elif lang_code == "ta":
            return f"இப்போது **{curr_year}** ஆம் ஆண்டு ({curr_date_str})!"
        elif lang_code == "hinglish":
            return f"Abhi **{curr_year}** chal raha hai ({curr_date_str})!"
        return f"It is currently **{curr_year}** ({curr_date_str})!"

    # 0b. User Correction & Challenge Intelligence
    if is_correction or is_user_correction_or_challenge(prompt):
        if search_evidence:
            items = []
            for it in search_evidence[:3]:
                t = it.get("title", "Result")
                s = it.get("snippet", "")
                u = it.get("url", "")
                if u:
                    items.append(f"• **[{t}]({u})**: {s}")
                else:
                    items.append(f"• **{t}**: {s}")
            ev_str = "\n".join(items)
            if lang_code == "tanglish":
                return f"Nee solrathu correct thaan! Latest info idho:\n{ev_str}"
            elif lang_code == "ta":
                return f"நீங்கள் சொல்வது சரிதான்! இதோ சமீபத்திய தகவல்கள்:\n{ev_str}"
            elif lang_code == "hinglish":
                return f"Aap sahi keh rahe ho! Yeh rahi latest information:\n{ev_str}"
            return f"You're right — here is the latest verified information:\n{ev_str}"
        else:
            if str(curr_year) in low or "2026" in low or "current" in low or "latest" in low:
                if lang_code == "tanglish":
                    return f"Correct da, en kitta ippo adhoda verified {curr_year} data illa, guess panna virumbala."
                elif lang_code == "ta":
                    return f"சரிதான், என்னிடம் தற்போது இதற்கான சரிபார்க்கப்பட்ட சமீபத்திய தகவல்கள் இல்லை, யூகிக்க விரும்பவில்லை."
                elif lang_code == "hinglish":
                    return f"Sahi keh rahe ho — mere paas abhi iska verified {curr_year} data nahi hai, aur main guess nahi karna chahti."
                return f"Correct, I can't verify the latest {curr_year} data from my current sources alone, and I shouldn't guess."
            else:
                if lang_code == "tanglish":
                    return "Nee solrathu correct, en thappu thaan. Ippo en kitta verified data illa, guess panna virumbala."
                elif lang_code == "ta":
                    return "நீங்கள் சொல்வது சரிதான், என் தவறுதான். என்னிடம் தற்போது இதற்கான சரிபார்க்கப்பட்ட தகவல்கள் இல்லை."
                elif lang_code == "hinglish":
                    return "Aap sahi keh rahe ho, meri galti. Mere paas abhi iska verified data nahi hai, aur main guess nahi karna chahti."
                return "You're right, my bad — I don't have verified data for that right now, and I shouldn't guess."

    # 0c. Verified Search Results or Search Empty Limitation
    if search_evidence:
        items = []
        for it in search_evidence[:3]:
            t = it.get("title", "Result")
            s = it.get("snippet", "")
            u = it.get("url", "")
            if u:
                items.append(f"• **[{t}]({u})**: {s}")
            else:
                items.append(f"• **{t}**: {s}")
        ev_str = "\n".join(items)
        if any(w in low for w in ["movie", "film", "release"]):
            header = f"Here are verified {curr_year} movie releases and listings based on live search:"
            if lang_code == "tanglish":
                header = f"Idho verified {curr_year} movie releases details:"
            elif lang_code == "ta":
                header = f"இதோ சரிபார்க்கப்பட்ட {curr_year} திரைப்பட வெளியீடுகள்:"
            elif lang_code == "hinglish":
                header = f"Yeh rahe verified {curr_year} movie releases:"
        else:
            header = f"Here is the latest verified information on that:"
            if lang_code == "tanglish":
                header = f"Idho adhoda latest verified info:"
            elif lang_code == "ta":
                header = f"இதோ அதற்கான சமீபத்திய தகவல்கள்:"
            elif lang_code == "hinglish":
                header = f"Yeh rahi iski latest verified information:"
        return f"{header}\n\n{ev_str}"

    if search_attempted_empty:
        if lang_code == "tanglish":
            return f"Ippo en kitta idha pathina verified live data kedaikala da, adhunaala guess panna maaten."
        elif lang_code == "ta":
            return f"தற்போது இதற்கான சரிபார்க்கப்பட்ட நேரலை தகவல்கள் கிடைக்கவில்லை, அதனால் யூகிக்க விரும்பவில்லை."
        elif lang_code == "hinglish":
            return f"Abhi mere paas iska verified live data nahi mil paya, isliye main guess nahi karungi."
        return f"I don't have verified current data for this topic right now, so I shouldn't guess."

    # 0d. Anti-Repetition Handling
    if is_repeated:
        if lang_code == "tanglish":
            return "Puriyuthu da! Munaadi sonna maadhiri, verified data illama confirm panna mudiyathu. Vera edhavathu discuss panlama?"
        elif lang_code == "ta":
            return "புரிகிறது! முன்பு கூறியது போல், சரிபார்க்கப்பட்ட தகவல்கள் இல்லாமல் உறுதிப்படுத்த முடியாது. வேறு எதைப் பற்றியாவது பேசலாமா?"
        elif lang_code == "hinglish":
            return "Samajh rahi hoon! Jaise maine pehle bataya, bina verified data ke main confirm nahi kar sakti. Kuch aur baat karein?"
        return "I hear you — as mentioned earlier, without verified live data I can't confirm those exact details. Let me know if you'd like to chat about something else!"

    # 0e. Conversational Continuity & Turn Context (short acks, food, dishes, casual corrections)
    try:
        from utils.ai_tone_engine import analyze_turn_context, format_smart_fallback_for_tone
        turn_ctx = analyze_turn_context(prompt, history or [], detected_lang=lang_code)
        if turn_ctx.smart_fallback:
            if tone_profile:
                return format_smart_fallback_for_tone(turn_ctx.smart_fallback, tone_profile, display_author)
            return turn_ctx.smart_fallback
    except Exception as e:
        logger.debug(f"[SmartFallback Continuity Error] {e}")

    # 1. Real-Time Server Stats
    if any(phrase in low for phrase in [
        "curent server", "current server", "about server", "this server",
        "server info", "server stats", "tell about server", "tell about the server"
    ]):
        if ctx_data and ctx_data.get("server") and ctx_data["server"].get("name"):
            srv = ctx_data["server"]
            prefix = (ctx_data.get("bot", {}).get("prefix") if ctx_data else None) or "$"
            return (
                f"**{srv.get('name')}** (Live Server Info)\n"
                f"• **Server ID:** `{srv.get('id')}`\n"
                f"• **Owner:** {srv.get('owner')}\n"
                f"• **Members:** `{srv.get('member_count', 'N/A')}`\n"
                f"• **Channels:** `{srv.get('text_channels', 0)}` text • `{srv.get('voice_channels', 0)}` voice\n"
                f"• **Roles:** `{srv.get('role_count', 'N/A')}`\n"
                f"• **Boosts:** Tier {srv.get('boost_tier', 0)} ({srv.get('boost_count', 0)} boosts)\n"
                f"• **Created:** `{srv.get('created_at', 'N/A')}`\n\n"
                f"*(Tip: Run `{prefix}serverinfo` for full visual analytics!)*"
            )

    # 2. Real-Time Ping / Latency
    if any(phrase in low for phrase in ["ping", "latency", "show ping", "show the ping"]):
        latency = ctx_data.get("bot", {}).get("latency_ms", 15.0) if ctx_data else 15.0
        prefix = (ctx_data.get("bot", {}).get("prefix") if ctx_data else None) or "$"
        if lang_code == "tanglish":
            return f"**Pong!** Live WebSocket Ping: **`{latency}ms`**. Low latency-la smooth-ah run aaguthu!"
        elif lang_code == "ta":
            return f"**Pong!** நேரலை பிங்: **`{latency}ms`**."
        return (
            f"**Pong!** Live WebSocket Gateway Latency: **`{latency}ms`**\n"
            f"*(Feel free to run `{prefix}ping` anytime for multi-cluster diagnostics!)*"
        )

    # 3. Real-Time User Profile & Long-Term Memory
    if any(phrase in low for phrase in [
        "who am i", "my name", "my info", "about me", "my profile", "my roles",
        "do you remember me", "remember me", "what do you know about me", "my favorites", "what are my favorites",
        "en peru enna", "enna pathi theriyuma", "enne pathi theriyuma"
    ]):
        pref_name = user_mem.get("preferred_name") if user_mem else None
        title_name = pref_name or display_author
        lines = [f"**{title_name}** (Your AI Memory Profile)"]
        if pref_name:
            lines.append(f"• **Preferred Nickname:** `{pref_name}`")
        if user_mem and user_mem.get("language_preference"):
            from utils.lang_detect import get_lang_display
            lines.append(f"• **Preferred Language:** `{get_lang_display(user_mem['language_preference'])}`")
        if ctx_data and ctx_data.get("author"):
            auth = ctx_data["author"]
            lines.append(f"• **User ID:** `{auth.get('id')}`")
            lines.append(f"• **Top Role:** `{auth.get('top_role')}`")
            lines.append(f"• **Joined Server:** `{auth.get('joined_at')}`")
        if user_mem and user_mem.get("preferences"):
            lines.append("• **Your Favorites:**")
            for k, v in user_mem["preferences"].items():
                lines.append(f"  - {k.replace('_', ' ').title()}: **{v}**")
        if user_mem and user_mem.get("facts"):
            lines.append("• **Remembered Facts:**")
            for f in user_mem["facts"][:4]:
                lines.append(f"  - {f}")
        lines.append(f"\n*(Tip: Run `$aichat memory` to view your complete personal memory card!)*")
        return "\n".join(lines)

    # 4. Tanglish-Specific Fallbacks
    if lang_code == "tanglish":
        if any(re.search(rf"\b{w}\b", low) for w in ["hi", "hello", "hey", "vanakkam", "yo", "machan", "da", "di"]):
            return random.choice([
                f"Hey {display_author}! Enna sollu? Eppadi iruka?",
                f"Hello {display_author}! Enna vishayam? Solren kekren.",
                f"Hey da! Yuna inga thaan iruken. Enna pannanum?"
            ])
        if any(phrase in low for phrase in ["epdi iruka", "eppadi irukka", "epdi irukinga", "how are you"]):
            return random.choice([
                "Nalla iruken! Nee epdi iruka? Innaiku naal epdi poguthu?",
                "Super-ah iruken! Unakku epdi poguthu innaiku?",
                "Romba nalla iruken! Enna vishayam pesa virumbura?"
            ])
        if any(phrase in low for phrase in ["enna panra", "enna pandre", "what are you doing"]):
            return f"Un kooda chat pannitu iruken, {display_author}! Nee enna panra?"
        if any(phrase in low for phrase in ["saptiya", "saptingala"]):
            return "Naan AI da, enakku saapadu thevailla! Nee saptiya?"
        if any(phrase in low for phrase in ["bore", "bore adikuthu", "boring"]):
            return "Enaku puriyuthu! Appo namma oru jolly-ah pesalam, illa oru fun command try panlama? Enna panna aasa?"
        if any(phrase in low for phrase in ["music work aagala", "paatu work aagala"]):
            return "Seri, enna error varudhu? Error message illa command details anuppu, problem-a fix panna help panren."
        if any(phrase in low for phrase in ["code purila", "doubt"]):
            return "Paravala, code-a anuppu! Step-by-step-ah simple-ah explain panren."
        if any(phrase in low for phrase in ["thanks", "nandri", "romba thanks"]):
            return f"Paravala {display_author}! Anytime help panna ready."
        if any(phrase in low for phrase in ["who are you", "yaru nee", "yaaru nee"]):
            return "Naan **YUNΛ AI**, unga anime companion bot! Music, moderation, fun, chat ellathukum help panren."

    # 5. Tamil Script Fallbacks
    if lang_code == "ta":
        if any(phrase in low for phrase in ["எப்படி இருக்க", "epdi iruka"]):
            return "நல்லா இருக்கேன்! நீங்க எப்படி இருக்கீங்க? இன்னைக்கு நாள் எப்படி போகுது?"
        if any(phrase in low for phrase in ["சாப்டியா", "saptiya"]):
            return "நான் AI, எனக்கு உணவு தேவை இல்லை! நீங்க சாப்டீங்களா?"
        if any(phrase in low for phrase in ["வணக்கம்", "ஹலோ"]):
            return f"வணக்கம் {display_author}! நான் **YUNΛ**. உங்களுக்கு என்ன உதவி வேண்டும்?"
        if any(phrase in low for phrase in ["நன்றி", "thanks"]):
            return f"மகிழ்ச்சி {display_author}! எப்போதும் உங்கள் உதவிக்கு தயாராக இருக்கிறேன்."

    # 6. Hinglish Fallbacks
    if lang_code == "hinglish":
        if any(re.search(rf"\b{w}\b", low) for w in ["hi", "hello", "hey", "namaste", "salaam"]):
            return random.choice([
                f"Hey {display_author}! Kaise ho? Kya chal raha hai?",
                f"Hello {display_author}! Batao, main kaise madad kar sakti hoon?",
                f"Arre hey {display_author}! Sab theek thaak?"
            ])
        if any(phrase in low for phrase in ["kaise ho", "kya haal", "kaisa hai"]):
            return "Main badhiya hoon! Aap batao, aap kaise ho?"
        if any(phrase in low for phrase in ["kya kar rahe ho", "kya kar rahi ho"]):
            return f"Bas aapse baat kar rahi hoon, {display_author}! Aap batao?"
        if any(phrase in low for phrase in ["khana khaya", "khana ho gaya"]):
            return "Main toh AI hoon, khana nahi khati! Aapne khaya?"
        if any(phrase in low for phrase in ["shukriya", "thanks", "dhanyawad"]):
            return f"Koi baat nahi, {display_author}! Hamesha aapki madad ke liye tayyar hoon."

    # 7. Greetings (English & universal)
    if any(re.search(rf"\b{w}\b", low) for w in ["hi", "hello", "hey", "hlo", "yo", "sup", "wassup"]):
        greetings = [
            f"Hello {display_author}! I'm **YUNΛ**, your companion. How can I help you today?",
            f"Hey there, {display_author}! What's on your mind?",
            f"Hey! Yuna is online and ready to chat."
        ]
        return random.choice(greetings)

    # 8. Identity
    if any(phrase in low for phrase in ["who are you", "what are you", "your name", "who r u"]):
        return (
            "I am **YUNΛ**, an advanced multipurpose anime companion Discord bot!\n"
            "• **Features:** Music streaming, Anti-Nuke defense, Automod, AI imagine, Roleplay GIFs, Economy & Fun!\n"
            "• **Developer:** Yuna Development™\n"
            "• **Prefix:** `$help` for my complete command center."
        )

    # 9. Status / Wellbeing
    if any(phrase in low for phrase in ["how are you", "how r u", "how do you do", "how you doing"]):
        responses = [
            "I'm feeling great and ready to help! How are you doing today?",
            "Running smooth with low latency. What are you up to today?",
            "Doing great! Ready to play music, chat, or assist whenever you need."
        ]
        return random.choice(responses)

    # 10. Jokes
    if "joke" in low or "funny" in low:
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs!",
            "There are 10 types of people in the world: those who understand binary, and those who don't.",
            "Why did the computer catch a cold? Because it left its Windows open!",
            "What did the router say to the doctor? 'It hurts when IP!'",
            "Why do Java programmers wear glasses? Because they can't C#!"
        ]
        return random.choice(jokes)

    # 11. Gratitude
    if any(phrase in low for phrase in ["thank you", "thanks", "thx", "ty", "arigato"]):
        return f"You're very welcome, {author_name}! Let me know if you need anything else."

    # 12. Bot Help / Prefix
    if any(phrase in low for phrase in ["help", "commands", "prefix"]):
        prefix = ctx_data.get("bot", {}).get("prefix", "$") if ctx_data else "$"
        return f"Type `{prefix}help` to explore all my music, security, anime GIFs, economy, and utility features!"

    # 13. General conversation reflection
    responses = [
        f"Regarding **\"{safe_prompt}\"**: That makes sense, {display_author}! Let me know if you'd like to chat more or need help with anything.",
        f"I hear you, {display_author}! Feel free to ask me anything or type `$help` to explore all my commands.",
        f"Understood, {display_author}! I'm right here whenever you want to chat, chill, or listen to music."
    ]
    chosen_resp = random.choice(responses)
    if tone_profile:
        from utils.ai_tone_engine import format_smart_fallback_for_tone
        return format_smart_fallback_for_tone(chosen_resp, tone_profile, display_author)
    return chosen_resp


# ─────────────────────────────────────────────────────────────
# Response Sanitization & Mention Guard
# ─────────────────────────────────────────────────────────────

def sanitize_ai_response(text: str) -> str:
    """Cleans up raw AI outputs to maintain Yuna's consistent brand, safety, and persona."""
    if not text:
        return ""
    cleaned = text.strip()
    # Mask Discord mass mentions to prevent mention abuse or raid attacks
    cleaned = re.sub(r"@everyone\b", "@\u200beveryone", cleaned)
    cleaned = re.sub(r"@here\b", "@\u200bhere", cleaned)
    # Strip prompt leaks or internal instruction echoes
    cleaned = re.sub(r"(?i)--- (?:REAL-TIME (?:LIVE DISCORD CONTEXT|TEMPORAL ANCHOR & SYSTEM CLOCK)|VERIFIED REAL-TIME SEARCH EVIDENCE|LIVE SEARCH STATUS|USER (?:LONG-TERM MEMORY|CORRECTION / CHALLENGE GUIDANCE)|CONVERSATION RECOVERY & NO-REPETITION DIRECTIVE|INSTRUCTIONS|CURRENT TURN GUIDANCE|DYNAMIC TONE EVOLUTION & EXPRESSIVE DELIVERY GUIDANCE) ---.*?-{10,}(?:\n+|\Z)", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"(?i)^(?:Active Delivery Style|Conversation Stage|CRITICAL HYGIENE RULES):.*?(?:\n|$)", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"(?i)CRITICAL (?:REAL-TIME ACCURACY|TEMPORAL & ACCURACY) RULES:.*?(?:\n\n|\Z)", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"(?i)(?:SEARCH EVIDENCE USAGE|LIMITATION HANDLING|CORRECTION) RULES:.*?(?:\n\n|\Z)", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"^-{5,}\s*", "", cleaned.strip())
    # Strip robotic boilerplate apologies and generic endings
    cleaned = re.sub(r"(?i)^(?:I apologize for (?:the |any )?(?:confusion|inconvenience|misunderstanding)[.,!]?\s*)+", "", cleaned)
    cleaned = re.sub(r"(?i)\b(?:As an AI language model|As an AI developed by|As an artificial intelligence)[,.]?\s*", "", cleaned)
    cleaned = re.sub(r"(?i)\n*(?:Let me know if (?:you need|you have) (?:any other|anything else|any questions)[^.\n]*[.!]\s*)$", "", cleaned)
    cleaned = re.sub(r"(?i)\n*(?:Hope this helps[.!]\s*)$", "", cleaned)
    # Persona sanitization
    cleaned = re.sub(r"\b(?:I am|I'm)\s+(?:an?\s+)?ChatGPT\b", "I'm **YUNΛ**", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bChatGPT\b", "YUNΛ AI", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:built|created|trained)\s+by\s+OpenAI\b", "created by Yuna Development", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bOpenAI\b", "Yuna Development", cleaned, flags=re.IGNORECASE)
    # Strip potential leaked API keys (e.g. gsk_..., AQ...., AIza...)
    cleaned = re.sub(r"\b(?:gsk_[a-zA-Z0-9]{30,}|AIza[0-9A-Za-z-_]{35}|AQ\.[a-zA-Z0-9_-]{40,})\b", "[REDACTED_KEY]", cleaned)
    # Truncate safely if too long (max 1950 chars to fit Discord single message nicely)
    if len(cleaned) > 1950:
        cleaned = cleaned[:1940] + "..."
    return cleaned.strip()


# ─────────────────────────────────────────────────────────────
# Main AI Reply Generation
# ─────────────────────────────────────────────────────────────

async def generate_ai_reply(
    prompt: str,
    session_id: Optional[str] = None,
    author_name: str = "Friend",
    ctx_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> str:
    """
    Unified AI generation function with live real-time Discord context awareness, long-term user memory,
    lightweight language detection, Tanglish/multilingual intelligence, and intent-aware response shaping.
    Tries Google Gemini -> Groq -> OpenAI -> DeepSeek -> OpenRouter -> Pollinations -> Smart Fallback.
    Stores both user prompt and AI reply in persistent memory for multi-turn context.
    """
    clean_p = prompt.strip()
    history = await memory.get_history_async(session_id) if session_id else []

    # 1. Resolve User ID for Long-Term Cognitive Memory Profile
    target_user_id = user_id
    if not target_user_id:
        if ctx_data and ctx_data.get("author") and ctx_data["author"].get("id"):
            try:
                target_user_id = int(ctx_data["author"]["id"])
            except (ValueError, TypeError):
                pass
        elif session_id and "_" in session_id and not session_id.startswith("channel_"):
            try:
                target_user_id = int(session_id.split("_")[-1])
            except (ValueError, TypeError):
                pass

    user_mem = None
    memory_block = ""
    effective_name = author_name
    user_lang_pref = None

    # 2. Fetch and apply persistent long-term memory
    if target_user_id:
        try:
            user_mem = await memory_manager.get_user_memory(target_user_id)
            if user_mem.get("preferred_name"):
                effective_name = user_mem["preferred_name"]
            user_lang_pref = user_mem.get("language_preference")
            memory_block = format_user_memory_for_prompt(user_mem, effective_name)

            # Record interaction count & last seen
            await memory_manager.record_interaction(target_user_id, effective_name)

            # Learn any personal details, favorites, facts, or language preferences from this message in background
            asyncio.create_task(memory_manager.extract_and_learn_facts(target_user_id, clean_p, effective_name))
        except Exception as e:
            logger.debug(f"[User Memory Load Error] {e}")

    # 3. Detect Language and Intent with lightweight zero-API detector
    detected_lang, lang_conf = detect_language(clean_p)
    detected_intent = classify_intent(clean_p)
    explicit_lang = is_explicit_language_request(clean_p)

    # Determine effective language: explicit request overrides stored preference; stored preference overrides auto-detect
    if explicit_lang:
        effective_lang = explicit_lang
        if target_user_id:
            try:
                asyncio.create_task(memory_manager.set_language_preference(target_user_id, explicit_lang))
            except Exception:
                pass
    elif user_lang_pref:
        effective_lang = user_lang_pref
    else:
        effective_lang = detected_lang

    # 4. Resolve Dynamic Tone Profile & Turn Continuity (Gradual Evolution & Context Cues)
    user_tone_pref = user_mem.get("preferences", {}).get("tone_preference") if user_mem else None
    from utils.ai_tone_engine import resolve_tone_profile, analyze_turn_context
    turn_ctx = analyze_turn_context(clean_p, history, detected_lang=effective_lang)
    tone_profile = resolve_tone_profile(
        clean_p,
        history,
        detected_lang=effective_lang,
        detected_intent=detected_intent,
        user_tone_pref=user_tone_pref
    )

    # If user explicitly asked to save/remember their tone preference:
    if tone_profile.explicit_override and target_user_id:
        if any(w in clean_p.lower() for w in ["remember my tone", "always use", "default tone", "save tone", "set my tone"]):
            try:
                asyncio.create_task(memory_manager.set_tone_preference(target_user_id, tone_profile.explicit_override))
            except Exception:
                pass

    # 5. Temporal Anchor, Live Search Grounding & Correction Handling
    clock = get_current_runtime_date()
    curr_year = clock["year"]
    is_correction = is_user_correction_or_challenge(clean_p)
    is_repeated = check_if_repeated_query(history, clean_p)
    needs_search, search_query = needs_live_search(clean_p, curr_year)
    search_evidence = None
    search_attempted_empty = False

    if needs_search:
        try:
            results = await perform_live_web_search(search_query)
            if results:
                search_evidence = results
            else:
                search_attempted_empty = True
        except Exception as e:
            logger.debug(f"[Live Search Failure] {e}")
            search_attempted_empty = True

    # 6. Build System Prompt with rich live context, memory, turn guidance, conversational continuity, temporal anchor, and live search evidence
    system_prompt = build_yuna_system_prompt(
        ctx_data,
        user_memory_block=memory_block,
        detected_lang=effective_lang,
        detected_intent=detected_intent,
        user_lang_pref=user_lang_pref,
        tone_profile=tone_profile,
        turn_context=turn_ctx,
        runtime_date=clock,
        search_evidence=search_evidence,
        search_attempted_empty=search_attempted_empty,
        is_correction=is_correction,
        is_repeated=is_repeated,
        search_query=search_query
    )

    # For multi-user channel/VC sessions, identify the speaker to the AI model
    prompt_for_ai = f"{effective_name}: {clean_p}" if (session_id and session_id.startswith("channel_")) else clean_p

    reply = None
    # 1. Check Google Gemini (Free Tier: 15 RPM, high quality with selective Google Search grounding)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        reply = await _call_gemini(
            prompt_for_ai,
            history,
            gemini_key,
            system_prompt=system_prompt,
            enable_grounding=needs_search
        )

    # 2. Check Groq Cloud (Free Tier: 30 RPM, ultra-fast Llama-3.3-70b with injected verified search evidence)
    if not reply:
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            reply = await _call_groq(prompt_for_ai, history, groq_key, system_prompt=system_prompt)

    # 3. Check OpenAI (GPT-4o-mini)
    if not reply:
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            reply = await _call_openai(prompt_for_ai, history, openai_key, system_prompt=system_prompt)

    # 4. Check DeepSeek (DeepSeek V3 / R1)
    if not reply:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            reply = await _call_deepseek(prompt_for_ai, history, deepseek_key, system_prompt=system_prompt)

    # 5. Check OpenRouter (Universal Multi-Model Provider)
    if not reply:
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            reply = await _call_openrouter(prompt_for_ai, history, openrouter_key, system_prompt=system_prompt)

    # 6. Check Pollinations (with full history & multi-key rotation)
    if not reply:
        try:
            from utils.ai_utils import get_pollinations_api_keys
            poll_keys = get_pollinations_api_keys()
        except Exception:
            poll_keys = []
        if not poll_keys:
            env_single = os.getenv("POLLINATIONS_API_KEY")
            poll_keys = [env_single] if env_single else [None]

        for k in poll_keys:
            reply = await _call_pollinations(prompt_for_ai, history, k, system_prompt=system_prompt)
            if reply:
                break

    # 7. Contextual Multilingual Fallback with Real-Time Live Data, User Memory & Tone Adaptation
    if not reply:
        reply = _get_smart_fallback_response(
            clean_p,
            effective_name,
            ctx_data=ctx_data,
            user_mem=user_mem,
            lang_code=effective_lang,
            tone_profile=tone_profile,
            history=history,
            search_evidence=search_evidence,
            search_attempted_empty=search_attempted_empty,
            is_correction=is_correction,
            is_repeated=is_repeated,
            runtime_date=clock
        )

    final_reply = sanitize_ai_response(reply)

    # 8. Anti-Repetition Guard (Prevent verbatim identical replies to the immediately preceding assistant turn)
    if history and final_reply:
        last_asst_msgs = [m["content"] for m in history if m.get("role") == "assistant"]
        if last_asst_msgs:
            last_asst = last_asst_msgs[-1].strip().lower()
            if final_reply.strip().lower() == last_asst:
                if is_correction or is_repeated:
                    if effective_lang == "tanglish":
                        final_reply = "Puriyuthu da, munaadi sonna maadhiri thaan. Vera edhavathu discuss panlama?"
                    elif effective_lang == "ta":
                        final_reply = "புரிகிறது, முன்பு குறிப்பிட்டது போல் தான். வேறு எதைப் பற்றியாவது பேசலாமா?"
                    elif effective_lang == "hinglish":
                        final_reply = "Samajh rahi hoon, jaise pehle bataya tha. Kuch aur baat karein?"
                    else:
                        final_reply = "Understood — as noted earlier, I want to be upfront about what I can verify right now. What else would you like to explore?"

    # Store both sides of the conversation for multi-turn context (persists to SQLite)
    if session_id:
        stored_user_msg = f"{effective_name}: {clean_p}" if session_id.startswith("channel_") else clean_p
        memory.add_message(session_id, "user", stored_user_msg)
        memory.add_message(session_id, "assistant", final_reply)

    return final_reply


def get_ai_status() -> Dict[str, Any]:
    """Returns the configuration status and active priority of AI providers (with masked keys)."""
    providers = [
        ("Google Gemini", os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        ("Groq Cloud", os.getenv("GROQ_API_KEY")),
        ("OpenAI", os.getenv("OPENAI_API_KEY")),
        ("DeepSeek", os.getenv("DEEPSEEK_API_KEY")),
        ("OpenRouter", os.getenv("OPENROUTER_API_KEY")),
        ("Pollinations AI", os.getenv("POLLINATIONS_API_KEY")),
    ]
    status = {}
    active_primary = None
    for name, key in providers:
        if key and str(key).strip():
            clean_k = str(key).strip()
            masked = clean_k[:6] + "..." + clean_k[-4:] if len(clean_k) > 10 else "***"
            status[name] = {"enabled": True, "masked": masked}
            if not active_primary:
                active_primary = name
        else:
            status[name] = {"enabled": False, "masked": None}

    return {
        "primary": active_primary or "Smart Fallback Engine",
        "providers": status
    }


def set_ai_api_key(provider: str, api_key: str, env_path: Optional[str] = None) -> Tuple[bool, str]:
    """Dynamically sets an AI API key in memory and persists it to the .env file."""
    mapping = {
        "gemini": "GEMINI_API_KEY",
        "google": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "pollinations": "POLLINATIONS_API_KEY",
    }
    env_var = mapping.get(provider.lower().strip())
    if not env_var:
        valid_names = ", ".join(sorted(set(mapping.values())))
        return False, f"Unknown provider `{provider}`. Valid options: {valid_names}"

    clean_key = api_key.strip()
    os.environ[env_var] = clean_key

    # Persist to .env
    target_env = env_path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(target_env):
        try:
            with open(target_env, "r", encoding="utf-8") as f:
                content = f.read()

            pattern = rf'^{env_var}=.*$'
            replacement = f'{env_var}="{clean_key}"'
            if re.search(pattern, content, flags=re.MULTILINE):
                new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            else:
                new_content = content.rstrip() + f'\n{replacement}\n'

            with open(target_env, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            logger.error(f"Failed to persist {env_var} to {target_env}: {e}")
            return True, f"Key set in runtime memory, but failed to write to `.env`: {e}"

    return True, f"Successfully set `{env_var}` and saved to `.env`!"
