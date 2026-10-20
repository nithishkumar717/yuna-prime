import os
import json
import re
import discord
from typing import Union, Optional, Any

# Map of numeric and alphabet emoji keys
NUMERIC_EMOJIS = {
    "0": "0️⃣", "zero": "0️⃣",
    "1": "1️⃣", "one": "1️⃣",
    "2": "2️⃣", "two": "2️⃣",
    "3": "3️⃣", "three": "3️⃣",
    "4": "4️⃣", "four": "4️⃣",
    "5": "5️⃣", "five": "5️⃣",
    "6": "6️⃣", "six": "6️⃣",
    "7": "7️⃣", "seven": "7️⃣",
    "8": "8️⃣", "eight": "8️⃣",
    "9": "9️⃣", "nine": "9️⃣",
    "10": "🔟", "ten": "🔟",
}

ALPHABET_EMOJIS = {
    "a": "🇦", "b": "🇧", "c": "🇨", "d": "🇩", "e": "🇪", "f": "🇫",
    "g": "🇬", "h": "🇭", "i": "🇮", "j": "🇯", "k": "🇰", "l": "🇱",
    "m": "🇲", "n": "🇳", "o": "🇴", "p": "🇵", "q": "🇶", "r": "🇷",
    "s": "🇸", "t": "🇹", "u": "🇺", "v": "🇻", "w": "🇼", "x": "🇽",
    "y": "🇾", "z": "🇿"
}

# Comprehensive maps for ALL types of emojis
CATEGORIZED_EMOJIS = {
    # 🛡️ Security & Moderation
    "shield": "🛡️", "mod": "🛡️", "admin": "🛡️", "security": "🛡️",
    "crown": "👑", "owner": "👑", "king": "👑",
    "ban": "🔨", "hammer": "🔨", "kick": "👢", "mute": "🔇", "timeout": "⏱️",
    "lock": "🔒", "unlock": "🔓", "key": "🔑", "badge": "🏷️",

    # 🎵 Music & Audio Controls
    "play": "▶️", "pause": "⏸️", "stop": "⏹️", "skip": "⏭️", "next": "⏭️",
    "previous": "⏮️", "prev": "⏮️", "loop": "🔁", "repeat": "🔁",
    "shuffle": "🔀", "volume": "🔊", "vol": "🔊", "music": "🎵", "song": "🎶",
    "track": "💿", "playlist": "📜", "queue": "📜", "radio": "📻", "headphone": "🎧",

    # 🏹 Navigation & UI
    "home": "🏠", "left": "◀️", "right": "▶️", "up": "🔼", "down": "🔽",
    "refresh": "🔄", "reload": "🔄", "pin": "📌", "link": "🔗",
    "search": "🔍", "info": "ℹ️", "help": "❓", "ping": "📡",

    # 🎮 Games, Fun & Rewards
    "game": "🎮", "controller": "🎮", "dice": "🎲", "trophy": "🏆",
    "giveaway": "🎉", "tada": "🎉", "gift": "🎁", "fire": "🔥",
    "sparkles": "✨", "star": "⭐", "heart": "❤️", "coin": "🪙",
    "money": "💵", "cards": "🃏", "clown": "🤡",

    # 🛠️ Utility & Channels
    "gear": "⚙️", "gears": "⚙️", "settings": "⚙️", "bin": "🗑️", "trash": "🗑️",
    "channel": "💬", "text_channel": "💬", "voice_channel": "🔊",
    "role": "🎭", "user": "👤", "member": "👤", "bot": "🤖", "clock": "⏰",
}

