import os
import json

BOT_CONFIG_PATH = "local-bot-config-backup.json"
GUILD_PROFILES_PATH = "local-guild-profiles-backup.json"
SECURITY_CONFIG_PATH = os.path.join("data", "security.json")

DEFAULT_BOT_CONFIG = {
    "serverPassword": "",
    "passwordHint": "",
    "welcomeEnabled": True,
    "welcomeChannel": "welcome",
    "welcomeMessage": "👋 Welcome {user} to the server! You are our {memberCount}th member!",
    "byeEnabled": True,
    "byeChannel": "goodbye",
    "byeMessage": "😢 Goodbye {user}, we will miss you!",
    "badWordsEnabled": True,
    "badWords": ["crap", "stupid", "idiot", "damn", "slop"],
    "whitelistedWords": [],
    "urlProtectionEnabled": True,
    "whitelistedDomains": ["google.com", "discord.gg", "github.com"],
    "botProtection": False,
    "attachmentProtection": False,
    "spamProtection": True,
    "webhookProtection": True,
    "antiNukeEnabled": True,
    "whitelistedUsers": [],
    "everyonePinChannel": "announcements",
    "everyonePinMessage": "📢 Attention @everyone! This is an important pinned notification!",
    "warningsMap": {},
    "mentionDmEnabled": True,
    "mentionDmCooldown": 60,
    "messageLogsEnabled": True,
    "voiceLogsEnabled": True,
    "roleLogsEnabled": True,
    "memberLogsEnabled": True,
    "inviteLogsEnabled": True,
    "webhookLogsEnabled": True,
    "emojiLogsEnabled": True,
    "stickerLogsEnabled": True,
    "tempVcEnabled": True,
    "joinToCreateEnabled": True,
    "voice247Enabled": False,
    "voiceEnabled": True,
    "afkEnabled": True,
    "dragMeEnabled": True,
    "autoRoleEnabled": False,
    "autoRoleName": "Member",
    "nicknameAutomationEnabled": False,
    "nicknamePrefix": "SD",
    "musicEnabled": True,
    "music247Enabled": False,
    "musicAutoplayEnabled": False,
    "ticketsEnabled": True,
    "ticketCategory": "Tickets",
    "aiEnabled": True,
    "aiVisionEnabled": True,
    "aiSystemPrompt": "You are ❀ YUNΛ AI, a helpful, protective Discord moderation bot.",
    "utilitiesEnabled": True,
    "antiBotEnabled": True,
    "antiSpamEnabled": True,
    "antiUrlEnabled": True,
    "antiAttachmentEnabled": False,
    "antiWebhookEnabled": True,
    "everyonePingEnabled": True,
    "roleProtectionEnabled": True,
    "channelProtectionEnabled": True,
    "emojiProtectionEnabled": True,
    "stickerProtectionEnabled": True,
    "punishmentRule": "kick",
    "autoDeleteViolations": True,
    "authLogs": [],
    "pendingResetRequests": [],
}

DEFAULT_SECURITY_CONFIG = {
    "badWordsEnabled": False,
    "badWords": ["crap", "stupid", "idiot", "damn", "slop"],
    "whitelistedWords": [],
    "badWordsWarningLimit": 3,
    "badWordsTimeoutMs": 120000,
    "botProtection": False,
    "allowedBots": 5,
    "botWarningLimit": 3,
    "urlProtectionEnabled": False,
    "whitelistedDomains": ["google.com", "discord.gg", "github.com"],
    "urlAllowedChannels": [],
    "attachmentProtection": False,
    "attachmentAllowedChannels": [],
    "spamProtection": False,
    "spamMessageLimit": 3,
    "spamTimeWindowMs": 5000,
    "spamTimeoutMs": 120000,
    "webhookProtection": False,
    "allowedWebhooks": 2,
    "whitelistedWebhooks": [],
    "antiNukeEnabled": False,
    "whitelistedUsers": [],
    "antiNukeWarningLimit": 3,
    "autoDeleteViolations": True,
}

def get_bot_config():
    if os.path.exists(BOT_CONFIG_PATH):
        try:
            with open(BOT_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Create merged dictionary
                merged = DEFAULT_BOT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            print(f"Error loading bot config: {e}")
    return DEFAULT_BOT_CONFIG.copy()

def save_bot_config(updates):
    config = get_bot_config()
    config.update(updates)
    try:
        with open(BOT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving bot config: {e}")
    return config

def delete_bot_config():
    if os.path.exists(BOT_CONFIG_PATH):
        try:
            os.remove(BOT_CONFIG_PATH)
        except Exception as e:
            print(f"Error deleting bot config: {e}")

def get_guild_profile(guild_id):
    default_profile = {
        "guildId": guild_id,
        "customAvatar": "",
        "customBanner": "",
        "customBio": "I am your customized server security, moderation, and welcomes assistant.",
        "extraOwners": []
    }
    if os.path.exists(GUILD_PROFILES_PATH):
        try:
            with open(GUILD_PROFILES_PATH, "r", encoding="utf-8") as f:
                profiles = json.load(f)
                return profiles.get(guild_id, default_profile)
        except Exception as e:
            print(f"Error loading guild profiles: {e}")
    return default_profile

def save_guild_profile(guild_id, updates):
    profiles = {}
    if os.path.exists(GUILD_PROFILES_PATH):
        try:
            with open(GUILD_PROFILES_PATH, "r", encoding="utf-8") as f:
                profiles = json.load(f)
        except Exception:
            pass
    profile = profiles.get(guild_id, {
        "guildId": guild_id,
        "customAvatar": "",
        "customBanner": "",
        "customBio": "I am your customized server security, moderation, and welcomes assistant.",
        "extraOwners": []
    })
    profile.update(updates)
    profiles[guild_id] = profile
    try:
        with open(GUILD_PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2)
    except Exception as e:
        print(f"Error saving guild profile: {e}")
    return profile

def get_security_config():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(SECURITY_CONFIG_PATH):
        try:
            with open(SECURITY_CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                merged = DEFAULT_SECURITY_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            print(f"Error loading security config: {e}")
    return DEFAULT_SECURITY_CONFIG.copy()

def save_security_config(updates):
    os.makedirs("data", exist_ok=True)
    config = get_security_config()
    config.update(updates)
    try:
        with open(SECURITY_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving security config: {e}")
    return config
