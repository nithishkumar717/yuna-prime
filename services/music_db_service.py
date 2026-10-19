from __future__ import annotations
import os
import re
import time
import asyncio
import threading
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from pymongo import MongoClient, UpdateOne, DESCENDING

def _sanitize_mongo_key(key: str) -> str:
    """Replaces periods and dollar signs in dictionary keys for MongoDB compliance."""
    return re.sub(r'[\.\$]', '_', str(key or 'unknown')).strip()

class MusicDatabaseService:
    """
    Dedicated MongoDB Cloud Service for Yuna Music:
    - 3-Year / Long-term user listening stats (first played date, lifetime counters)
    - Capped song history (50 songs per user / server)
    - Liked songs & favorites
    - User playlists, autoplay history, and playback recovery
    - Persistent voice status and 24/7 connection settings
    - Global deduplicated song catalog
    - Smart recommendation queries based on listening patterns
    """
    _instance: Optional[MusicDatabaseService] = None

    def __init__(self) -> None:
        self.uri = os.getenv("MUSIC_MONGODB_URI") or os.getenv("MUSIC_MONGO_URI") or os.getenv("MONGODB_URI")
        self._client: Optional[MongoClient] = None
        self._db: Any = None
        self._connected: bool = False
        self._legacy_migration_done = False
        self._legacy_migration_lock = threading.Lock()
        self._init_client()

    @classmethod
    def get_instance(cls) -> MusicDatabaseService:
        if cls._instance is None:
            cls._instance = MusicDatabaseService()
        return cls._instance

    def _init_client(self) -> None:
        if not self.uri:
            print("[MUSIC DB] Warning: No MongoDB URI configured for MusicDatabaseService.")
            return

        try:
            from core.database.upsert_sync_engine import resolve_mongo_uri
            effective_uri = resolve_mongo_uri(self.uri)
        except Exception:
            effective_uri = self.uri

        try:
            self._client = MongoClient(
                effective_uri,
                serverSelectionTimeoutMS=15000,
                connectTimeoutMS=15000,
                socketTimeoutMS=25000,
                maxPoolSize=25,
                minPoolSize=0,
                maxIdleTimeMS=120000,
                retryWrites=True
            )
            # Use database 'yunamusic'
            self._db = self._client.get_database("yunamusic")
            self._ensure_indexes()
            self._connected = True
            print("[MUSIC DB] Connected to MongoDB Cloud (yunamusic cluster).")
        except Exception as e:
            print(f"[MUSIC DB] Initial connection warning: {e}")
            self._connected = False

    def _ensure_indexes(self) -> None:
        """Create indexes in the background to ensure blazing fast queries."""
        try:
            if self._db is not None:
                # User history indexes
                self._db.user_history.create_index("userId", unique=True, background=True)
                self._db.user_track_stats.create_index([("userId", 1), ("trackKey", 1)], unique=True, background=True)
                self._db.user_track_stats.create_index([("userId", 1), ("playCount", -1)], background=True)
                self._db.guild_history.create_index("guildId", unique=True, background=True)
                # Liked songs index
                self._db.liked_songs.create_index("userId", unique=True, background=True)
                # Playlists indexes
                self._db.playlists.create_index([("userId", 1), ("name", 1)], unique=True, background=True)
                self._db.playlists.create_index("isPublic", background=True)
                # Song catalog
                self._db.song_catalog.create_index("canonicalUrl", unique=True, background=True)
                self._db.song_catalog.create_index("playCount", background=True)
                self._db.song_catalog.create_index("title", background=True)

                # Persistent music and voice configuration collections.
                self._db.vc_status_configs.create_index("channelId", unique=True, background=True)
                self._db.vc_status_configs.create_index([("guildId", 1), ("channelId", 1)], background=True)
                self._db.voice247.create_index("guildId", unique=True, background=True)
                self._db.vc_daily_greetings.create_index("memberId", unique=True, background=True)
                self._db.music_playback_state.create_index("guildId", unique=True, background=True)
                self._db.music_playback_resume_state.create_index("guildId", unique=True, background=True)
                self._db.saved_playlists.create_index([("userId", 1), ("name", 1)], unique=True, background=True)
                self._db.saved_playlists.create_index([("isPrivate", 1), ("guildId", 1)], background=True)
                # Playlist sharing is disabled: migrate older shared entries to private.
                self._db.saved_playlists.update_many(
                    {"isPrivate": {"$ne": True}},
                    {"$set": {"isPrivate": True}},
                )
                self._db.autoplay_playlists.create_index("guildId", unique=True, background=True)
                self._db.autoplay_played_history.create_index([("guildId", 1), ("playedAt", -1)], background=True)
        except Exception as e:
            print(f"[MUSIC DB] Index setup note: {e}")

    def is_connected(self) -> bool:
        """Returns True if MongoDB client and database are initialized. Non-blocking."""
        return bool(self._client is not None and self._db is not None and self._connected)

    async def ping_async(self, timeout_secs: float = 2.0) -> bool:
        """Asynchronously pings MongoDB in a background thread without blocking the event loop."""
        if not self._client or self._db is None:
            return False
        try:
            def _ping():
                self._client.admin.command("ping")
            await asyncio.wait_for(asyncio.to_thread(_ping), timeout=timeout_secs)
            self._connected = True
            return True
        except Exception:
            return False

    # =========================================================================
    # 1. PLAYBACK HISTORY & 3-YEAR USER / GUILD STATS
    # =========================================================================

    def _record_song_play_sync(self, user_id: int, guild_id: int, track: Dict[str, Any]) -> None:
        if self._db is None:
            return

        now = datetime.now(timezone.utc)
        title = track.get("title") or "Unknown Track"
        artist = track.get("uploader") or track.get("artist") or "Unknown Artist"
        url = track.get("url") or track.get("webpage_url") or ""
        duration = int(track.get("duration") or 0)
        minutes = round(duration / 60, 2) if duration > 0 else 3.0
        thumbnail = track.get("thumbnail") or ""

        track_summary = {
            "title": title,
            "artist": artist,
            "url": url,
            "duration": duration,
            "thumbnail": thumbnail,
            "playedAt": now.isoformat(),
            "guildId": str(guild_id)
        }

        artist_key = _sanitize_mongo_key(artist)[:50]

        # 1. Update User Profile & Lifetime Stats (Preserves first_played_at forever!)
        if user_id and user_id > 0:
            user_filter = {"userId": str(user_id)}
            user_update = {
                "$setOnInsert": {
                    "userId": str(user_id),
                    "firstPlayedAt": now,
                    "createdAt": now
                },
                "$set": {
                    "lastPlayedAt": now
                },
                "$inc": {
                    "totalPlays": 1,
                    "totalMinutes": minutes,
                    f"artists.{artist_key}": 1
                },
                "$push": {
                    "recentHistory": {
                        "$each": [track_summary],
                        "$slice": -50  # Keep latest 50 tracks to keep storage strictly under 2KB per user!
                    }
                }
            }
            try:
                self._db.user_history.update_one(user_filter, user_update, upsert=True)
            except Exception as e:
                print(f"[MUSIC DB] Error updating user history for {user_id}: {e}")

            # Keep lifetime per-user play counts separate from the capped recentHistory list.
            # This preserves the existing history while enabling accurate frequently played songs.
            if url:
                track_key_raw = f"{title.strip().lower()}|{artist.strip().lower()}"
                track_key = hashlib.sha256(track_key_raw.encode("utf-8")).hexdigest()
                try:
                    self._db.user_track_stats.update_one(
                        {"userId": str(user_id), "trackKey": track_key},
                        {
                            "$setOnInsert": {"userId": str(user_id), "trackKey": track_key},
                            "$set": {
                                "title": title,
                                "artist": artist,
                                "url": url,
                                "thumbnail": thumbnail,
                                "duration": duration,
                                "lastPlayedAt": now,
                            },
                            "$inc": {"playCount": 1},
                        },
                        upsert=True,
                    )
                except Exception as e:
                    print(f"[MUSIC DB] Error updating per-user track stats for {user_id}: {e}")

        # 2. Update Guild History (Server stats)
        if guild_id and guild_id > 0:
            guild_filter = {"guildId": str(guild_id)}
            guild_update = {
                "$setOnInsert": {
                    "guildId": str(guild_id),
                    "firstPlayedAt": now
                },
                "$set": {
                    "lastPlayedAt": now
                },
                "$inc": {
                    "totalPlays": 1,
                    "totalMinutes": minutes
                },
                "$push": {
                    "recentHistory": {
                        "$each": [track_summary],
                        "$slice": -50  # Keep latest 50 tracks
                    }
                }
            }
            try:
                self._db.guild_history.update_one(guild_filter, guild_update, upsert=True)
            except Exception as e:
                print(f"[MUSIC DB] Error updating guild history for {guild_id}: {e}")

        # 3. Upsert Global Deduplicated Catalog
        if url:
            catalog_filter = {"canonicalUrl": url}
            catalog_update = {
                "$setOnInsert": {
                    "canonicalUrl": url,
                    "title": title,
                    "artist": artist,
                    "duration": duration,
                    "thumbnail": thumbnail,
                    "firstSeenAt": now
                },
                "$set": {
                    "lastPlayedAt": now
                },
                "$inc": {
                    "playCount": 1
                }
            }
            try:
                self._db.song_catalog.update_one(catalog_filter, catalog_update, upsert=True)
            except Exception as e:
                pass

    async def record_song_play(self, user_id: int, guild_id: int, track: Dict[str, Any]) -> None:
        """Asynchronously records playback event in the thread pool without blocking Discord loop."""
        await asyncio.to_thread(self._record_song_play_sync, user_id, guild_id, track)

    def _get_user_history_sync(self, user_id: int) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return self._db.user_history.find_one({"userId": str(user_id)})

    async def get_user_history(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_user_history_sync, user_id)

    def _get_user_top_tracks_sync(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        cursor = self._db.user_track_stats.find({"userId": str(user_id)}).sort(
            [("playCount", DESCENDING), ("lastPlayedAt", DESCENDING)]
        ).limit(max(1, min(int(limit), 50)))
        return [
            {
                "title": str(doc.get("title") or "Unknown track"),
                "artist": str(doc.get("artist") or "Unknown artist"),
                "url": str(doc.get("url") or ""),
                "thumbnail": str(doc.get("thumbnail") or ""),
                "duration": int(doc.get("duration") or 0),
                "playCount": int(doc.get("playCount") or 0),
                "lastPlayedAt": doc.get("lastPlayedAt").isoformat() if hasattr(doc.get("lastPlayedAt"), "isoformat") else str(doc.get("lastPlayedAt") or ""),
            }
            for doc in cursor
        ]

    async def get_user_top_tracks(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_user_top_tracks_sync, user_id, limit)

    def _get_guild_history_sync(self, guild_id: int) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return self._db.guild_history.find_one({"guildId": str(guild_id)})

    async def get_guild_history(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_guild_history_sync, guild_id)

    # =========================================================================
    # 2. "FIRST PLAYED 3 YEARS AGO" & SONG STATS LOOKUP
    # =========================================================================

    def _get_song_info_stats_sync(self, user_id: int, track_url: str, track_title: str) -> Dict[str, Any]:
        """Looks up how many times this user has heard this song, when they first heard it, and global plays."""
        res = {
            "user_play_count": 0,
            "first_played_at": None,
            "global_play_count": 0,
            "member_since": None
        }
        if self._db is None:
            return res

        # Check global catalog
        cat = self._db.song_catalog.find_one({"canonicalUrl": track_url}) if track_url else None
        if not cat and track_title:
            cat = self._db.song_catalog.find_one({"title": track_title})
        if cat:
            res["global_play_count"] = cat.get("playCount", 1)
            res["first_played_at"] = cat.get("firstSeenAt")

        # Check user history
        user_doc = self._db.user_history.find_one({"userId": str(user_id)})
        if user_doc:
            res["member_since"] = user_doc.get("firstPlayedAt")
            recent = user_doc.get("recentHistory") or []
            cnt = sum(1 for t in recent if (track_url and t.get("url") == track_url) or (t.get("title") == track_title))
            res["user_play_count"] = cnt
            # If user has an artist count
            artists = user_doc.get("artists") or {}
            if cat and cat.get("artist"):
                clean_art = _sanitize_mongo_key(cat["artist"])
                res["user_artist_plays"] = artists.get(clean_art, 0)

        return res

    async def get_song_info_stats(self, user_id: int, track_url: str, track_title: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self._get_song_info_stats_sync, user_id, track_url, track_title)

    # =========================================================================
    # 3. LIKED SONGS SYSTEM
    # =========================================================================

    def _like_song_sync(self, user_id: int, track: Dict[str, Any]) -> Tuple[bool, str]:
        """Likes a track for a user. Returns (success, message)."""
        if self._db is None:
            return False, "Database not connected."

        now = datetime.now(timezone.utc)
        title = track.get("title") or "Unknown Track"
        url = track.get("url") or track.get("webpage_url") or ""
        artist = track.get("uploader") or track.get("artist") or "Unknown Artist"
        duration = int(track.get("duration") or 0)
        thumbnail = track.get("thumbnail") or ""

        track_data = {
            "title": title,
            "artist": artist,
            "url": url,
            "duration": duration,
            "thumbnail": thumbnail,
            "likedAt": now.isoformat()
        }

        user_doc = self._db.liked_songs.find_one({"userId": str(user_id)})
        if user_doc:
            current_tracks = user_doc.get("tracks", [])
            # Check duplicate
            if any(t.get("url") == url or (t.get("title") == title and t.get("artist") == artist) for t in current_tracks):
                return False, f"**{title}** is already in your Liked Songs!"
            if len(current_tracks) >= 500:
                return False, "You reached the limit of 500 Liked Songs. Please remove some first."

        self._db.liked_songs.update_one(
            {"userId": str(user_id)},
            {
                "$setOnInsert": {"userId": str(user_id), "createdAt": now},
                "$push": {"tracks": track_data}
            },
            upsert=True
        )
        return True, f"Added **{title}** to your Liked Songs! ❤️"

    async def like_song(self, user_id: int, track: Dict[str, Any]) -> Tuple[bool, str]:
        return await asyncio.to_thread(self._like_song_sync, user_id, track)

    def _unlike_song_sync(self, user_id: int, url_or_title: str) -> Tuple[bool, str]:
        if self._db is None:
            return False, "Database not connected."

        user_doc = self._db.liked_songs.find_one({"userId": str(user_id)})
        if not user_doc or not user_doc.get("tracks"):
            return False, "You don't have any Liked Songs yet."

        tracks = user_doc.get("tracks", [])
        initial_len = len(tracks)
        new_tracks = [t for t in tracks if t.get("url") != url_or_title and t.get("title", "").lower() != url_or_title.lower()]

        if len(new_tracks) == initial_len:
            return False, "Track not found in your Liked Songs."

        self._db.liked_songs.update_one(
            {"userId": str(user_id)},
            {"$set": {"tracks": new_tracks}}
        )
        return True, "Removed track from your Liked Songs! 💔"

    async def unlike_song(self, user_id: int, url_or_title: str) -> Tuple[bool, str]:
        return await asyncio.to_thread(self._unlike_song_sync, user_id, url_or_title)

    def _get_liked_songs_sync(self, user_id: int) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        doc = self._db.liked_songs.find_one({"userId": str(user_id)})
        return doc.get("tracks", []) if doc else []

    async def get_liked_songs(self, user_id: int) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_liked_songs_sync, user_id)

    # =========================================================================
    # 4. CLOUD PLAYLISTS (Unlimited cross-device storage)
    # =========================================================================

    def _save_playlist_sync(self, user_id: int, name: str, tracks: List[Dict[str, Any]], creator_name: str = "Unknown", is_private: bool = False, guild_id: int = 0) -> Tuple[bool, str]:
        if self._db is None:
            return False, "Database not connected."

        clean_name = name.strip()
        if not clean_name:
            return False, "Playlist name cannot be empty."

        now = datetime.now(timezone.utc)
        filter_query = {"userId": str(user_id), "name": clean_name.lower()}

        # Limit to max 25 playlists per user to prevent spam
        count = self._db.playlists.count_documents({"userId": str(user_id)})
        existing = self._db.playlists.find_one(filter_query)
        if not existing and count >= 25:
            return False, "You have reached the maximum limit of 25 custom playlists."

        update_data = {
            "$set": {
                "userId": str(user_id),
                "name": clean_name.lower(),
                "displayName": clean_name,
                "creatorName": creator_name,
                "isPrivate": bool(is_private),
                "guildId": str(guild_id),
                "tracks": tracks[:200],  # Max 200 songs per playlist
                "trackCount": len(tracks[:200]),
                "updatedAt": now
            },
            "$setOnInsert": {
                "createdAt": now
            }
        }
        self._db.playlists.update_one(filter_query, update_data, upsert=True)
        return True, f"Playlist **{clean_name}** ({len(tracks)} tracks) saved to Cloud!"

    async def save_playlist(self, user_id: int, name: str, tracks: List[Dict[str, Any]], creator_name: str = "Unknown", is_private: bool = False, guild_id: int = 0) -> Tuple[bool, str]:
        return await asyncio.to_thread(self._save_playlist_sync, user_id, name, tracks, creator_name, is_private, guild_id)

    def _get_playlist_sync(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return self._db.playlists.find_one({"userId": str(user_id), "name": name.strip().lower()})

    async def get_playlist(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_playlist_sync, user_id, name)

    def _list_user_playlists_sync(self, user_id: int) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        cursor = self._db.playlists.find({"userId": str(user_id)}).sort("updatedAt", DESCENDING)
        return list(cursor)

    async def list_user_playlists(self, user_id: int) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._list_user_playlists_sync, user_id)

    def _delete_playlist_sync(self, user_id: int, name: str) -> Tuple[bool, str]:
        if self._db is None:
            return False, "Database not connected."
        res = self._db.playlists.delete_one({"userId": str(user_id), "name": name.strip().lower()})
        if res.deleted_count > 0:
            return True, f"Playlist **{name}** deleted successfully."
        return False, f"Playlist **{name}** not found."

    async def delete_playlist(self, user_id: int, name: str) -> Tuple[bool, str]:
        return await asyncio.to_thread(self._delete_playlist_sync, user_id, name)

    # =========================================================================
    # 5. SMART MUSIC SUGGESTIONS & TOP CHARTS
    # =========================================================================

    def _get_user_recommendations_sync(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Generates smart track suggestions by:
        1. Finding the user's top 3 most-played artists from MongoDB.
        2. Querying the global song catalog for highest-played songs by those artists that the user hasn't heard recently.
        3. Blending with top trending tracks from the global catalog.
        """
        if self._db is None:
            return []

        suggestions: List[Dict[str, Any]] = []
        user_doc = self._db.user_history.find_one({"userId": str(user_id)})
        recent_urls = set()

        if user_doc:
            recent = user_doc.get("recentHistory") or []
            recent_urls = {t.get("url") for t in recent if t.get("url")}
            artists = user_doc.get("artists") or {}
            # Sort artists by play count
            sorted_artists = sorted(artists.items(), key=lambda x: x[1], reverse=True)[:3]
            top_artist_names = [a[0] for a in sorted_artists]

            for art_slug in top_artist_names:
                regex_pattern = re.compile(re.escape(art_slug.replace('_', ' ')), re.IGNORECASE)
                cursor = self._db.song_catalog.find(
                    {"artist": {"$regex": regex_pattern}, "canonicalUrl": {"$nin": list(recent_urls)}}
                ).sort("playCount", DESCENDING).limit(3)
                for doc in cursor:
                    suggestions.append({
                        "title": doc.get("title"),
                        "artist": doc.get("artist"),
                        "url": doc.get("canonicalUrl"),
                        "duration": doc.get("duration", 0),
                        "thumbnail": doc.get("thumbnail"),
                        "reason": f"Because you listen to {art_slug.replace('_', ' ').title()}"
                    })

        # Fill remaining slots with global top trending tracks
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            already_suggested = {s.get("url") for s in suggestions} | recent_urls
            cursor = self._db.song_catalog.find(
                {"canonicalUrl": {"$nin": list(already_suggested)}}
            ).sort("playCount", DESCENDING).limit(remaining)
            for doc in cursor:
                suggestions.append({
                    "title": doc.get("title"),
                    "artist": doc.get("artist"),
                    "url": doc.get("canonicalUrl"),
                    "duration": doc.get("duration", 0),
                    "thumbnail": doc.get("thumbnail"),
                    "reason": "Top trending song on Yuna"
                })

        return suggestions[:limit]

    async def get_user_recommendations(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_user_recommendations_sync, user_id, limit)

    # =========================================================================
    # 6. MUSIC / VOICE PERSISTENCE (yunamusic MongoDB)
    # =========================================================================

    @staticmethod
    def _plain_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        result = dict(doc)
        result.pop("_id", None)
        return result

    # -- Permanent voice-channel statuses -----------------------------------

    @staticmethod
    def _vc_status_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        doc = MusicDatabaseService._plain_doc(doc)
        if not doc:
            return None
        return {
            "guild_id": int(doc.get("guildId", 0)),
            "channel_id": int(doc.get("channelId", 0)),
            "status_text": doc.get("statusText"),
            "emoji": doc.get("emoji"),
            "full_status": doc.get("fullStatus", ""),
            "enforcement": bool(doc.get("enforcement", True)),
            "created_at": doc.get("createdAt", 0),
            "updated_at": doc.get("updatedAt", 0),
            "updated_by": int(doc.get("updatedBy", 0)),
        }

    def _get_vc_status_config_sync(self, channel_id: int) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return self._vc_status_doc(self._db.vc_status_configs.find_one({"channelId": str(channel_id)}))

    async def get_vc_status_config(self, channel_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_vc_status_config_sync, channel_id)

    def _get_vc_status_guild_configs_sync(self, guild_id: int) -> Dict[int, Dict[str, Any]]:
        if self._db is None:
            return {}
        configs = {}
        for doc in self._db.vc_status_configs.find({"guildId": str(guild_id)}):
            parsed = self._vc_status_doc(doc)
            if parsed:
                configs[parsed["channel_id"]] = parsed
        return configs

    async def get_vc_status_guild_configs(self, guild_id: int) -> Dict[int, Dict[str, Any]]:
        return await asyncio.to_thread(self._get_vc_status_guild_configs_sync, guild_id)

    def _get_all_enforced_vc_status_configs_sync(self) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        return [
            parsed for doc in self._db.vc_status_configs.find({"enforcement": True})
            if (parsed := self._vc_status_doc(doc))
        ]

    async def get_all_enforced_vc_status_configs(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_all_enforced_vc_status_configs_sync)

    def _save_vc_status_config_sync(
        self, guild_id: int, channel_id: int, status_text: Optional[str], emoji: Optional[str],
        full_status: str, enforcement: bool, user_id: int
    ) -> Dict[str, Any]:
        now = time.time()
        if self._db is None:
            return {
                "guild_id": guild_id, "channel_id": channel_id, "status_text": status_text,
                "emoji": emoji, "full_status": full_status, "enforcement": enforcement,
                "created_at": now, "updated_at": now, "updated_by": user_id,
            }
        existing = self._db.vc_status_configs.find_one({"channelId": str(channel_id)}, {"createdAt": 1})
        created_at = existing.get("createdAt", now) if existing else now
        doc = {
            "guildId": str(guild_id), "channelId": str(channel_id),
            "statusText": status_text, "emoji": emoji, "fullStatus": full_status,
            "enforcement": bool(enforcement), "createdAt": created_at,
            "updatedAt": now, "updatedBy": int(user_id),
        }
        self._db.vc_status_configs.update_one(
            {"channelId": str(channel_id)}, {"$set": doc}, upsert=True
        )
        return self._vc_status_doc(doc) or {}

    async def save_vc_status_config(
        self, guild_id: int, channel_id: int, status_text: Optional[str], emoji: Optional[str],
        full_status: str, enforcement: bool = True, user_id: int = 0
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._save_vc_status_config_sync, guild_id, channel_id, status_text, emoji,
            full_status, enforcement, user_id
        )

    def _toggle_vc_status_enforcement_sync(self, channel_id: int, enabled: bool) -> bool:
        if self._db is None:
            return False
        result = self._db.vc_status_configs.update_one(
            {"channelId": str(channel_id)},
            {"$set": {"enforcement": bool(enabled), "updatedAt": time.time()}},
        )
        return result.matched_count > 0

    async def toggle_vc_status_enforcement(self, channel_id: int, enabled: bool) -> bool:
        return await asyncio.to_thread(self._toggle_vc_status_enforcement_sync, channel_id, enabled)

    def _delete_vc_status_config_sync(self, channel_id: int) -> bool:
        if self._db is None:
            return False
        return self._db.vc_status_configs.delete_one({"channelId": str(channel_id)}).deleted_count > 0

    async def delete_vc_status_config(self, channel_id: int) -> bool:
        return await asyncio.to_thread(self._delete_vc_status_config_sync, channel_id)

    def _delete_vc_status_guild_configs_sync(self, guild_id: int) -> int:
        if self._db is None:
            return 0
        return self._db.vc_status_configs.delete_many({"guildId": str(guild_id)}).deleted_count

    async def delete_vc_status_guild_configs(self, guild_id: int) -> int:
        return await asyncio.to_thread(self._delete_vc_status_guild_configs_sync, guild_id)

    # -- 24/7 connections and voice greetings -------------------------------

    def get_voice247_configs_sync(self) -> Dict[int, Dict[str, Any]]:
        if self._db is None:
            return {}
        return {
            int(doc["guildId"]): {
                "channel_id": int(doc["channelId"]),
                "text_channel_id": int(doc["textChannelId"]) if doc.get("textChannelId") else None,
            }
            for doc in self._db.voice247.find({})
            if doc.get("guildId") and doc.get("channelId")
        }

    async def get_voice247_configs(self) -> Dict[int, Dict[str, Any]]:
        return await asyncio.to_thread(self.get_voice247_configs_sync)

    def _set_voice247_sync(self, guild_id: int, channel_id: int, text_channel_id: Optional[int]) -> bool:
        if self._db is None:
            return False
        self._db.voice247.update_one(
            {"guildId": str(guild_id)},
            {"$set": {
                "guildId": str(guild_id), "channelId": str(channel_id),
                "textChannelId": str(text_channel_id) if text_channel_id else None,
                "updatedAt": time.time(),
            }},
            upsert=True,
        )
        return True

    async def set_voice247(self, guild_id: int, channel_id: int, text_channel_id: Optional[int]) -> bool:
        return await asyncio.to_thread(self._set_voice247_sync, guild_id, channel_id, text_channel_id)

    def _delete_voice247_sync(self, guild_id: int) -> bool:
        if self._db is None:
            return False
        self._db.voice247.delete_one({"guildId": str(guild_id)})
        return True

    async def delete_voice247(self, guild_id: int) -> bool:
        return await asyncio.to_thread(self._delete_voice247_sync, guild_id)

    def _update_voice247_channel_sync(self, guild_id: int, channel_id: int) -> bool:
        if self._db is None:
            return False
        result = self._db.voice247.update_one(
            {"guildId": str(guild_id)},
            {"$set": {"channelId": str(channel_id), "updatedAt": time.time()}},
        )
        return result.matched_count > 0

    async def update_voice247_channel(self, guild_id: int, channel_id: int) -> bool:
        return await asyncio.to_thread(self._update_voice247_channel_sync, guild_id, channel_id)

    def _mark_voice_greeted_sync(self, member_id: int, greeted_date: str) -> bool:
        if self._db is None:
            return False
        self._db.vc_daily_greetings.update_one(
            {"memberId": str(member_id)},
            {"$set": {"memberId": str(member_id), "greetedDate": greeted_date}},
            upsert=True,
        )
        return True

    async def mark_voice_greeted(self, member_id: int, greeted_date: str) -> bool:
        return await asyncio.to_thread(self._mark_voice_greeted_sync, member_id, greeted_date)

    def _get_voice_greetings_for_date_sync(self, greeted_date: str) -> Dict[int, str]:
        if self._db is None:
            return {}
        return {
            int(doc["memberId"]): doc.get("greetedDate", greeted_date)
            for doc in self._db.vc_daily_greetings.find({"greetedDate": greeted_date})
            if doc.get("memberId")
        }

    async def get_voice_greetings_for_date(self, greeted_date: str) -> Dict[int, str]:
        return await asyncio.to_thread(self._get_voice_greetings_for_date_sync, greeted_date)

    def _prune_voice_greetings_sync(self, before_date: str) -> int:
        if self._db is None:
            return 0
        return self._db.vc_daily_greetings.delete_many({"greetedDate": {"$lt": before_date}}).deleted_count

    async def prune_voice_greetings(self, before_date: str) -> int:
        return await asyncio.to_thread(self._prune_voice_greetings_sync, before_date)

    # -- Playback recovery state --------------------------------------------

    @staticmethod
    def _playback_state_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        doc = MusicDatabaseService._plain_doc(doc)
        if not doc:
            return None
        return {
            "guild_id": int(doc.get("guildId", 0)),
            "channel_id": int(doc["channelId"]) if doc.get("channelId") else None,
            "text_channel_id": int(doc["textChannelId"]) if doc.get("textChannelId") else None,
            "current_song": doc.get("currentSong"),
            "queue": doc.get("queue") or [],
            "autoplay": bool(doc.get("autoplay", True)),
            "autoplay_lang": doc.get("autoplayLang", "auto"),
            "autoplay_mood": doc.get("autoplayMood", "auto"),
            "is_playing": bool(doc.get("isPlaying", False)),
            "is_paused": bool(doc.get("isPaused", False)),
            "updated_at": doc.get("updatedAt", 0),
        }

    def _save_music_playback_state_sync(self, guild_id: int, state: Dict[str, Any]) -> bool:
        if self._db is None:
            return False
        now = int(time.time())
        doc = {
            "guildId": str(guild_id),
            "channelId": str(state["channel_id"]) if state.get("channel_id") else None,
            "textChannelId": str(state["text_channel_id"]) if state.get("text_channel_id") else None,
            "currentSong": state.get("current_song"),
            "queue": state.get("queue") or [],
            "autoplay": bool(state.get("autoplay", True)),
            "autoplayLang": state.get("autoplay_lang", "auto"),
            "autoplayMood": state.get("autoplay_mood", "auto"),
            "isPlaying": bool(state.get("is_playing", False)),
            "isPaused": bool(state.get("is_paused", False)),
            "updatedAt": int(state.get("updated_at", now)),
        }
        self._db.music_playback_state.update_one({"guildId": str(guild_id)}, {"$set": doc}, upsert=True)
        return True

    async def save_music_playback_state(self, guild_id: int, state: Dict[str, Any]) -> bool:
        return await asyncio.to_thread(self._save_music_playback_state_sync, guild_id, state)

    def _get_music_playback_state_sync(self, guild_id: int) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        return self._playback_state_doc(self._db.music_playback_state.find_one({"guildId": str(guild_id)}))

    async def get_music_playback_state(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_music_playback_state_sync, guild_id)

    def _get_active_music_playback_states_sync(self, max_age_seconds: int = 1800) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        cutoff = int(time.time()) - max_age_seconds
        try:
            self._db.music_playback_state.update_many(
                {"isPlaying": True, "$or": [{"updatedAt": {"$lt": cutoff}}, {"updatedAt": {"$exists": False}}]},
                {"$set": {"isPlaying": False, "isPaused": False}}
            )
        except Exception:
            pass
        return [
            parsed for doc in self._db.music_playback_state.find({
                "isPlaying": True,
                "isPaused": {"$ne": True},
                "updatedAt": {"$gte": cutoff}
            })
            if (parsed := self._playback_state_doc(doc))
        ]

    async def get_active_music_playback_states(self, max_age_seconds: int = 1800) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_active_music_playback_states_sync, max_age_seconds)

    def _clear_music_playback_state_sync(self, guild_id: int) -> bool:
        if self._db is None:
            return False
        self._db.music_playback_state.update_one(
            {"guildId": str(guild_id)},
            {"$set": {"currentSong": None, "queue": [], "isPlaying": False, "isPaused": False, "updatedAt": int(time.time())}},
        )
        return True

    async def clear_music_playback_state(self, guild_id: int) -> bool:
        return await asyncio.to_thread(self._clear_music_playback_state_sync, guild_id)

    async def update_music_playback_channel(self, guild_id: int, channel_id: int) -> bool:
        def _update() -> bool:
            if self._db is None:
                return False
            result = self._db.music_playback_state.update_one(
                {"guildId": str(guild_id)},
                {"$set": {"channelId": str(channel_id), "updatedAt": int(time.time())}},
            )
            return result.matched_count > 0
        return await asyncio.to_thread(_update)

    # -- Restart snapshots (formerly playback_resume_state.json) -------------

    def save_playback_resume_states_sync(self, saved_at: float, guilds: Dict[str, Dict[str, Any]]) -> int:
        if self._db is None:
            return 0
        collection = self._db.music_playback_resume_state
        if not guilds:
            collection.delete_many({})
            return 0
        guild_ids = list(guilds.keys())
        collection.delete_many({"guildId": {"$nin": guild_ids}})
        for guild_id, entry in guilds.items():
            collection.update_one(
                {"guildId": str(guild_id)},
                {"$set": {"guildId": str(guild_id), "entry": entry, "savedAt": saved_at}},
                upsert=True,
            )
        return len(guilds)

    def _get_playback_resume_states_sync(self) -> Dict[str, Dict[str, Any]]:
        if self._db is None:
            return {}
        states = {}
        for doc in self._db.music_playback_resume_state.find({}):
            if not doc.get("guildId"):
                continue
            entry = dict(doc.get("entry") or {})
            entry["_snapshot_saved_at"] = float(doc.get("savedAt", 0) or 0)
            states[str(doc["guildId"])] = entry
        return states

    async def get_playback_resume_states(self) -> Dict[str, Dict[str, Any]]:
        return await asyncio.to_thread(self._get_playback_resume_states_sync)

    def get_playback_resume_state_sync(self, guild_id: int) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        doc = self._db.music_playback_resume_state.find_one({"guildId": str(guild_id)})
        return doc.get("entry") if doc else None

    async def get_playback_resume_state(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self.get_playback_resume_state_sync, guild_id)

    def clear_playback_resume_states_sync(self) -> None:
        if self._db is not None:
            self._db.music_playback_resume_state.delete_many({})

    async def clear_playback_resume_states(self) -> None:
        await asyncio.to_thread(self.clear_playback_resume_states_sync)

    # -- Saved playlists and autoplay history -------------------------------

    @staticmethod
    def _saved_playlist_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        doc = MusicDatabaseService._plain_doc(doc)
        if not doc:
            return None
        return {
            "user_id": int(doc.get("userId", 0)),
            "owner_id": int(doc.get("userId", 0)),
            "name": doc.get("name", ""),
            "display_name": doc.get("displayName") or doc.get("name", ""),
            "tracks": doc.get("tracks") or [],
            "created_at": int(doc.get("createdAt", 0)),
            "creator_name": doc.get("creatorName") or "Unknown",
            "is_private": int(bool(doc.get("isPrivate", False))),
            "guild_id": int(doc.get("guildId", 0) or 0),
        }

    def _get_saved_playlist_sync(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        if self._db is None:
            return None
        doc = self._db.saved_playlists.find_one({"userId": str(user_id), "name": name.strip().lower()})
        return self._saved_playlist_doc(doc)

    async def get_saved_playlist(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_saved_playlist_sync, user_id, name)

    def _save_saved_playlist_sync(
        self, user_id: int, name: str, tracks: List[Dict[str, Any]], creator_name: str,
        is_private: int, guild_id: int, created_at: Optional[int] = None
    ) -> bool:
        if self._db is None:
            return False
        clean_name = name.strip().lower()
        key = {"userId": str(user_id), "name": clean_name}
        existing = self._db.saved_playlists.find_one(key, {"createdAt": 1})
        now = int(time.time())
        self._db.saved_playlists.update_one(
            key,
            {"$set": {
                **key, "displayName": name.strip(), "tracks": tracks,
                "creatorName": creator_name or "Unknown", "isPrivate": True,
                "guildId": str(guild_id or 0), "updatedAt": now,
            }, "$setOnInsert": {"createdAt": int(created_at or (existing or {}).get("createdAt", now))}},
            upsert=True,
        )
        return True

    async def save_saved_playlist(
        self, user_id: int, name: str, tracks: List[Dict[str, Any]], creator_name: str = "Unknown",
        is_private: int = 1, guild_id: int = 0, created_at: Optional[int] = None
    ) -> bool:
        return await asyncio.to_thread(
            self._save_saved_playlist_sync, user_id, name, tracks, creator_name,
            is_private, guild_id, created_at
        )

    def _list_saved_playlists_sync(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        cursor = self._db.saved_playlists.find(query).sort("updatedAt", DESCENDING)
        return [parsed for doc in cursor if (parsed := self._saved_playlist_doc(doc))]

    async def list_saved_playlists(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._list_saved_playlists_sync, query)

    async def list_all_saved_playlists(self) -> List[Dict[str, Any]]:
        return await self.list_saved_playlists({})

    async def list_public_saved_playlists(self) -> List[Dict[str, Any]]:
        # Public playlist discovery is intentionally disabled.
        return []

    async def update_saved_playlist_tracks(self, user_id: int, name: str, tracks: List[Dict[str, Any]]) -> bool:
        def _update() -> bool:
            if self._db is None:
                return False
            result = self._db.saved_playlists.update_one(
                {"userId": str(user_id), "name": name.strip().lower()},
                {"$set": {"tracks": tracks, "updatedAt": int(time.time())}},
            )
            return result.matched_count > 0
        return await asyncio.to_thread(_update)

    async def set_saved_playlist_privacy(self, user_id: int, name: str, is_private: int) -> bool:
        def _update() -> bool:
            if self._db is None:
                return False
            result = self._db.saved_playlists.update_one(
                {"userId": str(user_id), "name": name.strip().lower()},
                {"$set": {"isPrivate": True, "updatedAt": int(time.time())}},
            )
            return result.matched_count > 0
        return await asyncio.to_thread(_update)

    async def delete_saved_playlist(self, user_id: int, name: str) -> bool:
        def _delete() -> bool:
            if self._db is None:
                return False
            return self._db.saved_playlists.delete_one(
                {"userId": str(user_id), "name": name.strip().lower()}
            ).deleted_count > 0
        return await asyncio.to_thread(_delete)

    async def rename_saved_playlist(self, user_id: int, old_name: str, new_name: str) -> bool:
        def _rename() -> bool:
            if self._db is None:
                return False
            old_key = {"userId": str(user_id), "name": old_name.strip().lower()}
            new_key = {"userId": str(user_id), "name": new_name.strip().lower()}
            old_doc = self._db.saved_playlists.find_one(old_key)
            if not old_doc:
                return False
            collision = self._db.saved_playlists.find_one(new_key)
            if collision and collision.get("_id") != old_doc.get("_id"):
                return False
            old_doc["name"] = new_key["name"]
            old_doc["displayName"] = new_name.strip()
            old_doc["updatedAt"] = int(time.time())
            old_doc.pop("_id", None)
            self._db.saved_playlists.replace_one(new_key, old_doc, upsert=True)
            if old_key != new_key:
                self._db.saved_playlists.delete_one(old_key)
            return True
        return await asyncio.to_thread(_rename)

    async def find_public_saved_playlist(self, name: str, include_private: bool = False) -> Optional[Dict[str, Any]]:
        # Private playlists must always be looked up with an explicit owner ID.
        return None

    async def get_public_saved_tracks(self) -> List[Dict[str, Any]]:
        playlists = await self.list_public_saved_playlists()
        return [track for playlist in playlists for track in playlist.get("tracks", []) if isinstance(track, dict)]

    async def get_all_saved_playlists_for_migration(self) -> List[Dict[str, Any]]:
        return await self.list_all_saved_playlists()

    async def get_recent_autoplay_track_keys(self, guild_id: int, cutoff: int) -> set[str]:
        def _get() -> set[str]:
            if self._db is None:
                return set()
            keys: set[str] = set()
            for doc in self._db.autoplay_played_history.find({"guildId": str(guild_id), "playedAt": {"$gte": cutoff}}):
                for key in (doc.get("trackId"), doc.get("trackUrl"), doc.get("titleNorm")):
                    if key:
                        keys.add(str(key))
            return keys
        return await asyncio.to_thread(_get)

    async def record_autoplay_track(self, guild_id: int, track_id: str, track_url: str, title_norm: str, played_at: int) -> bool:
        def _record() -> bool:
            if self._db is None:
                return False
            self._db.autoplay_played_history.insert_one({
                "guildId": str(guild_id), "trackId": track_id, "trackUrl": track_url,
                "titleNorm": title_norm, "playedAt": int(played_at),
            })
            # Retain the latest 250 records per guild.
            old_ids = [doc["_id"] for doc in self._db.autoplay_played_history.find(
                {"guildId": str(guild_id)}, {"_id": 1}
            ).sort("playedAt", DESCENDING).skip(250)]
            if old_ids:
                self._db.autoplay_played_history.delete_many({"_id": {"$in": old_ids}})
            return True
        return await asyncio.to_thread(_record)

    # -- One-time, non-destructive import of existing SQLite / JSON data ------

    def _migrate_legacy_music_data_sync(self) -> Dict[str, int]:
        if self._db is None:
            return {}
        with self._legacy_migration_lock:
            if self._legacy_migration_done:
                return {}
            from contextlib import closing
            import json
            import sqlite3

            migrated: Dict[str, int] = {}
            migration_failed = False

            def migrate_table(path: str, table: str, marker: str, collection, transform) -> None:
                nonlocal migration_failed
                if not os.path.isfile(path) or self._db.migration_markers.find_one({"_id": marker}):
                    return
                try:
                    count = 0
                    with closing(sqlite3.connect(path)) as conn:
                        conn.row_factory = sqlite3.Row
                        exists = conn.execute(
                            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
                        ).fetchone()
                        if not exists:
                            return
                        cursor = conn.execute(f'SELECT * FROM "{table}"')
                        for row in cursor:
                            converted = transform(dict(row))
                            if converted is None:
                                continue
                            key, doc = converted
                            collection.update_one(key, {"$setOnInsert": doc}, upsert=True)
                            count += 1
                    self._db.migration_markers.insert_one({
                        "_id": marker, "completedAt": time.time(), "rows": count,
                    })
                    migrated[marker] = count
                except Exception as exc:
                    migration_failed = True
                    print(f"[MUSIC DB] Legacy import warning ({marker}): {exc}")

            def parse_json(value, fallback):
                try:
                    return json.loads(value) if value else fallback
                except Exception:
                    return fallback

            def voice247(row):
                # The old dashboard-only schema carried an explicit enabled flag;
                # don't revive its disabled rows during the one-time import.
                if row.get("enabled") is not None and not bool(row.get("enabled")):
                    return None
                if not row.get("channel_id"):
                    return None
                doc = {"guildId": str(row["guild_id"]), "channelId": str(row["channel_id"]),
                       "textChannelId": str(row["text_channel_id"]) if row.get("text_channel_id") else None}
                return {"guildId": doc["guildId"]}, doc

            def greeting(row):
                doc = {"memberId": str(row["member_id"]), "greetedDate": str(row["greeted_date"])}
                return {"memberId": doc["memberId"]}, doc

            def playback(row):
                gid = str(row["guild_id"])
                doc = {
                    "guildId": gid,
                    "channelId": str(row.get("channel_id")) if row.get("channel_id") else None,
                    "textChannelId": str(row.get("text_channel_id")) if row.get("text_channel_id") else None,
                    "currentSong": parse_json(row.get("current_song"), None),
                    "queue": parse_json(row.get("queue"), []),
                    "autoplay": bool(row.get("autoplay", 1)),
                    "autoplayLang": row.get("autoplay_lang") or "auto",
                    "autoplayMood": row.get("autoplay_mood") or "auto",
                    "isPlaying": bool(row.get("is_playing", 0)),
                    "updatedAt": int(row.get("updated_at") or 0),
                }
                return {"guildId": gid}, doc

            def playlist(row):
                uid = str(row["user_id"])
                name = str(row["playlist_name"] or "").strip().lower()
                doc = {
                    "userId": uid, "name": name, "displayName": str(row["playlist_name"] or name),
                    "tracks": parse_json(row.get("tracks_data"), []),
                    "createdAt": int(row.get("created_at") or time.time()),
                    "creatorName": row.get("creator_name") or "Unknown",
                    "isPrivate": bool(row.get("is_private", 0)),
                    "guildId": str(row.get("guild_id") or 0),
                    "updatedAt": int(row.get("created_at") or time.time()),
                }
                return {"userId": uid, "name": name}, doc

            def autoplay_playlist(row):
                gid = str(row["guild_id"])
                doc = {"guildId": gid, "playlistName": row.get("playlist_name"), "userId": str(row.get("user_id") or "")}
                return {"guildId": gid}, doc

            def autoplay_history(row):
                legacy_id = str(row.get("id", ""))
                gid = str(row["guild_id"])
                doc = {
                    "_id": f"legacy:{gid}:{legacy_id}", "legacyId": legacy_id, "guildId": gid,
                    "trackId": row.get("track_id"), "trackUrl": row.get("track_url"),
                    "titleNorm": row.get("title_norm"), "playedAt": int(row.get("played_at") or 0),
                }
                return {"_id": doc["_id"]}, doc

            def vc_status(row):
                cid = str(row["channel_id"])
                doc = {
                    "guildId": str(row["guild_id"]), "channelId": cid,
                    "statusText": row.get("status_text"), "emoji": row.get("emoji"),
                    "fullStatus": row.get("full_status") or "", "enforcement": bool(row.get("enforcement", 1)),
                    "createdAt": float(row.get("created_at") or time.time()),
                    "updatedAt": float(row.get("updated_at") or time.time()),
                    "updatedBy": int(row.get("updated_by") or 0),
                }
                return {"channelId": cid}, doc

            migrate_table("db/voice247.db", "voice247", "sqlite:voice247", self._db.voice247, voice247)
            migrate_table("db/voice247.db", "vc_daily_greetings", "sqlite:vc_daily_greetings", self._db.vc_daily_greetings, greeting)
            migrate_table("db/voice247.db", "music_playback_state", "sqlite:music_playback_state", self._db.music_playback_state, playback)
            migrate_table("db/playlists.db", "user_playlists", "sqlite:user_playlists", self._db.saved_playlists, playlist)
            migrate_table("db/playlists.db", "autoplay_playlists", "sqlite:autoplay_playlists", self._db.autoplay_playlists, autoplay_playlist)
            migrate_table("db/playlists.db", "autoplay_played_history", "sqlite:autoplay_played_history", self._db.autoplay_played_history, autoplay_history)
            migrate_table("db/vc_status.db", "vc_status_configs", "sqlite:vc_status_configs", self._db.vc_status_configs, vc_status)

            resume_path = "db/playback_resume_state.json"
            marker = "json:playback_resume_state"
            if os.path.isfile(resume_path) and not self._db.migration_markers.find_one({"_id": marker}):
                try:
                    with open(resume_path, "r", encoding="utf-8") as file:
                        payload = json.load(file)
                    guild_entries = payload.get("guilds", {}) if isinstance(payload, dict) else {}
                    for guild_id, entry in guild_entries.items():
                        self._db.music_playback_resume_state.update_one(
                            {"guildId": str(guild_id)},
                            {"$setOnInsert": {"guildId": str(guild_id), "entry": entry,
                                              "savedAt": payload.get("saved_at", time.time())}},
                            upsert=True,
                        )
                    self._db.migration_markers.insert_one({
                        "_id": marker, "completedAt": time.time(), "rows": len(guild_entries),
                    })
                    migrated[marker] = len(guild_entries)
                except Exception as exc:
                    migration_failed = True
                    print(f"[MUSIC DB] Legacy resume snapshot import warning: {exc}")

            self._legacy_migration_done = not migration_failed
            if migrated:
                print(f"[MUSIC DB] Imported existing local music/voice data into yunamusic: {migrated}")
            return migrated

    async def migrate_legacy_music_data(self) -> Dict[str, int]:
        return await asyncio.to_thread(self._migrate_legacy_music_data_sync)

    # =========================================================================
    # 7. SQLITE PLAYLIST COMPATIBILITY
    # =========================================================================

    def _migrate_sqlite_playlists_sync(self, sqlite_db_path: str = "db/playlists.db") -> int:
        """Compatibility wrapper that imports legacy playlist rows into saved_playlists."""
        if self._db is None or not os.path.exists(sqlite_db_path):
            return 0
        if os.path.normpath(sqlite_db_path) == os.path.normpath("db/playlists.db"):
            return self._migrate_legacy_music_data_sync().get("sqlite:user_playlists", 0)

        from contextlib import closing
        import sqlite3
        import json
        migrated = 0
        try:
            with closing(sqlite3.connect(sqlite_db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT user_id, playlist_name, tracks_data, created_at, creator_name, is_private, guild_id FROM user_playlists")
                for row in cursor:
                    row = dict(row)
                    try:
                        tracks = json.loads(row.get("tracks_data") or "[]")
                    except Exception:
                        tracks = []
                    if self._save_saved_playlist_sync(
                        user_id=int(row["user_id"]),
                        name=str(row["playlist_name"]),
                        tracks=tracks,
                        creator_name=str(row.get("creator_name") or "Unknown"),
                        is_private=int(row.get("is_private") or 0),
                        guild_id=int(row.get("guild_id") or 0),
                        created_at=int(row.get("created_at") or time.time()),
                    ):
                        migrated += 1
            print(f"[MUSIC DB] Migrated {migrated} playlists from SQLite to MongoDB Cloud.")
        except Exception as e:
            print(f"[MUSIC DB] SQLite migration warning: {e}")
        return migrated

    async def migrate_sqlite_playlists(self, sqlite_db_path: str = "db/playlists.db") -> int:
        return await asyncio.to_thread(self._migrate_sqlite_playlists_sync, sqlite_db_path)

# Global singleton
music_db = MusicDatabaseService.get_instance()
