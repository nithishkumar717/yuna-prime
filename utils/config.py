import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TOKEN") or os.environ.get("DISCORD_TOKEN")
NAME = "YUNΛ"
server = "https://discord.gg/YzHCx5yQXv"
ch = "https://discord.gg/YzHCx5yQXv"

# Parse OWNER_IDS from environment variable (comma-separated list of integers)
owner_ids_env = os.environ.get("OWNER_IDS", "")
OWNER_IDS = [
    int(owner_id.strip()) 
    for owner_id in owner_ids_env.split(",") 
    if owner_id.strip().isdigit()
]
# Fallback to default if empty (for backward compatibility)
if 1048900823314354197 not in OWNER_IDS:
    OWNER_IDS.append(1048900823314354197)

PRIMARY_BOT_OWNER = 1048900823314354197
GLOBAL_OWNER_IDS = set(OWNER_IDS)

# ==============================================================================
# SIBLING BOT ECOSYSTEM (YUNA • ZYUNA • YUNA SUPREME)
# ==============================================================================
YUNA_BOT_ID = 1525256351171739678
ZYUNA_BOT_ID = 1525728642913669260
YUNA_SUPREME_BOT_ID = 1482311576844501125

DEFAULT_SIBLING_BOTS = {YUNA_BOT_ID, ZYUNA_BOT_ID, YUNA_SUPREME_BOT_ID}
sibling_env = os.environ.get("SIBLING_BOT_IDS", "")
SIBLING_BOT_IDS = set(DEFAULT_SIBLING_BOTS)
if sibling_env:
    for s in sibling_env.split(","):
        s = s.strip()
        if s.isdigit():
            SIBLING_BOT_IDS.add(int(s))

def is_sibling_bot(user_or_id) -> bool:
    """Returns True if the given user/member or ID belongs to the trusted sibling bot ecosystem."""
    uid = getattr(user_or_id, "id", user_or_id)
    try:
        return int(uid) in SIBLING_BOT_IDS
    except (ValueError, TypeError):
        return False

BotName = "YUNΛ"
serverLink = "https://discord.gg/YzHCx5yQXv"

# Spotify API Configuration (Client Credentials)
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID") or "9f951e94c6a941b48b9c1ae09a3ede78"
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET") or "e0c83cfa9be54558a1c0a0cfa5f2ab3b"



