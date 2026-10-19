"""
YUNA AI Persistent User Memory & Cognitive Profile System
Provides long-term, cross-session user memory for YUNA AI:
1. Remembers user's preferred name / nickname
2. Remembers user's language preferences (Tanglish, Tamil, Hindi, English, etc.)
3. Remembers user's favorite things (anime, games, songs, food, etc.)
4. Extracts and remembers personal facts, hobbies, pets, and background
5. Persistent conversation history & episodic summaries across restarts
6. Injects rich personalized context into AI prompts
7. Provides user commands ($aichat memory, $aichat remember, $aichat forget, $aichat setname, $aichat lang)
"""

import os
import re
import time
import json
import logging
from typing import Optional, Dict, List, Any, Tuple
from collections import OrderedDict
import aiosqlite
import discord
from utils.lang_detect import is_explicit_language_request, get_lang_display

logger = logging.getLogger("YunaAIMemory")

DATABASE_PATH = "db/ai_memory.db"
MAX_CACHE_SIZE = 1000


class AIMemoryManager:
    """Manages persistent SQLite memory profiles with an LRU in-memory cache and cross-session persistence."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        # In-memory LRU cache: user_id -> Dict[str, Any]
        self._cache: OrderedDict[int, Dict[str, Any]] = OrderedDict()
        self._initialized = False

    async def init_db(self):
        """Initializes database schema and runs migrations."""
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_ai_profile (
                    user_id INTEGER PRIMARY KEY,
                    preferred_name TEXT,
                    gender_pronouns TEXT,
                    language_preference TEXT,
                    interaction_count INTEGER DEFAULT 0,
                    last_seen REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Migration: ensure language_preference column exists in user_ai_profile
            async with db.execute("PRAGMA table_info(user_ai_profile)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if "language_preference" not in columns:
                    try:
                        await db.execute("ALTER TABLE user_ai_profile ADD COLUMN language_preference TEXT DEFAULT NULL;")
                    except Exception as e:
                        logger.debug(f"[Migration Note] Column add: {e}")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_ai_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    category TEXT DEFAULT 'general',
                    fact TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, fact)
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_ai_preferences (
                    user_id INTEGER NOT NULL,
                    pref_key TEXT NOT NULL,
                    pref_val TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, pref_key)
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_ai_episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER,
                    topic TEXT,
                    summary TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_episodes_user ON user_ai_episodes(user_id, id DESC);")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS ai_channel_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_ai_history_session ON ai_channel_history(session_id, created_at);")

            await db.commit()
        self._initialized = True

    def _cache_put(self, user_id: int, data: Dict[str, Any]):
        """Inserts or updates data in the LRU cache with eviction."""
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
        self._cache[user_id] = data
        if len(self._cache) > MAX_CACHE_SIZE:
            self._cache.popitem(last=False)

    async def get_user_memory(self, user_id: int) -> Dict[str, Any]:
        """Fetches full persistent memory profile for a user with cache fallback."""
        if not self._initialized:
            await self.init_db()

        if user_id in self._cache:
            self._cache.move_to_end(user_id)
            return self._cache[user_id]

        profile_data: Dict[str, Any] = {
            "user_id": user_id,
            "preferred_name": None,
            "gender_pronouns": None,
            "language_preference": None,
            "interaction_count": 0,
            "last_seen": None,
            "preferences": {},
            "facts": [],
            "episodes": []
        }

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 1. Profile
                async with db.execute(
                    "SELECT preferred_name, gender_pronouns, language_preference, interaction_count, last_seen FROM user_ai_profile WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        profile_data["preferred_name"] = row[0]
                        profile_data["gender_pronouns"] = row[1]
                        profile_data["language_preference"] = row[2]
                        profile_data["interaction_count"] = row[3] or 0
                        profile_data["last_seen"] = row[4]

                # 2. Preferences (favorites, etc.)
                async with db.execute(
                    "SELECT pref_key, pref_val FROM user_ai_preferences WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    for k, v in rows:
                        profile_data["preferences"][k] = v

                # 3. Facts
                async with db.execute(
                    "SELECT fact FROM user_ai_facts WHERE user_id = ? ORDER BY id DESC LIMIT 15",
                    (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    profile_data["facts"] = [r[0] for r in rows]

                # 4. Recent episodic summaries
                async with db.execute(
                    "SELECT topic, summary FROM user_ai_episodes WHERE user_id = ? ORDER BY id DESC LIMIT 3",
                    (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    profile_data["episodes"] = [{"topic": r[0], "summary": r[1]} for r in rows]

            self._cache_put(user_id, profile_data)
        except Exception as e:
            logger.error(f"[AI Memory Error] Failed to fetch user memory {user_id}: {e}")

        return profile_data

    async def record_interaction(self, user_id: int, author_name: Optional[str] = None):
        """Increments conversation count and updates last_seen timestamp."""
        if not self._initialized:
            await self.init_db()

        now = time.time()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO user_ai_profile (user_id, interaction_count, last_seen, updated_at)
                    VALUES (?, 1, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        interaction_count = interaction_count + 1,
                        last_seen = excluded.last_seen,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, now))
                await db.commit()

            if user_id in self._cache:
                self._cache[user_id]["interaction_count"] = self._cache[user_id].get("interaction_count", 0) + 1
                self._cache[user_id]["last_seen"] = now
        except Exception as e:
            logger.debug(f"[AI Memory] record_interaction error: {e}")

    async def set_preferred_name(self, user_id: int, name: str) -> bool:
        """Sets a user's preferred name / nickname for Yuna to use."""
        if not self._initialized:
            await self.init_db()

        clean_name = name.strip()[:50]
        if not clean_name:
            return False

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO user_ai_profile (user_id, preferred_name, interaction_count, last_seen, updated_at)
                    VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        preferred_name = excluded.preferred_name,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, clean_name, time.time()))
                await db.commit()

            if user_id in self._cache:
                self._cache[user_id]["preferred_name"] = clean_name
            return True
        except Exception as e:
            logger.error(f"[AI Memory] set_preferred_name error: {e}")
            return False

    async def set_language_preference(self, user_id: int, lang_code: Optional[str]) -> bool:
        """Sets a user's explicit preferred language (e.g. 'tanglish', 'ta', 'en', 'hi', or None to reset)."""
        if not self._initialized:
            await self.init_db()

        clean_lang = lang_code.strip().lower() if lang_code else None
        if clean_lang == "auto" or clean_lang == "none" or clean_lang == "reset":
            clean_lang = None

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO user_ai_profile (user_id, language_preference, interaction_count, last_seen, updated_at)
                    VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        language_preference = excluded.language_preference,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, clean_lang, time.time()))
                await db.commit()

            if user_id in self._cache:
                self._cache[user_id]["language_preference"] = clean_lang
            return True
        except Exception as e:
            logger.error(f"[AI Memory] set_language_preference error: {e}")
            return False

    async def get_language_preference(self, user_id: int) -> Optional[str]:
        """Returns the user's explicit language preference if set."""
        mem = await self.get_user_memory(user_id)
        return mem.get("language_preference")

    async def get_tone_preference(self, user_id: int) -> Optional[str]:
        """Returns the user's explicit tone style preference if set (e.g. rugged, lovely, normal)."""
        mem = await self.get_user_memory(user_id)
        return mem.get("preferences", {}).get("tone_preference")

    async def set_tone_preference(self, user_id: int, tone: Optional[str]) -> bool:
        """Sets or resets the user's explicit tone style preference."""
        if not tone or tone.lower().strip() in ("auto", "reset", "none", "default"):
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM user_ai_preferences WHERE user_id = ? AND pref_key = 'tone_preference'", (user_id,))
                    await db.commit()
                if user_id in self._cache:
                    self._cache[user_id]["preferences"].pop("tone_preference", None)
                return True
            except Exception as e:
                logger.error(f"[AI Memory] set_tone_preference delete error: {e}")
                return False
        return await self.set_preference(user_id, "tone_preference", tone.lower().strip())

    async def set_preference(self, user_id: int, key: str, value: str) -> bool:
        """Stores a specific favorite or preference (e.g. favorite_anime)."""
        if not self._initialized:
            await self.init_db()

        clean_k = key.strip().lower()[:50]
        clean_v = value.strip()[:100]
        if not clean_k or not clean_v:
            return False

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO user_ai_preferences (user_id, pref_key, pref_val, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, pref_key) DO UPDATE SET
                        pref_val = excluded.pref_val,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, clean_k, clean_v))
                await db.commit()

            if user_id in self._cache:
                self._cache[user_id]["preferences"][clean_k] = clean_v
            return True
        except Exception as e:
            logger.error(f"[AI Memory] set_preference error: {e}")
            return False

    async def add_fact(self, user_id: int, fact: str, category: str = "general") -> bool:
        """Adds a permanent remembered fact about the user."""
        if not self._initialized:
            await self.init_db()

        clean_f = fact.strip()[:200]
        if not clean_f or len(clean_f) < 3:
            return False

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR IGNORE INTO user_ai_facts (user_id, category, fact)
                    VALUES (?, ?, ?);
                """, (user_id, category, clean_f))
                await db.commit()

            if user_id in self._cache:
                if clean_f not in self._cache[user_id]["facts"]:
                    self._cache[user_id]["facts"].insert(0, clean_f)
                    if len(self._cache[user_id]["facts"]) > 15:
                        self._cache[user_id]["facts"].pop()
            return True
        except Exception as e:
            logger.error(f"[AI Memory] add_fact error: {e}")
            return False

    async def add_episode(self, user_id: int, summary: str, topic: Optional[str] = None, channel_id: Optional[int] = None) -> bool:
        """Stores a high-level episodic summary of a past conversation topic."""
        if not self._initialized:
            await self.init_db()

        clean_summary = summary.strip()[:300]
        if not clean_summary:
            return False

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO user_ai_episodes (user_id, channel_id, topic, summary)
                    VALUES (?, ?, ?, ?);
                """, (user_id, channel_id, topic[:100] if topic else None, clean_summary))
                await db.commit()

            if user_id in self._cache:
                self._cache[user_id]["episodes"].insert(0, {"topic": topic, "summary": clean_summary})
                if len(self._cache[user_id]["episodes"]) > 3:
                    self._cache[user_id]["episodes"].pop()
            return True
        except Exception as e:
            logger.error(f"[AI Memory] add_episode error: {e}")
            return False

    async def save_history_message(self, session_id: str, role: str, content: str):
        """Persists a conversation turn into SQLite so sessions survive bot reboots."""
        if not self._initialized:
            await self.init_db()

        clean_c = content.strip()
        if not clean_c:
            return

        now = time.time()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO ai_channel_history (session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?);
                """, (session_id, role, clean_c, now))
                # Prune older messages beyond 20 turns for this session
                await db.execute("""
                    DELETE FROM ai_channel_history WHERE id IN (
                        SELECT id FROM ai_channel_history WHERE session_id = ?
                        ORDER BY id DESC LIMIT -1 OFFSET 20
                    );
                """, (session_id,))
                await db.commit()
        except Exception as e:
            logger.debug(f"[AI Memory] save_history_message error: {e}")

    async def load_history_messages(self, session_id: str, max_messages: int = 10, ttl_seconds: float = 300) -> List[Dict[str, str]]:
        """Loads recent conversation history from SQLite for active sessions."""
        if not self._initialized:
            await self.init_db()

        cutoff = time.time() - ttl_seconds
        results: List[Dict[str, str]] = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT role, content FROM ai_channel_history
                    WHERE session_id = ? AND created_at >= ?
                    ORDER BY id ASC LIMIT ?;
                """, (session_id, cutoff, max_messages)) as cursor:
                    rows = await cursor.fetchall()
                    for r, c in rows:
                        results.append({"role": r, "content": c})
        except Exception as e:
            logger.debug(f"[AI Memory] load_history_messages error: {e}")

        return results

    async def clear_history(self, session_id: str):
        """Removes stored conversation turns for a session."""
        if not self._initialized:
            await self.init_db()
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM ai_channel_history WHERE session_id = ?", (session_id,))
                await db.commit()
        except Exception as e:
            logger.debug(f"[AI Memory] clear_history error: {e}")

    async def clear_user_memory(self, user_id: int) -> bool:
        """Deletes all remembered data for a user (privacy / reset command)."""
        if not self._initialized:
            await self.init_db()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM user_ai_profile WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM user_ai_facts WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM user_ai_preferences WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM user_ai_episodes WHERE user_id = ?", (user_id,))
                await db.commit()

            self._cache.pop(user_id, None)
            return True
        except Exception as e:
            logger.error(f"[AI Memory] clear_user_memory error: {e}")
            return False

    async def extract_and_learn_facts(self, user_id: int, text: str, author_name: str) -> List[str]:
        """
        Fast local pattern extraction to automatically capture personal user details,
        favorites, hobbies, facts, and language preferences from natural chat messages.
        """
        learned = []
        raw = text.strip()
        low = raw.lower()

        # 1. Explicit Language Switch / Preference: "reply in tanglish", "tamil la pesu", etc.
        target_lang = is_explicit_language_request(raw)
        if target_lang:
            await self.set_language_preference(user_id, target_lang)
            learned.append(f"Language preference set to: {get_lang_display(target_lang)}")

        # 2. Explicit Remember Requests: "remember that I...", "please remember...", "don't forget that..."
        remember_match = re.search(r"(?:please\s+)?(?:remember(?:\s+that)?|don't\s+forget(?:\s+that)?)\s+(.+)", raw, re.IGNORECASE)
        if remember_match:
            fact_candidate = remember_match.group(1).strip().rstrip(".!")
            if len(fact_candidate) > 3:
                await self.add_fact(user_id, fact_candidate, category="explicit")
                learned.append(f"Remembered: {fact_candidate}")

        # 3. Preferred Name: "my name is Alex", "call me Alex", "i am called Alex"
        name_match = re.search(r"\b(?:my name is|call me|i'm called|i am called)\s+([A-Z][a-zA-Z0-9_\s]{1,25})\b", raw)
        if not name_match:
            name_match = re.search(r"\b(?:my name is|call me)\s+([a-zA-Z0-9_]{2,20})\b", low)
        if name_match:
            candidate = name_match.group(1).strip().title()
            if candidate.lower() not in {"yuna", "bot", "what", "who", "user", "friend", "not", "why"}:
                await self.set_preferred_name(user_id, candidate)
                learned.append(f"Preferred name set to: {candidate}")

        # 4. Specific Favorites
        fav_patterns = [
            (r"\bmy fav(?:orite)? anime is ([^.!?\n,]+)", "favorite_anime", "Favorite Anime"),
            (r"\bmy fav(?:orite)? game is ([^.!?\n,]+)", "favorite_game", "Favorite Game"),
            (r"\bmy fav(?:orite)? (?:song|music|band|artist) is ([^.!?\n,]+)", "favorite_music", "Favorite Music"),
            (r"\bmy fav(?:orite)? food is ([^.!?\n,]+)", "favorite_food", "Favorite Food"),
            (r"\bmy fav(?:orite)? (?:movie|film|show|series) is ([^.!?\n,]+)", "favorite_movie", "Favorite Movie/Show"),
            (r"\bmy fav(?:orite)? (?:color|colour) is ([^.!?\n,]+)", "favorite_color", "Favorite Color"),
            (r"\bmy fav(?:orite)? character is ([^.!?\n,]+)", "favorite_character", "Favorite Character"),
        ]
        for pattern, key, label in fav_patterns:
            m = re.search(pattern, raw, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if 2 <= len(val) <= 60:
                    await self.set_preference(user_id, key, val)
                    learned.append(f"{label}: {val}")

        # 5. Hobbies, Gaming & Activities: "i love playing X", "i like playing X"
        game_play_match = re.search(r"\bi\s+(?:love|enjoy|like|play)\s+playing\s+([^.!?\n,]+)", raw, re.IGNORECASE)
        if game_play_match:
            game_title = game_play_match.group(1).strip()
            if 2 <= len(game_title) <= 50:
                fact_str = f"Plays and enjoys {game_title}"
                await self.add_fact(user_id, fact_str, category="interest")
                learned.append(fact_str)

        # 6. Work / Profession / Studies
        prof_match = re.search(r"\bi\s+(?:work as|am studying|study)\s+([^.!?\n,]+)", raw, re.IGNORECASE)
        if prof_match:
            job_desc = prof_match.group(1).strip()
            if 3 <= len(job_desc) <= 50:
                fact_str = f"Studies or works in {job_desc}"
                await self.add_fact(user_id, fact_str, category="work")
                learned.append(fact_str)

        prof_iam_match = re.search(r"\bi'?m\s+(?:a|an)\s+(developer|programmer|coder|student|designer|gamer|musician|doctor|engineer|artist|teacher)\b", raw, re.IGNORECASE)
        if prof_iam_match:
            role_word = prof_iam_match.group(1).strip().capitalize()
            fact_str = f"Identifies as a {role_word}"
            await self.add_fact(user_id, fact_str, category="work")
            learned.append(fact_str)

        # 7. Pets: "my dog's name is X", "i have a cat named X"
        pet_match = re.search(r"\b(?:my\s+(dog|cat|bird|pet)(?:'s)?\s+name\s+is|i\s+have\s+a\s+(dog|cat|bird|pet)\s+named)\s+([A-Za-z0-9_]{2,25})\b", raw, re.IGNORECASE)
        if pet_match:
            pet_type = (pet_match.group(1) or pet_match.group(2) or "pet").capitalize()
            pet_name = pet_match.group(3).strip().capitalize()
            fact_str = f"Has a {pet_type} named {pet_name}"
            await self.add_fact(user_id, fact_str, category="pet")
            learned.append(fact_str)

        # 8. Birthday: "my birthday is on July 4th", "my birthday is July 4"
        bday_match = re.search(r"\bmy\s+birthday\s+is\s+(?:on\s+)?([A-Za-z0-9_\s]{3,30})\b", raw, re.IGNORECASE)
        if bday_match:
            bday_str = bday_match.group(1).strip()
            if 3 <= len(bday_str) <= 30:
                await self.set_preference(user_id, "birthday", bday_str)
                learned.append(f"Birthday: {bday_str}")

        # 9. Location / Country: "i live in India", "i am from Germany"
        loc_match = re.search(r"\b(?:i\s+live\s+in|i\s+am\s+from)\s+([A-Z][a-zA-Z\s]{2,30})\b", raw)
        if loc_match:
            country = loc_match.group(1).strip()
            if country.lower() not in {"a house", "the server", "earth", "bed", "discord"}:
                await self.set_preference(user_id, "location", country)
                learned.append(f"Location: {country}")

        return learned


# Global singleton memory manager
memory_manager = AIMemoryManager()


def format_user_memory_for_prompt(user_mem: Dict[str, Any], author_display_name: str) -> str:
    """Formats stored user memory facts cleanly for AI system prompt injection."""
    if not user_mem:
        return ""

    pref_name = user_mem.get("preferred_name")
    lang_pref = user_mem.get("language_preference")
    count = user_mem.get("interaction_count", 0)
    preferences = user_mem.get("preferences", {})
    facts = user_mem.get("facts", [])
    episodes = user_mem.get("episodes", [])

    lines = []
    lines.append("\n--- USER LONG-TERM MEMORY & PERSONAL PROFILE ---")
    if count > 0:
        lines.append(f"You have chatted with this user {count} times before!")
    if pref_name:
        lines.append(f"• Preferred Name / Nickname: '{pref_name}' (Address them by this name!)")
    else:
        lines.append(f"• Discord Name: '{author_display_name}'")

    if lang_pref:
        lang_label = get_lang_display(lang_pref)
        lines.append(f"• User's Explicit Language Preference: {lang_label} (Always reply in this language!)")

    tone_pref = preferences.get("tone_preference")
    if tone_pref:
        lines.append(f"• User's Explicit Tone Style Preference: {tone_pref.capitalize()} (Adopt this delivery style unless addressing technical issues!)")

    if preferences:
        lines.append("• User's Favorite Things & Preferences:")
        for k, v in preferences.items():
            formatted_key = k.replace("_", " ").title()
            lines.append(f"  - {formatted_key}: {v}")

    if facts:
        lines.append("• Remembered Facts About This User:")
        for f in facts[:10]:
            lines.append(f"  - {f}")

    if episodes:
        lines.append("• Past Conversation Memories:")
        for ep in episodes[:3]:
            topic = ep.get("topic") or "General"
            summary = ep.get("summary", "")
            lines.append(f"  - [{topic}] {summary}")

    lines.append("\nHOW TO USE THIS MEMORY:")
    lines.append("1. Greet or address them warmly using their preferred name if set.")
    lines.append("2. If the user asks 'do you remember me?', 'what's my name?', 'what are my favorites?', or similar personal questions, RECALL THESE EXACT STORED FACTS accurately and happily!")
    lines.append("3. If language preference is set, respect it naturally.")
    lines.append("4. Tailor recommendations and friendly banter around their known favorites and hobbies.")
    lines.append("5. Never say 'According to my database' or sound robotic; act like a genuine friend.")
    lines.append("--------------------------------------------------\n")

    return "\n".join(lines)


def build_memory_embed(user: discord.User, user_mem: Dict[str, Any]) -> discord.Embed:
    """Builds a beautiful Discord embed displaying the user's active AI memory profile."""
    pref_name = user_mem.get("preferred_name") or "Not set (using Discord display name)"
    lang_pref = user_mem.get("language_preference")
    count = user_mem.get("interaction_count", 0)
    preferences = user_mem.get("preferences", {})
    facts = user_mem.get("facts", [])
    episodes = user_mem.get("episodes", [])

    lang_text = get_lang_display(lang_pref) if lang_pref else "Automatic (Matches your messages)"

    tone_pref = preferences.get("tone_preference")
    tone_text = tone_pref.capitalize() if tone_pref else "Adaptive (Gradual Context Evolution)"

    embed = discord.Embed(
        title="🌸 YUNΛ AI • Your Personal Memory Profile",
        description=(
            f"Here is everything Yuna remembers about **{user.display_name}** across conversations!\n\n"
            f"• **Preferred Name:** `{pref_name}`\n"
            f"• **Preferred Language:** `{lang_text}`\n"
            f"• **Tone Style:** `{tone_text}`\n"
            f"• **Conversations Remembered:** `{count}` interactions\n"
        ),
        color=0x7C3AED
    )

    if preferences:
        fav_lines = []
        for k, v in preferences.items():
            if k == "tone_preference":
                continue
            k_clean = k.replace("_", " ").title()
            fav_lines.append(f"• **{k_clean}:** {v}")
        if fav_lines:
            embed.add_field(
                name="💖 Favorite Things",
                value="\n".join(fav_lines),
                inline=False
            )

    if facts:
        fact_lines = [f"• {f}" for f in facts[:10]]
        embed.add_field(
            name="📝 Remembered Notes & Facts",
            value="\n".join(fact_lines),
            inline=False
        )
    else:
        embed.add_field(
            name="📝 Remembered Notes & Facts",
            value="*No specific facts stored yet! Tell Yuna facts naturally or use `$aichat remember <fact>`.*",
            inline=False
        )

    if episodes:
        ep_lines = [f"• **{ep.get('topic') or 'Topic'}:** {ep.get('summary')}" for ep in episodes[:3]]
        embed.add_field(
            name="💭 Past Conversation Topics",
            value="\n".join(ep_lines),
            inline=False
        )

    embed.add_field(
        name="🛠️ Memory Controls",
        value=(
            "• `$aichat remember <fact>` — Tell Yuna to remember something\n"
            "• `$aichat setname <nickname>` — Set how Yuna addresses you\n"
            "• `$aichat lang <language>` — Set preferred language (e.g. `tanglish`, `tamil`, `auto`)\n"
            "• `$aichat tone <style>` — Set tone delivery (e.g. `rugged`, `lovely`, `cinematic`, `auto`)\n"
            "• `$aichat forget` — Clear your stored profile & reset memory"
        ),
        inline=False
    )

    user_icon = user.display_avatar.url if user.display_avatar else None
    embed.set_thumbnail(url=user_icon)
    embed.set_footer(text="Yuna Cognitive Memory Engine • Real-Time Learning", icon_url=user_icon)
    return embed
