import asyncio
import aiosqlite
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def auto_heal_corrupted_dbs(db_dir: str = "db"):
    """
    Auto-Recovery System: Detects corrupted, malformed, or unreadable SQLite databases.
    Quarantines the broken file and removes stale WAL locks so clean schemas can be rebuilt.
    """
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        return

    import sqlite3
    import time
    for fname in os.listdir(db_dir):
        if not fname.endswith(".db"):
            continue
        fpath = os.path.join(db_dir, fname)
        is_corrupt = False
        err_msg = ""
        try:
            conn = sqlite3.connect(fpath, timeout=3.0)
            c = conn.cursor()
            c.execute("PRAGMA integrity_check;")
            res = c.fetchone()
            if not res or res[0] != "ok":
                is_corrupt = True
                err_msg = f"Integrity check failed: {res}"
            else:
                c.execute("SELECT 1 FROM sqlite_master LIMIT 1;")
                c.fetchone()
            conn.close()
        except Exception as e:
            is_corrupt = True
            err_msg = str(e)

        if is_corrupt:
            ts = int(time.time())
            quarantine = f"{fpath}.corrupt_{ts}"
            print(f"⚠️ [DATABASE AUTO-HEAL] Corrupted/malformed DB detected ({fname}: {err_msg}). Quarantining to {quarantine}...", flush=True)
            for extra in [f"{fpath}-wal", f"{fpath}-shm"]:
                if os.path.exists(extra):
                    try:
                        os.remove(extra)
                    except Exception:
                        pass
            try:
                os.rename(fpath, quarantine)
            except Exception as qe:
                print(f"⚠️ [DATABASE AUTO-HEAL] Could not rename {fname}: {qe}", flush=True)

