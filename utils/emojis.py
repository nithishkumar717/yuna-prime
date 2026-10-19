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

ANIMATED_TICK = "<a:tick:1558726958802800660>"
ANTINUKE_TICK = "<:17742:1560628833105743972>"
ANIMATED_CROSS = "<:yuna_cross:1227866668152393789>"
STATIC_TICK = "<a:tick:1558726958802800660>"
ANIMATED_SETTINGS = "<a:SETTINGS:1548704222562746478>"
STATIC_MOD = "<:MOD:1548704219517821089>"
ANIMATED_ENABLED = "<a:enable:1548704224974737569>"
STATIC_DISABLED = "<:disable:1548686459865792583>"
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
STATIC_LOCK = "<:lock:1557211239724224692>"
STATIC_UNLOCK = "<:unlock:1557212304297431090>"
STATIC_HIDEVC = "<:hidevc:1557214632920227872>"
STATIC_KICKVC = "<:kickvc:1557215509559124039>"
ANIMATED_LOADING = "<a:loading:1554957482248380416>"
ANIMATED_KING = "<a:crown:1557835666757521438>"
ANIMATED_CROWN = "<a:crown:1557835666757521438>"
ANIMATED_ALERT = "<a:37496alert:1550972111215009914>"
ANIMATED_DISC = "<a:yunadisc:1557984542084829284>"
ANIMATED_YUNADISC = "<a:yunadisc:1557984542084829284>"
ANIMATED_ARROW = "<a:arrow:1557834336571494480>"
STATIC_ARROW = "<a:arrow:1557834336571494480>"

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
ANIMATED_RED_ARROW = "<a:redarrow:1558031429886156800>"
ANIMATED_WHITE_CROWN = "<a:whitecrown:1558031295668420638>"
ANIMATED_CROWN_SPIN = "<a:crownspin:1558031266543308821>"
ANIMATED_YUNA_TICKET = "<a:yunaticket:1558031276848713808>"
ANIMATED_BANNED = "<a:bannedanimated:1558031257063923722>"
ANIMATED_PREMIUM_LOGO = "<:yunalogopremium:1558031253167673416>"
ANIMATED_BOOSTER = "<:booster:1550977479957684314>"
ANIMATED_NITRO = "<:BadgeNitro:1550977477810065509>"