ANIMATED_TICK = "<a:tick:1562100631605350441>"
ANTINUKE_TICK = "<:antinuke_tick:1562101296939409458>"
ANIMATED_CROSS = "<:cross:1562101096686686218>"
STATIC_TICK = "<a:tick:1562100631605350441>"
ANIMATED_SETTINGS = "<a:settings:1562101136234651679>"
STATIC_MOD = "<:mod:1562101121248530473>"
ANIMATED_ENABLED = "<a:enable:1562101109869252740>"
STATIC_DISABLED = "<:yuna_disable:1562099874865094726>"
STATIC_PREVIOUS = "<:previous:1548595151755026442>"
STATIC_NEXT = "<:next:1548595448602693652>"
STATIC_LOOP = "<:loop:1548594863530971196>"
STATIC_PLAYPAUSE = "<:playpause:1548638534573752381>"
STATIC_SHUFFLE = "<:shuffle:1554917090366849024>"
STATIC_HISTORY = "<:history:1554924675035959347>"
STATIC_LANG = "<:lang:1554925676321050624>"
STATIC_SONGRESUME = "<:songresume:1554927027545440306>"
STATIC_SONGMOOD = "<:songmood:1554929086579609780>"
STATIC_SONGFILTER = "<:songfilter:1554929878774718495>"
STATIC_SONGQUEUE = "<:songqueue:1554930299706802247>"
STATIC_ADDSONG = "<:addsong:1554930526228455575>"
STATIC_247MODE = "<:247mode:1554930825014022144>"
STATIC_PLAYLIST = "<:playlist:1554930999085895680>"
STATIC_MUTE = "<:mute:1557204695284711516>"
STATIC_MUTEALL = "<:muteall:1554932785284776076>"
STATIC_UNMUTEALL = "<:unmuteall:1557210238162182175>"
STATIC_DEAFEN = "<:deafen:1557206833012277288>"
STATIC_UNDEAFEN = "<:undeafen:1557208136509820948>"
STATIC_LOCK = "<:lock:1562101260616732683>"
STATIC_UNLOCK = "<:unlock:1562101269341151413>"
STATIC_HIDEVC = "<:hidevc:1557214632920227872>"
STATIC_KICKVC = "<:kickvc:1557215509559124039>"
ANIMATED_LOADING = "<a:loading:1562101208842506370>"
ANIMATED_KING = "<a:crown:1562101197689725050>"
ANIMATED_CROWN = "<a:crown:1562101197689725050>"
ANIMATED_ALERT = "<a:alert:1562101219051311267>"
ANIMATED_DISC = "<a:yunadisc:1557984542084829284>"
ANIMATED_YUNADISC = "<a:yunadisc:1557984542084829284>"
ANIMATED_ARROW = "<a:arrow:1562101229415440394>"
STATIC_ARROW = "<a:arrow:1562101229415440394>"

# --- Music & Audio Controls ---
ANIMATED_TDMUSIC = "<a:tdmusic:1558031407865929840>"
ANIMATED_STOPMUSIC = "<:stopmusic:1554923334913884250>"
ANIMATED_MUSICSEARCH = "<:musicsearch:1554920989589110884>"
ANIMATED_10SECPLUS = "<:10secplus:1554918644935294986>"
ANIMATED_10SEC = "<:10sec:1554917901969006665>"
ANIMATED_VOLUME = "<:volume:1554911786480697405>"
ANIMATED_MUSICCONTROL = "<:musiccontrol:1551982339393851493>"
ANIMATED_HEART = "<a:heart:1548687259744866314>"
ANIMATED_SPOTIFY = "<:spotify:1547874100519899246>"

# --- Temp Voice Channel Controls ---
ANIMATED_WAITINGROOM = "<:waitingroom:1548704287708815420>"
ANIMATED_UNTRUST = "<:untrust:1548704285649408101>"
ANIMATED_UNBLOCK = "<:unblock:1548704282390298716>"
ANIMATED_TRUST = "<:trust:1548704280222109726>"
ANIMATED_TRANSFER = "<:transfer:1548704278284206230>"
ANIMATED_REGION = "<:region:1548704272034566184>"
ANIMATED_PRIVACY = "<:privacy:1548704268062687282>"
ANIMATED_NAME = "<:name:1548704259980263505>"
ANIMATED_LIMIT = "<:limit:1548704252862537779>"
ANIMATED_KICK = "<:kick:1548704249880383488>"
ANIMATED_INVITE = "<:invite:1548704246499909815>"
ANIMATED_DELETE = "<:delete:1548704238799028306>"
ANIMATED_CLAIM = "<:claim:1548704236307615745>"
ANIMATED_CHAT = "<:chat:1548704229986664570>"
ANIMATED_BLOCK = "<:block:1548704227310706791>"