async def setup_all_dbs():
    # Auto-heal any corrupted databases before running migrations
    auto_heal_corrupted_dbs("db")
    
    # Create db directory if not exists
    os.makedirs("db", exist_ok=True)
    
    # Setup anti.db
    async with aiosqlite.connect('db/anti.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS extraowners (
                guild_id INTEGER PRIMARY KEY,
                owner_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS antinuke (
                guild_id INTEGER PRIMARY KEY,
                status BOOLEAN,
                log_channel INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS whitelisted_users (
                guild_id INTEGER,
                user_id INTEGER,
                ban BOOLEAN DEFAULT FALSE,
                kick BOOLEAN DEFAULT FALSE,
                prune BOOLEAN DEFAULT FALSE,
                botadd BOOLEAN DEFAULT FALSE,
                serverup BOOLEAN DEFAULT FALSE,
                memup BOOLEAN DEFAULT FALSE,
                chcr BOOLEAN DEFAULT FALSE,
                chdl BOOLEAN DEFAULT FALSE,
                chup BOOLEAN DEFAULT FALSE,
                rlcr BOOLEAN DEFAULT FALSE,
                rlup BOOLEAN DEFAULT FALSE,
                rldl BOOLEAN DEFAULT FALSE,
                meneve BOOLEAN DEFAULT FALSE,
                mngweb BOOLEAN DEFAULT FALSE,
                mngstemo BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS whitelisted_roles (
                guild_id INTEGER,
                role_id INTEGER,
                added_by INTEGER,
                ban BOOLEAN DEFAULT FALSE,
                kick BOOLEAN DEFAULT FALSE,
                prune BOOLEAN DEFAULT FALSE,
                botadd BOOLEAN DEFAULT FALSE,
                serverup BOOLEAN DEFAULT FALSE,
                memup BOOLEAN DEFAULT FALSE,
                chcr BOOLEAN DEFAULT FALSE,
                chdl BOOLEAN DEFAULT FALSE,
                chup BOOLEAN DEFAULT FALSE,
                rlcr BOOLEAN DEFAULT FALSE,
                rlup BOOLEAN DEFAULT FALSE,
                rldl BOOLEAN DEFAULT FALSE,
                meneve BOOLEAN DEFAULT FALSE,
                mngweb BOOLEAN DEFAULT FALSE,
                mngstemo BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        try:
            await db.execute('ALTER TABLE whitelisted_roles ADD COLUMN added_by INTEGER;')
        except Exception:
            pass
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Nightmode (
                guildId TEXT,
                roleId TEXT,
                adminPermissions INTEGER,
                original_permissions INTEGER DEFAULT 0,
                PRIMARY KEY (guildId, roleId)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS wlevy1 (
                guild_id INTEGER PRIMARY KEY,
                status BOOLEAN DEFAULT FALSE
            )
        ''')
        await db.commit()
        print("Initialized db/anti.db")

    # Setup prefix.db
    async with aiosqlite.connect('db/prefix.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS prefixes (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT NOT NULL
            )
        ''')
        await db.commit()
        print("Initialized db/prefix.db")

    
    # Setup np.db
    async with aiosqlite.connect('db/np.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS np (
                id INTEGER PRIMARY KEY
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY
            )
        ''')
        await db.commit()
        print("Initialized db/np.db")
    
    # Setup topcheck.db
    async with aiosqlite.connect('db/topcheck.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS topcheck (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            )
        ''')
        await db.commit()
        print("Initialized db/topcheck.db")
    
    # Setup ignore.db
    async with aiosqlite.connect('db/ignore.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ignored_channels (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ignored_users (
                guild_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ignored_commands (
                guild_id INTEGER,
                command_name TEXT,
                PRIMARY KEY (guild_id, command_name)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bypassed_users (
                guild_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.commit()
        print("Initialized db/ignore.db")
    
    # Setup block.db
    async with aiosqlite.connect('db/block.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_blacklist (
                user_id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guild_blacklist (
                guild_id TEXT PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()
        print("Initialized db/block.db")

    # Setup stats.db
    async with aiosqlite.connect('db/stats.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER
            )
        ''')
        await db.commit()
        print("Initialized db/stats.db")

    # Setup anti.db
    async with aiosqlite.connect('db/anti.db', timeout=30.0) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=30000;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute('''
            CREATE TABLE IF NOT EXISTS antinuke (
                guild_id INTEGER PRIMARY KEY,
                status BOOLEAN DEFAULT 0,
                log_channel INTEGER
            )
        ''')
        # Check and migrate columns for antinuke
        async with db.execute("PRAGMA table_info(antinuke)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if 'status' not in columns:
                if 'enabled' in columns:
                    await db.execute("ALTER TABLE antinuke RENAME COLUMN enabled TO status")
                else:
                    await db.execute("ALTER TABLE antinuke ADD COLUMN status BOOLEAN DEFAULT 0")
            if 'log_channel' not in columns:
                await db.execute("ALTER TABLE antinuke ADD COLUMN log_channel INTEGER")

        await db.execute('''
            CREATE TABLE IF NOT EXISTS whitelisted_users (
                guild_id INTEGER,
                user_id INTEGER,
                ban BOOLEAN DEFAULT FALSE,
                kick BOOLEAN DEFAULT FALSE,
                prune BOOLEAN DEFAULT FALSE,
                botadd BOOLEAN DEFAULT FALSE,
                serverup BOOLEAN DEFAULT FALSE,
                memup BOOLEAN DEFAULT FALSE,
                chcr BOOLEAN DEFAULT FALSE,
                chdl BOOLEAN DEFAULT FALSE,
                chup BOOLEAN DEFAULT FALSE,
                rlcr BOOLEAN DEFAULT FALSE,
                rlup BOOLEAN DEFAULT FALSE,
                rldl BOOLEAN DEFAULT FALSE,
                meneve BOOLEAN DEFAULT FALSE,
                mngweb BOOLEAN DEFAULT FALSE,
                mngstemo BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS extraowners (
                guild_id INTEGER PRIMARY KEY,
                owner_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Nightmode (
                guildId TEXT,
                roleId TEXT,
                adminPermissions INTEGER,
                original_permissions INTEGER DEFAULT 0,
                PRIMARY KEY (guildId, roleId)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS nightmode_roles (
                guild_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                role_name TEXT,
                original_permissions INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_stripped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_restored_at TIMESTAMP,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS nightmode_guilds (
                guild_id INTEGER PRIMARY KEY
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS nightmode_config (
                guild_id INTEGER PRIMARY KEY,
                auto_enabled INTEGER DEFAULT 0,
                log_channel INTEGER,
                start_hour INTEGER DEFAULT 0,
                start_minute INTEGER DEFAULT 0,
                start_second INTEGER DEFAULT 0,
                end_hour INTEGER DEFAULT 6,
                end_minute INTEGER DEFAULT 0,
                end_second INTEGER DEFAULT 0,
                start_time TEXT DEFAULT '00:00:00',
                end_time TEXT DEFAULT '06:00:00',
                timezone TEXT DEFAULT 'Asia/Kolkata',
                last_action TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS limit_settings (
                guild_id INTEGER,
                action_type TEXT,
                action_limit INTEGER,
                time_window INTEGER,
                PRIMARY KEY (guild_id, action_type)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS whitelisted_bots (
                guild_id INTEGER,
                bot_id INTEGER,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, bot_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bot_protection (
                guild_id INTEGER PRIMARY KEY,
                status BOOLEAN DEFAULT 1
            )
        ''')
        await db.commit()
        print("Initialized db/anti.db")

    # Setup automod.db
    async with aiosqlite.connect('db/automod.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS automod (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS automod_punishments (
                guild_id INTEGER,
                event TEXT,
                punishment TEXT,
                PRIMARY KEY (guild_id, event)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS automod_ignored (
                guild_id INTEGER,
                id INTEGER,
                type TEXT,
                PRIMARY KEY (guild_id, id, type)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS external_app_lockdown (
                guild_id INTEGER PRIMARY KEY,
                locked_roles TEXT,
                unlock_timestamp REAL,
                channel_id INTEGER
            )
        ''')
        await db.commit()
        print("Initialized db/automod.db")

    # Setup customrole.db
    async with aiosqlite.connect('db/customrole.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS custom_roles (
                guild_id INTEGER,
                user_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.commit()
        print("Initialized db/customrole.db")

    # Setup emergency.db
    async with aiosqlite.connect('db/emergency.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS emergency (
                guild_id INTEGER PRIMARY KEY,
                lockdown INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS authorised_users (
                guild_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS emergency_roles (
                guild_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS restore_roles (
                guild_id INTEGER,
                role_id INTEGER,
                permissions INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS role_positions (
                guild_id INTEGER,
                role_id INTEGER,
                position INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        await db.commit()
        print("Initialized db/emergency.db")

    # Setup blword.db
    async with aiosqlite.connect('db/blword.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                guild_id TEXT,
                word TEXT,
                PRIMARY KEY (guild_id, word)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bypass (
                guild_id TEXT,
                user_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bypass_roles (
                guild_id TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )
        ''')
        await db.commit()
        print("Initialized db/blword.db")

    # Setup votes.db (for top.gg)
    async with aiosqlite.connect('db/votes.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                user_id TEXT PRIMARY KEY,
                total_votes INTEGER NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                last_vote_time TEXT
            )
        ''')
        await db.commit()
        print("Initialized db/votes.db")

    # Setup giveaways.db
    async with aiosqlite.connect('db/giveaways.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                guild_id INTEGER,
                prize TEXT,
                winners INTEGER,
                end_time INTEGER,
                hosted_by INTEGER,
                ended INTEGER DEFAULT 0
            )
        ''')
        await db.commit()
        print("Initialized db/giveaways.db")

    # Setup afk.db
    async with aiosqlite.connect('db/afk.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS afk (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                time INTEGER
            )
        ''')
        await db.commit()
        print("Initialized db/afk.db")

    # Setup badges.db
    async with aiosqlite.connect('db/badges.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS badges (
                user_id INTEGER PRIMARY KEY,
                owner INTEGER DEFAULT 0,
                staff INTEGER DEFAULT 0,
                partner INTEGER DEFAULT 0,
                sponsor INTEGER DEFAULT 0,
                friend INTEGER DEFAULT 0,
                early INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0,
                bug INTEGER DEFAULT 0
            )
        ''')
        await db.commit()
    # Setup invites.db
    async with aiosqlite.connect('db/invites.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS invite_config (
                guild_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                log_channel INTEGER,
                vc_channel INTEGER,
                vc_format TEXT DEFAULT 'Invites: {total}',
                join_msg TEXT,
                leave_msg TEXT,
                log_mode TEXT DEFAULT 'text',
                topz_channel INTEGER,
                topz_message_id INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_invites (
                guild_id INTEGER,
                user_id INTEGER,
                real INTEGER DEFAULT 0,
                fake INTEGER DEFAULT 0,
                leaves INTEGER DEFAULT 0,
                bonus INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS joined_members (
                guild_id INTEGER,
                member_id INTEGER,
                inviter_id INTEGER,
                code TEXT,
                PRIMARY KEY (guild_id, member_id)
            )
        ''')
        await db.commit()
        print("Initialized db/invites.db")

    # Setup tempvc.db
    async with aiosqlite.connect('db/tempvc.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tempvc_creators (
                guild_id TEXT NOT NULL,
                creator_id TEXT NOT NULL,
                name TEXT NOT NULL,
                name_template TEXT,
                category_id TEXT,
                privacy_mode TEXT DEFAULT 'Public',
                user_limit INTEGER DEFAULT 0,
                bitrate TEXT DEFAULT '64kbps',
                sync_permissions TEXT DEFAULT 'Sync with Category',
                PRIMARY KEY (guild_id, creator_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tempvc_config (
                guild_id TEXT PRIMARY KEY,
                interface_channel_id TEXT,
                category_id TEXT,
                name_template TEXT,
                privacy_mode TEXT,
                user_limit INTEGER,
                bitrate TEXT,
                censor_channel_names INTEGER DEFAULT 0,
                allowed_features TEXT
            )
        ''')
        await db.commit()
        print("Initialized db/tempvc.db")

    # Setup marry.db
    async with aiosqlite.connect('db/marry.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS marriages (
                guild_id TEXT NOT NULL,
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                married_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user1_id)
            )
        ''')
        await db.commit()
        print("Initialized db/marry.db")

    # Setup audit_logs.db
    async with aiosqlite.connect('db/audit_logs.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                guild_id INTEGER,
                entry_id TEXT,
                action_code INTEGER,
                module TEXT,
                action TEXT,
                headline TEXT,
                actor_name TEXT,
                actor_id TEXT,
                actor_avatar TEXT,
                target_name TEXT,
                target_id TEXT,
                reason TEXT,
                details TEXT,
                items_json TEXT,
                changes_json TEXT,
                timestamp_str TEXT,
                created_at REAL
            )
        ''')
        async with db.execute("PRAGMA table_info(audit_logs)") as cursor:
            cols = [c[1] for c in await cursor.fetchall()]
            if "headline" not in cols:
                await db.execute("ALTER TABLE audit_logs ADD COLUMN headline TEXT")
            if "items_json" not in cols:
                await db.execute("ALTER TABLE audit_logs ADD COLUMN items_json TEXT")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_guild_created ON audit_logs(guild_id, created_at DESC)")
        await db.commit()
        print("Initialized db/audit_logs.db")

    # High-Performance Query Indexes
    _idx_specs = [
        ('db/afk.db', 'CREATE INDEX IF NOT EXISTS idx_afk_user_id ON afk(user_id);'),
        ('db/audit_logs.db', 'CREATE INDEX IF NOT EXISTS idx_audit_guild_created ON audit_logs(guild_id, created_at DESC);'),
        ('db/audit_logs.db', 'CREATE INDEX IF NOT EXISTS idx_audit_logs_guild_id ON audit_logs(guild_id);'),
        ('db/automod.db', 'CREATE INDEX IF NOT EXISTS idx_automod_incidents_user ON automod_incidents(user_id);'),
        ('db/automod.db', 'CREATE INDEX IF NOT EXISTS idx_automod_punishments_guild ON automod_punishments(guild_id, event);'),
        ('db/automod.db', 'CREATE INDEX IF NOT EXISTS idx_automod_ignored_guild ON automod_ignored(guild_id);'),
        ('db/autonick.db', 'CREATE INDEX IF NOT EXISTS idx_autonick_guild ON autonick_config(guild_id);'),
        ('db/autorole.db', 'CREATE INDEX IF NOT EXISTS idx_autorole_config_guild ON autorole_config(guild_id);'),
        ('db/autorole.db', 'CREATE INDEX IF NOT EXISTS idx_autorole_legacy_guild ON autorole_legacy_backup(guild_id);'),
        ('db/badges.db', 'CREATE INDEX IF NOT EXISTS idx_badges_user_id ON badges(user_id);'),
        ('db/blword.db', 'CREATE INDEX IF NOT EXISTS idx_blword_guild ON blacklist(guild_id);'),
        ('db/blword.db', 'CREATE INDEX IF NOT EXISTS idx_blword_bypass_guild ON bypass(guild_id);'),
        ('db/blword.db', 'CREATE INDEX IF NOT EXISTS idx_blword_bypass_roles_guild ON bypass_roles(guild_id);'),
        ('db/customrole.db', 'CREATE INDEX IF NOT EXISTS idx_custom_roles_guild ON custom_roles(guild_id, name);'),
        ('db/emergency.db', 'CREATE INDEX IF NOT EXISTS idx_authorised_users_user ON authorised_users(user_id);'),
        ('db/festivals.db', 'CREATE INDEX IF NOT EXISTS idx_festivals_config_guild ON festivals_config(guild_id);'),
        ('db/marry.db', 'CREATE INDEX IF NOT EXISTS idx_marriages_user2 ON marriages(user2_id);'),
        ('db/reminders.db', 'CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id);'),
        ('db/anti.db', 'CREATE INDEX IF NOT EXISTS idx_nightmode_guild ON Nightmode(guildId);'),
        ('db/anti.db', 'CREATE INDEX IF NOT EXISTS idx_extraowners_guild ON extraowners(guild_id);'),
        ('db/giveaways.db', 'CREATE INDEX IF NOT EXISTS idx_giveaways_guild_ended ON giveaways(guild_id, ended);'),
        ('db/invites.db', 'CREATE INDEX IF NOT EXISTS idx_joined_members_inviter ON joined_members(guild_id, inviter_id);')
    ]
    for db_file, idx_sql in _idx_specs:
        try:
            async with aiosqlite.connect(db_file) as idb:
                await idb.execute(idx_sql)
                await idb.commit()
        except Exception:
            pass

    # Enforce WAL mode and NORMAL synchronous across all databases
    if os.path.exists("db"):
        for fname in os.listdir("db"):
            if fname.endswith(".db"):
                try:
                    async with aiosqlite.connect(os.path.join("db", fname)) as wdb:
                        await wdb.execute("PRAGMA journal_mode = WAL;")
                        await wdb.execute("PRAGMA synchronous = NORMAL;")
                        await wdb.commit()
                except Exception:
                    pass

    print("[DATABASE] All SQLite database schemas, performance indexes, and WAL modes initialized successfully.", flush=True)

if __name__ == "__main__":
    async def main():
        await setup_all_dbs()
        try:
            from utils.settings_manager import sync_all_settings
            stats = sync_all_settings()
            print(f"[DATABASE MONGO ATLAS] Cloud settings synced for {stats.get('guilds', 0)} guilds successfully!", flush=True)
        except Exception as me:
            print(f"[DATABASE MONGO ATLAS WARNING] {me}", flush=True)
    asyncio.run(main())