OFFICIAL_EMOJI_TAGS = {
    1558726958802800660: "<a:tick:1558726958802800660>",  # tick (animated)
    1558033457991524412: "<a:settings3:1558033457991524412>",  # settings3 (animated)
    1558033454514446337: "<a:chatbotwithheart:1558033454514446337>",  # chatbotwithheart (animated)
    1558031459200143421: "<a:angelbutterfly6:1558031459200143421>",  # angelbutterfly6 (animated)
    1558031454758375474: "<a:music1:1558031454758375474>",  # music1 (animated)
    1558031429886156800: "<a:redarrow:1558031429886156800>",  # redarrow (animated)
    1558031417789653082: "<a:angelbutterfly5:1558031417789653082>",  # angelbutterfly5 (animated)
    1558031413834682368: "<a:whitebat:1558031413834682368>",  # whitebat (animated)
    1558031410772574230: "<:cutie:1558031410772574230>",  # cutie (static)
    1558031407865929840: "<a:tdmusic:1558031407865929840>",  # tdmusic (animated)
    1558031400299532349: "<a:redheartrain:1558031400299532349>",  # redheartrain (animated)
    1558031392569565264: "<a:ak:1558031392569565264>",  # ak (animated)
    1558031389629222964: "<a:escape:1558031389629222964>",  # escape (animated)
    1558031386475237406: "<a:rightspark:1558031386475237406>",  # rightspark (animated)
    1558031383497023508: "<a:leftspark:1558031383497023508>",  # leftspark (animated)
    1558031379672076309: "<:cross:1558031379672076309>",  # cross (static)
    1558031377255899247: "<a:angelbutterfly4:1558031377255899247>",  # angelbutterfly4 (animated)
    1558031352996167711: "<a:angelbutterfly3:1558031352996167711>",  # angelbutterfly3 (animated)
    1558031348491354212: "<a:angelbutterfly2:1558031348491354212>",  # angelbutterfly2 (animated)
    1558031333714960444: "<a:animheart:1558031333714960444>",  # animheart (animated)
    1558031330791395409: "<a:fire:1558031330791395409>",  # fire (animated)
    1558031327536746566: "<a:hookup:1558031327536746566>",  # hookup (animated)
    1558031323312955503: "<a:skullrotation:1558031323312955503>",  # skullrotation (animated)
    1558031319609511956: "<a:count7:1558031319609511956>",  # count7 (animated)
    1558031315029459055: "<a:count6:1558031315029459055>",  # count6 (animated)
    1558031307441840168: "<a:angelbutterfly:1558031307441840168>",  # angelbutterfly (animated)
    1558031295668420638: "<a:whitecrown:1558031295668420638>",  # whitecrown (animated)
    1558031288995291236: "<a:horse:1558031288995291236>",  # horse (animated)
    1558031280074002483: "<a:symb:1558031280074002483>",  # symb (animated)
    1558031276848713808: "<a:yunaticket:1558031276848713808>",  # yunaticket (animated)
    1558031266543308821: "<a:crownspin:1558031266543308821>",  # crownspin (animated)
    1558031260591587358: "<a:minitwobutterflies:1558031260591587358>",  # minitwobutterflies (animated)
    1558031257063923722: "<a:bannedanimated:1558031257063923722>",  # bannedanimated (animated)
    1558031253167673416: "<:yunalogopremium:1558031253167673416>",  # yunalogopremium (static)
    1557984542084829284: "<a:yunadisc:1557984542084829284>",  # yunadisc (animated)
    1557835670683263027: "<a:settings2:1557835670683263027>",  # settings2 (animated)
    1557835666757521438: "<a:crown:1557835666757521438>",  # crown (animated)
    1557834336571494480: "<a:arrow:1557834336571494480>",  # arrow (animated)
    1557215509559124039: "<:kickvc:1557215509559124039>",  # kickvc (static)
    1557214632920227872: "<:hidevc:1557214632920227872>",  # hidevc (static)
    1557212304297431090: "<:unlock:1557212304297431090>",  # unlock (static)
    1557211239724224692: "<:lock:1557211239724224692>",  # lock (static)
    1557210238162182175: "<:unmuteall:1557210238162182175>",  # unmuteall (static)
    1557208136509820948: "<:undeafen:1557208136509820948>",  # undeafen (static)
    1557206833012277288: "<:deafen:1557206833012277288>",  # deafen (static)
    1557204695284711516: "<:mute:1557204695284711516>",  # mute (static)
    1554957482248380416: "<a:loading:1554957482248380416>",  # loading (animated)
    1554932785284776076: "<:muteall:1554932785284776076>",  # muteall (static)
    1554930999085895680: "<:playlist:1554930999085895680>",  # playlist (static)
    1554930825014022144: "<:247mode:1554930825014022144>",  # 247mode (static)
    1554930526228455575: "<:addsong:1554930526228455575>",  # addsong (static)
    1554930299706802247: "<:songqueue:1554930299706802247>",  # songqueue (static)
    1554929878774718495: "<:songfilter:1554929878774718495>",  # songfilter (static)
    1554929086579609780: "<:songmood:1554929086579609780>",  # songmood (static)
    1554927027545440306: "<:songresume:1554927027545440306>",  # songresume (static)
    1554925676321050624: "<:lang:1554925676321050624>",  # lang (static)
    1554924675035959347: "<:history:1554924675035959347>",  # history (static)
    1554923334913884250: "<:stopmusic:1554923334913884250>",  # stopmusic (static)
    1554920989589110884: "<:musicsearch:1554920989589110884>",  # musicsearch (static)
    1554918644935294986: "<:10secplus:1554918644935294986>",  # 10secplus (static)
    1554917901969006665: "<:10sec:1554917901969006665>",  # 10sec (static)
    1554917090366849024: "<:shuffle:1554917090366849024>",  # shuffle (static)
    1554911786480697405: "<:volume:1554911786480697405>",  # volume (static)
    1551982339393851493: "<:musiccontrol:1551982339393851493>",  # musiccontrol (static)
    1550977538237407442: "<:yuna_cross:1550977538237407442>",  # yuna_cross (static)
    1550977535678873773: "<:VerifiedBotDev:1550977535678873773>",  # VerifiedBotDev (static)
    1550977533284061275: "<:VERIFIED_BOT:1550977533284061275>",  # VERIFIED_BOT (static)
    1550977531086372895: "<a:success_check:1550977531086372895>",  # success_check (animated)
    1550977528158752788: "<a:star_purple:1550977528158752788>",  # star_purple (animated)
    1550977525230866622: "<a:star_gold:1550977525230866622>",  # star_gold (animated)
    1550977511826128966: "<a:sparkle_blast:1550977511826128966>",  # sparkle_blast (animated)
    1550977499176116295: "<a:sg_red_dot:1550977499176116295>",  # sg_red_dot (animated)
    1550977496466460762: "<a:rose_anim:1550977496466460762>",  # rose_anim (animated)
    1550977489424228363: "<a:premium:1550977489424228363>",  # premium (animated)
    1550977487222345901: "<a:owner_crown:1550977487222345901>",  # owner_crown (animated)
    1550977484382797885: "<:Denied:1550977484382797885>",  # Denied (static)
    1550977482092707870: "<:claim_reward:1550977482092707870>",  # claim_reward (static)
    1550977479957684314: "<:booster:1550977479957684314>",  # booster (static)
    1550977477810065509: "<:BadgeNitro:1550977477810065509>",  # BadgeNitro (static)
    1550972187047890954: "<:YunaTime:1550972187047890954>",  # YunaTime (static)
    1550972184325918751: "<:YunaMedia:1550972184325918751>",  # YunaMedia (static)
    1550972182220374026: "<:YunaArrow:1550972182220374026>",  # YunaArrow (static)
    1550972179770777713: "<:Yuna_users:1550972179770777713>",  # Yuna_users (static)
    1550972176981823488: "<:Yuna_notify:1550972176981823488>",  # Yuna_notify (static)
    1550972174452658196: "<:Yuna_giveaway:1550972174452658196>",  # Yuna_giveaway (static)
    1550972171596333117: "<:Yuna_duration:1550972171596333117>",  # Yuna_duration (static)
    1550972145910288464: "<a:sg_rd:1550972145910288464>",  # sg_rd (animated)
    1550972143502762024: "<a:RedHeart:1550972143502762024>",  # RedHeart (animated)
    1550972136741408859: "<a:max__A:1550972136741408859>",  # max__A (animated)
    1550972131251069080: "<a:king:1550972131251069080>",  # king (animated)
    1550972128004800602: "<a:GIFD:1550972128004800602>",  # GIFD (animated)
    1550972116881645699: "<:Dc_RedCrownEsports:1550972116881645699>",  # Dc_RedCrownEsports (static)
    1550972111215009914: "<a:37496alert:1550972111215009914>",  # 37496alert (animated)
    1548704287708815420: "<:waitingroom:1548704287708815420>",  # waitingroom (static)
    1548704285649408101: "<:untrust:1548704285649408101>",  # untrust (static)
    1548704282390298716: "<:unblock:1548704282390298716>",  # unblock (static)
    1548704280222109726: "<:trust:1548704280222109726>",  # trust (static)
    1548704278284206230: "<:transfer:1548704278284206230>",  # transfer (static)
    1548704272034566184: "<:region:1548704272034566184>",  # region (static)
    1548704268062687282: "<:privacy:1548704268062687282>",  # privacy (static)
    1548704259980263505: "<:name:1548704259980263505>",  # name (static)
    1548704252862537779: "<:limit:1548704252862537779>",  # limit (static)
    1548704249880383488: "<:kick:1548704249880383488>",  # kick (static)
    1548704246499909815: "<:invite:1548704246499909815>",  # invite (static)
    1548704238799028306: "<:delete:1548704238799028306>",  # delete (static)
    1548704236307615745: "<:claim:1548704236307615745>",  # claim (static)
    1548704229986664570: "<:chat:1548704229986664570>",  # chat (static)
    1548704227310706791: "<:block:1548704227310706791>",  # block (static)
    1548704224974737569: "<a:enable:1548704224974737569>",  # enable (animated)
    1548704222562746478: "<a:SETTINGS:1548704222562746478>",  # SETTINGS (animated)
    1548704219517821089: "<:MOD:1548704219517821089>",  # MOD (static)
    1548690043185528932: "<a:error_wrong:1548690043185528932>",  # error_wrong (animated)
    1548689317264625664: "<:music:1548689317264625664>",  # music (static)
    1548688868923023490: "<:stop:1548688868923023490>",  # stop (static)
    1548687259744866314: "<a:heart:1548687259744866314>",  # heart (animated)
    1548686459865792583: "<:disable:1548686459865792583>",  # disable (static)
    1548638534573752381: "<:playpause:1548638534573752381>",  # playpause (static)
    1548595448602693652: "<:next:1548595448602693652>",  # next (static)
    1548595151755026442: "<:previous:1548595151755026442>",  # previous (static)
    1548594863530971196: "<:loop:1548594863530971196>",  # loop (static)
    1548587576359780353: "<a:settings:1548587576359780353>",  # settings (animated)
    1548587574111633431: "<:mod:1548587574111633431>",  # mod (static)
    1548414902820020334: "<a:tick:1558726958802800660>",  # yuna_tick migrated to user preferred tick
    1547874100519899246: "<:spotify:1547874100519899246>",  # spotify (static)
    1227866668152393789: "<:yuna_cross:1227866668152393789>",  # yuna_cross (static)
}