# --- Badges, Arrows, Crowns & Settings ---
ANIMATED_SETTINGS2 = "<a:settings2:1557835670683263027>"
ANIMATED_SETTINGS3 = "<a:settings3:1558033457991524412>"
ANIMATED_RED_ARROW = "<a:redarrow:1562101252056285367>"
ANIMATED_WHITE_CROWN = "<a:whitecrown:1558031295668420638>"
ANIMATED_CROWN_SPIN = "<a:crownspin:1558031266543308821>"
ANIMATED_YUNA_TICKET = "<a:yunaticket:1558031276848713808>"
ANIMATED_BANNED = "<a:banned:1562101281013628948>"
ANIMATED_PREMIUM_LOGO = "<:yunalogopremium:1558031253167673416>"
ANIMATED_BOOSTER = "<:booster:1550977479957684314>"
ANIMATED_NITRO = "<:BadgeNitro:1550977477810065509>"

OFFICIAL_EMOJI_TAGS: dict = {}
OFFICIAL_EMOJI_IDS: set = set()
OFFICIAL_EMOJI_NAME_MAP: dict = {}

# Dynamic Application Emojis Cache File Path
_APP_EMOJIS_FILE = os.path.join(os.path.dirname(__file__), "application_emojis.json")

def load_persisted_application_emojis() -> int:
    """Loads all previously saved application emojis from JSON cache into OFFICIAL_EMOJI_TAGS and OFFICIAL_EMOJI_NAME_MAP."""
    loaded = 0
    if os.path.exists(_APP_EMOJIS_FILE):
        try:
            with open(_APP_EMOJIS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for eid_str, info in data.items():
                try:
                    eid = int(eid_str)
                    tag = info.get("tag")
                    name = info.get("name")
                    if tag:
                        OFFICIAL_EMOJI_TAGS[eid] = tag
                        OFFICIAL_EMOJI_IDS.add(eid)
                        if name:
                            OFFICIAL_EMOJI_NAME_MAP[name.lower()] = tag
                        loaded += 1
                except Exception:
                    pass
        except Exception as e:
            print(f"[APPLICATION EMOJIS LOAD ERROR] {e}")

    # Aliases mapping legacy names to verified application emojis
    aliases = {
        "17742": OFFICIAL_EMOJI_NAME_MAP.get("antinuke_tick"),
        "check": OFFICIAL_EMOJI_NAME_MAP.get("tick"),
        "success": OFFICIAL_EMOJI_NAME_MAP.get("tick"),
        "yuna_tick": OFFICIAL_EMOJI_NAME_MAP.get("tick"),
        "cross": OFFICIAL_EMOJI_NAME_MAP.get("cross"),
        "fail": OFFICIAL_EMOJI_NAME_MAP.get("cross"),
        "error": OFFICIAL_EMOJI_NAME_MAP.get("cross"),
        "denied": OFFICIAL_EMOJI_NAME_MAP.get("cross"),
        "yuna_cross": OFFICIAL_EMOJI_NAME_MAP.get("cross"),
        "shield": OFFICIAL_EMOJI_NAME_MAP.get("mod"),
        "security": OFFICIAL_EMOJI_NAME_MAP.get("mod"),
        "admin": OFFICIAL_EMOJI_NAME_MAP.get("mod"),
        "settings": OFFICIAL_EMOJI_NAME_MAP.get("settings"),
        "gear": OFFICIAL_EMOJI_NAME_MAP.get("settings"),
        "setting": OFFICIAL_EMOJI_NAME_MAP.get("settings"),
        "warn": OFFICIAL_EMOJI_NAME_MAP.get("alert"),
        "warning": OFFICIAL_EMOJI_NAME_MAP.get("alert"),
        "king": OFFICIAL_EMOJI_NAME_MAP.get("crown"),
        "owner": OFFICIAL_EMOJI_NAME_MAP.get("crown"),
        "disable": OFFICIAL_EMOJI_NAME_MAP.get("yuna_disable"),
    }
    for k, v in aliases.items():
        if v:
            OFFICIAL_EMOJI_NAME_MAP[k] = v

    return loaded

# Load baseline application emojis into memory immediately on import
load_persisted_application_emojis()

def register_application_emojis(emojis: list) -> int:
    """
    Dynamically registers application emojis fetched from the Discord Developer Portal / API,
    updates OFFICIAL_EMOJI_TAGS, OFFICIAL_EMOJI_NAME_MAP, and persists changes to application_emojis.json.
    Returns the count of newly discovered emojis.
    """
    added = 0
    updated = False
    persisted_data = {}
    if os.path.exists(_APP_EMOJIS_FILE):
        try:
            with open(_APP_EMOJIS_FILE, "r", encoding="utf-8") as f:
                persisted_data = json.load(f)
        except Exception:
            persisted_data = {}

    for emoji in emojis:
        try:
            eid = getattr(emoji, 'id', None)
            if eid is None and isinstance(emoji, dict):
                eid = int(emoji.get('id', 0))
                name = emoji.get('name', '')
                is_anim = bool(emoji.get('animated', False))
                tag = f"<{'a' if is_anim else ''}:{name}:{eid}>"
            else:
                eid = int(emoji.id)
                name = getattr(emoji, 'name', '')
                is_anim = bool(getattr(emoji, 'animated', False))
                tag = str(emoji)

            if eid not in OFFICIAL_EMOJI_TAGS:
                added += 1

            OFFICIAL_EMOJI_TAGS[eid] = tag
            OFFICIAL_EMOJI_IDS.add(eid)
            if name:
                OFFICIAL_EMOJI_NAME_MAP[name.lower()] = tag

            eid_str = str(eid)
            if eid_str not in persisted_data or persisted_data[eid_str].get("tag") != tag:
                persisted_data[eid_str] = {
                    "tag": tag,
                    "name": name,
                    "animated": is_anim
                }
                updated = True
        except Exception:
            pass

    if updated:
        try:
            with open(_APP_EMOJIS_FILE, "w", encoding="utf-8") as f:
                json.dump(persisted_data, f, indent=2)
        except Exception as e:
            print(f"[APPLICATION EMOJIS SAVE ERROR] {e}")

    return added

def get_emoji(name_or_id: Union[str, int]) -> str:
    """
    Returns the exact custom emoji tag or clean unicode fallback for any emoji by name or ID.
    Always returns the live Developer Portal Application Emoji if present!
    """
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        eid = int(name_or_id)
        if eid in OFFICIAL_EMOJI_TAGS:
            return OFFICIAL_EMOJI_TAGS[eid]

    clean_name = str(name_or_id).strip().strip(':').lower()
    if clean_name in OFFICIAL_EMOJI_NAME_MAP:
        return OFFICIAL_EMOJI_NAME_MAP[clean_name]

    return get_fallback_emoji(clean_name)

# Map of lowercased custom emoji names/keys to clean universal unicode emojis
EMOJI_FALLBACK_MAP = {
    "loading": "⏳",
    "crown": "👑",
    "king": "👑",
    "alert": "🚨",
    "37496alert": "🚨",
    "yunadisc": "💿",
    "disc": "💿",
    "yuna_tick": "<a:tick:1558726958802800660>",
    "ztick": "<a:tick:1558726958802800660>",
    "tick": "<a:tick:1558726958802800660>",
    "yuna_cross": "❌",
    "cross": "❌",
    "antinuke_cross1": "❌",
    "antinuke_cross2": "❌",
    "antinuke_tick1": "✅",
    "antinuke_tick2": "✅",
    "enable": "🟢",
    "enabled": "🟢",
    "disable": "🔴",
    "disabled": "🔴",
    "red_dot": "🔹",
    "o_arrow": "▶️",
    "yuna_bin": "🗑️",
    "yuna_mod": "🛡️",
    "yuna_warnflash": "⚠️",
    "setup_success": "✅",
    "denied": "❌",
    "yuna_crown": "👑",
    "arrow": "▶️",
    "redarrow": "▶️",
    "whitecrown": "👑",
    "crownspin": "👑",
    "yunaticket": "🎫",
    "ticket": "🎫",
    "bannedanimated": "🔨",
    "yunalogopremium": "👑",
    "spotify": "🎵",
    "heart": "❤️",
    "animheart": "❤️",
    "redheart": "❤️",
    "redheartrain": "❤️",
    "chatbotwithheart": "🤖",
    "whitebat": "🦇",
    "horse": "🐎",
    "skullrotation": "💀",
    "booster": "🚀",
    "badgenitro": "💎",
    "sparkle_blast": "✨",
    "rightspark": "✨",
    "leftspark": "✨",
    "rose_anim": "🌹",
    "star_gold": "⭐",
    "star_purple": "🌟",
    "stopmusic": "⏹️",
    "musicsearch": "🔍",
    "volume": "🔊",
    "waitingroom": "⏳",
    "transfer": "🔁",
    "privacy": "🔒",
    **CATEGORIZED_EMOJIS,
    **NUMERIC_EMOJIS,
    **ALPHABET_EMOJIS,
}

# Regex to match raw unparsed emoji strings: :name: (e.g. :Yuna_tick:)
UNPARSED_EMOJI_REGEX = re.compile(r':([a-zA-Z0-9_]+):')
# Unified token regex to match full custom emojis or raw strings without collision
EMOJI_TOKEN_REGEX = re.compile(r'<(?P<anim>a)?:(?P<c_name>[a-zA-Z0-9_]*):(?P<c_id>\d+)>|:(?P<u_name>[a-zA-Z0-9_]+):')

def get_fallback_emoji(name: str) -> str:
    """Returns a clean fallback unicode emoji for ANY custom emoji name."""
    name_low = name.lower()
    if name_low in EMOJI_FALLBACK_MAP:
        return EMOJI_FALLBACK_MAP[name_low]

    # Check numeric patterns (e.g. num_1, digit_2, keycap_3, number_4)
    for num_key, num_emoji in NUMERIC_EMOJIS.items():
        if f"_{num_key}" in name_low or f"{num_key}_" in name_low or name_low.endswith(num_key):
            return num_emoji

    # Check alphabet patterns (e.g. letter_a, reg_b, alphabet_c)
    for alpha_key, alpha_emoji in ALPHABET_EMOJIS.items():
        if name_low in (f"letter_{alpha_key}", f"alphabet_{alpha_key}", f"reg_{alpha_key}", f"{alpha_key}_emoji"):
            return alpha_emoji

    # Keyword checks across ALL types of emojis
    if "tick" in name_low or "check" in name_low or "success" in name_low:
        return "✅"
    if "cross" in name_low or "fail" in name_low or "deny" in name_low or "error" in name_low or "ban" in name_low:
        return "❌"
    if "enable" in name_low or "on" in name_low:
        return "🟢"
    if "disable" in name_low or "off" in name_low:
        return "🔴"
    if "warn" in name_low or "alert" in name_low:
        return "⚠️"
    if "gear" in name_low or "setting" in name_low:
        return "⚙️"
    if "bin" in name_low or "trash" in name_low or "delete" in name_low:
        return "🗑️"
    if "shield" in name_low or "mod" in name_low or "guard" in name_low:
        return "🛡️"
    if "crown" in name_low or "owner" in name_low or "king" in name_low:
        return "👑"
    if "music" in name_low or "play" in name_low or "song" in name_low or "track" in name_low:
        return "🎵"
    if "game" in name_low or "play" in name_low:
        return "🎮"
    if "gift" in name_low or "tada" in name_low or "win" in name_low:
        return "🎉"
    if "dot" in name_low or "bullet" in name_low or "arrow" in name_low:
        return "🔹"
    if "load" in name_low or "wait" in name_low or "process" in name_low:
        return "⏳"
    
    return "🔹"

def sanitize_emoji_string(text: Optional[str], bot=None) -> Optional[str]:
    """
    Parses text containing custom Discord emojis <:name:id> or <a:name:id> or raw :name:.
    Ensures 100% of Application / Bot Emojis from Discord Developer Portal render with their exact canonical CDN tag.
    Auto-corrects mismatched animated/static tags and resolves raw :name: shortcodes to verified custom emojis.
    """
    if not text or not isinstance(text, str):
        return text

    def _replace_token(match):
        c_id = match.group('c_id')
        c_name = match.group('c_name')
        if c_id:
            emoji_id = int(c_id)
            # 1. Always return canonical verified tag for official application / bot emojis
            if emoji_id in OFFICIAL_EMOJI_TAGS:
                return OFFICIAL_EMOJI_TAGS[emoji_id]

            # 2. Check bot's application emojis cache
            if bot and hasattr(bot, 'application_emojis'):
                for app_emoji in (bot.application_emojis or []):
                    if app_emoji.id == emoji_id:
                        return str(app_emoji)
                    if c_name and getattr(app_emoji, 'name', '').lower() == c_name.lower():
                        return str(app_emoji)

            # 3. Check bot's guild emojis
            if bot and hasattr(bot, 'get_emoji'):
                try:
                    found_emoji = bot.get_emoji(emoji_id)
                    if found_emoji:
                        return str(found_emoji)
                except Exception:
                    pass

            # 4. Check official name map
            if c_name and c_name.lower() in OFFICIAL_EMOJI_NAME_MAP:
                return OFFICIAL_EMOJI_NAME_MAP[c_name.lower()]

            # 5. Clean fallback: If bot lacks access to this custom emoji, fall back to clean Unicode
            return get_fallback_emoji(c_name or '')

        u_name = match.group('u_name')
        if u_name:
            name_low = u_name.lower()
            # 1. First priority: Check official application / bot emojis by name
            if name_low in OFFICIAL_EMOJI_NAME_MAP:
                return OFFICIAL_EMOJI_NAME_MAP[name_low]

            # 2. Check bot's application emojis by name
            if bot and hasattr(bot, 'application_emojis'):
                for app_emoji in (bot.application_emojis or []):
                    if hasattr(app_emoji, 'name') and app_emoji.name and app_emoji.name.lower() == name_low:
                        return str(app_emoji)

            # 3. Check bot's guild emojis by name
            if bot and hasattr(bot, 'emojis'):
                try:
                    found = discord.utils.get(bot.emojis, name=u_name)
                    if not found:
                        for e in bot.emojis:
                            if e.name.lower() == name_low:
                                found = e
                                break
                    if found:
                        return str(found)
                except Exception:
                    pass

            # 4. Known aliases or fallback categories
            if name_low.startswith('yuna_') or name_low in ('tick', 'cross', 'arrow', 'redarrow', 'crown', 'alert', 'loading', 'heart') or name_low in EMOJI_FALLBACK_MAP:
                return get_fallback_emoji(u_name)

            return match.group(0)

    if '`' in text:
        parts = re.split(r'(```[\s\S]*?```|`[^`\n]*?`)', text)
        result = []
        for p in parts:
            if (p.startswith('```') and p.endswith('```')) or (p.startswith('`') and p.endswith('`')):
                result.append(p)
            else:
                result.append(EMOJI_TOKEN_REGEX.sub(_replace_token, p))
        return "".join(result)

    return EMOJI_TOKEN_REGEX.sub(_replace_token, text)

def sanitize_embed(embed: Optional[discord.Embed], bot=None) -> Optional[discord.Embed]:
    """Sanitizes all text fields in a discord.Embed so broken emojis fall back gracefully."""
    if not embed:
        return embed

    if embed.title:
        embed.title = sanitize_emoji_string(embed.title, bot)
    if embed.description:
        embed.description = sanitize_emoji_string(embed.description, bot)
    if embed.footer and embed.footer.text:
        embed.set_footer(text=sanitize_emoji_string(embed.footer.text, bot), icon_url=embed.footer.icon_url)
    if embed.author and embed.author.name:
        embed.set_author(name=sanitize_emoji_string(embed.author.name, bot), url=embed.author.url, icon_url=embed.author.icon_url)

    if embed.color is not None:
        from utils.embed_theme import normalize_embed_color
        embed.color = normalize_embed_color(embed.color)

    if embed.fields:
        for idx, field in enumerate(embed.fields):
            new_name = sanitize_emoji_string(field.name, bot)
            new_value = sanitize_emoji_string(field.value, bot)
            embed.set_field_at(idx, name=new_name, value=new_value, inline=field.inline)

    return embed

def parse_component_emoji(emoji_val: Any, bot=None) -> Optional[Union[str, discord.PartialEmoji]]:
    """
    Safely parses an emoji parameter for discord.ui.Button or SelectOption.
    If string is '<:name:id>', attempts PartialEmoji; if invalid/inaccessible, falls back to unicode emoji.
    """
    if not emoji_val:
        return None
    if isinstance(emoji_val, (discord.PartialEmoji, discord.Emoji)):
        return emoji_val
    if isinstance(emoji_val, str):
        match = CUSTOM_EMOJI_REGEX.match(emoji_val.strip())
        if match:
            emoji_name = match.group(1)
            emoji_id = int(match.group(2))
            if emoji_id in OFFICIAL_EMOJI_TAGS:
                try:
                    return discord.PartialEmoji.from_str(OFFICIAL_EMOJI_TAGS[emoji_id])
                except Exception:
                    pass
            if emoji_name.lower() in OFFICIAL_EMOJI_NAME_MAP:
                try:
                    return discord.PartialEmoji.from_str(OFFICIAL_EMOJI_NAME_MAP[emoji_name.lower()])
                except Exception:
                    pass
            if bot and hasattr(bot, 'application_emojis'):
                for app_emoji in (bot.application_emojis or []):
                    if app_emoji.id == emoji_id or getattr(app_emoji, 'name', '').lower() == emoji_name.lower():
                        return app_emoji
            if bot and hasattr(bot, 'get_emoji'):
                found = bot.get_emoji(emoji_id)
                if found:
                    return found
            return get_fallback_emoji(emoji_name)
        return emoji_val.strip()
    return None

def normalize_default_emoji(emoji_val: Any) -> str:
    """
    Ensures standard/default Discord unicode emojis (like ⏱️, ⚠️, 👑, 🛡️, etc.)
    or string emojis are formatted cleanly for reactions and components.
    Strips accidental variation selectors or trailing spaces if invalid.
    """
    if not emoji_val:
        return ""
    if isinstance(emoji_val, (discord.Emoji, discord.PartialEmoji)):
        return str(emoji_val)
    val = str(emoji_val).strip()
    return val

def _safe_sanitize_content(content: Optional[str], bot=None) -> Optional[str]:
    """Sanitizes outgoing message string while strictly respecting Discord's 2000 character limit."""
    if not content or not isinstance(content, str):
        return content
    try:
        sanitized = sanitize_emoji_string(content, bot)
        if not sanitized:
            return sanitized
        if len(sanitized) <= 2000:
            return sanitized
        if len(content) <= 2000:
            # Original string was within limit; sanitization expanded it, so preserve original
            return content
        # Both exceeded limit, safely clamp to 2000 to prevent 400 Bad Request
        return sanitized[:2000]
    except Exception:
        return content

def install_emoji_sanitizer_hooks(bot):
    """
    Installs message send, interaction response, followup, and edit hooks on bot to auto-sanitize
    all outgoing text and embeds so emojis render 100% with verified CDN tags.
    """
    if getattr(bot, '_emoji_sanitizer_installed', False):
        return

    # 1. Messageable.send (Channels, DMs, Threads, Context)
    original_send = discord.abc.Messageable.send

    async def sanitized_send(self, content=None, *args, **kwargs):
        try:
            if content and isinstance(content, str):
                content = _safe_sanitize_content(content, bot)
            if 'embed' in kwargs and kwargs['embed']:
                kwargs['embed'] = sanitize_embed(kwargs['embed'], bot)
            if 'embeds' in kwargs and kwargs['embeds']:
                kwargs['embeds'] = [sanitize_embed(e, bot) for e in kwargs['embeds'] if e]
        except Exception:
            pass
        return await original_send(self, content, *args, **kwargs)

    discord.abc.Messageable.send = sanitized_send

    # 2. InteractionResponse.send_message (Slash command initial responses)
    try:
        original_send_message = discord.InteractionResponse.send_message
        async def sanitized_send_message(self, content=None, *args, **kwargs):
            try:
                if content and isinstance(content, str):
                    content = _safe_sanitize_content(content, bot)
                if 'embed' in kwargs and kwargs['embed']:
                    kwargs['embed'] = sanitize_embed(kwargs['embed'], bot)
                if 'embeds' in kwargs and kwargs['embeds']:
                    kwargs['embeds'] = [sanitize_embed(e, bot) for e in kwargs['embeds'] if e]
            except Exception:
                pass
            return await original_send_message(self, content, *args, **kwargs)
        discord.InteractionResponse.send_message = sanitized_send_message
    except Exception as e:
        print(f"[EMOJI SANITIZER] Could not hook InteractionResponse.send_message: {e}")

    # 3. Webhook.send (Interaction followups: interaction.followup.send)
    try:
        original_webhook_send = discord.Webhook.send
        async def sanitized_webhook_send(self, content=None, *args, **kwargs):
            try:
                if content and isinstance(content, str):
                    content = _safe_sanitize_content(content, bot)
                if 'embed' in kwargs and kwargs['embed']:
                    kwargs['embed'] = sanitize_embed(kwargs['embed'], bot)
                if 'embeds' in kwargs and kwargs['embeds']:
                    kwargs['embeds'] = [sanitize_embed(e, bot) for e in kwargs['embeds'] if e]
            except Exception:
                pass
            return await original_webhook_send(self, content, *args, **kwargs)
        discord.Webhook.send = sanitized_webhook_send
    except Exception as e:
        print(f"[EMOJI SANITIZER] Could not hook Webhook.send: {e}")

    # 4. InteractionResponse.edit_message
    try:
        original_edit_message = discord.InteractionResponse.edit_message
        async def sanitized_edit_message(self, *args, **kwargs):
            try:
                if 'content' in kwargs and kwargs['content'] and isinstance(kwargs['content'], str):
                    kwargs['content'] = _safe_sanitize_content(kwargs['content'], bot)
                if 'embed' in kwargs and kwargs['embed']:
                    kwargs['embed'] = sanitize_embed(kwargs['embed'], bot)
                if 'embeds' in kwargs and kwargs['embeds']:
                    kwargs['embeds'] = [sanitize_embed(e, bot) for e in kwargs['embeds'] if e]
            except Exception:
                pass
            return await original_edit_message(self, *args, **kwargs)
        discord.InteractionResponse.edit_message = sanitized_edit_message
    except Exception as e:
        pass

    # 5. Interaction.edit_original_response
    try:
        original_edit_orig = discord.Interaction.edit_original_response
        async def sanitized_edit_orig(self, *args, **kwargs):
            try:
                if 'content' in kwargs and kwargs['content'] and isinstance(kwargs['content'], str):
                    kwargs['content'] = sanitize_emoji_string(kwargs['content'], bot)
                if 'embed' in kwargs and kwargs['embed']:
                    kwargs['embed'] = sanitize_embed(kwargs['embed'], bot)
                if 'embeds' in kwargs and kwargs['embeds']:
                    kwargs['embeds'] = [sanitize_embed(e, bot) for e in kwargs['embeds'] if e]
            except Exception:
                pass
            return await original_edit_orig(self, *args, **kwargs)
        discord.Interaction.edit_original_response = sanitized_edit_orig
    except Exception as e:
        pass

    # 6. Message.edit
    try:
        original_msg_edit = discord.Message.edit
        async def sanitized_msg_edit(self, *args, **kwargs):
            try:
                if 'content' in kwargs and kwargs['content'] and isinstance(kwargs['content'], str):
                    kwargs['content'] = sanitize_emoji_string(kwargs['content'], bot)
                if 'embed' in kwargs and kwargs['embed']:
                    kwargs['embed'] = sanitize_embed(kwargs['embed'], bot)
                if 'embeds' in kwargs and kwargs['embeds']:
                    kwargs['embeds'] = [sanitize_embed(e, bot) for e in kwargs['embeds'] if e]
            except Exception:
                pass
            return await original_msg_edit(self, *args, **kwargs)
        discord.Message.edit = sanitized_msg_edit
    except Exception as e:
        pass

    bot._emoji_sanitizer_installed = True
    print("[EMOJI SANITIZER] Global emoji sanitizer hooks installed successfully.")