OFFICIAL_EMOJI_IDS = set(OFFICIAL_EMOJI_TAGS.keys())

# Map lowercased emoji names to their canonical tags (Application / Bot emojis)
CUSTOM_EMOJI_REGEX = re.compile(r'<a?:([a-zA-Z0-9_]+):(\d+)>')
OFFICIAL_EMOJI_NAME_MAP: dict = {}
for _eid, _tag in OFFICIAL_EMOJI_TAGS.items():
    _m = CUSTOM_EMOJI_REGEX.match(_tag)
    if _m:
        _name = _m.group(1).lower()
        if _name not in OFFICIAL_EMOJI_NAME_MAP:
            OFFICIAL_EMOJI_NAME_MAP[_name] = _tag

# Add verified aliases and shortcodes for Application Emojis
OFFICIAL_EMOJI_NAME_MAP.update({
    "tick": "<a:tick:1558726958802800660>",
    "check": "<a:tick:1558726958802800660>",
    "success": "<a:tick:1558726958802800660>",
    "yuna_tick": "<a:tick:1558726958802800660>",
    "cross": "<:cross:1558031379672076309>",
    "fail": "<:cross:1558031379672076309>",
    "error": "<a:error_wrong:1548690043185528932>",
    "denied": "<:Denied:1550977484382797885>",
    "crown": "<a:crown:1557835666757521438>",
    "owner": "<a:owner_crown:1550977487222345901>",
    "ticket": "<a:yunaticket:1558031276848713808>",
    "arrow": "<a:arrow:1557834336571494480>",
    "redarrow": "<a:redarrow:1558031429886156800>",
    "settings": "<a:settings:1548587576359780353>",
    "settings3": "<a:settings3:1558033457991524412>",
    "loading": "<a:loading:1554957482248380416>",
    "nitro": "<:BadgeNitro:1550977477810065509>",
    "badgenitro": "<:BadgeNitro:1550977477810065509>",
    "booster": "<:booster:1550977479957684314>",
    "botdev": "<:VerifiedBotDev:1550977535678873773>",
    "verifiedbotdev": "<:VerifiedBotDev:1550977535678873773>",
    "verified_bot": "<:VERIFIED_BOT:1550977533284061275>",
    "verifiedbot": "<:VERIFIED_BOT:1550977533284061275>",
})

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
                    if tag:
                        OFFICIAL_EMOJI_TAGS[eid] = tag
                        OFFICIAL_EMOJI_IDS.add(eid)
                        name = info.get("name")
                        if name:
                            OFFICIAL_EMOJI_NAME_MAP[name.lower()] = tag
                        loaded += 1
                except Exception:
                    pass
        except Exception as e:
            print(f"[APPLICATION EMOJIS LOAD ERROR] {e}")
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

            # 3. Check bot's guild emojis
            if bot and hasattr(bot, 'get_emoji'):
                try:
                    found_emoji = bot.get_emoji(emoji_id)
                    if found_emoji:
                        return str(found_emoji)
                except Exception:
                    pass

            # If not in official app emojis or bot cache, leave original custom emoji tag intact
            return match.group(0)

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
            if bot and hasattr(bot, 'get_emoji'):
                found = bot.get_emoji(emoji_id)
                if found:
                    return found
            try:
                return discord.PartialEmoji.from_str(emoji_val.strip())
            except Exception:
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

