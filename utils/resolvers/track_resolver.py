import re
import asyncio
import urllib.parse
import urllib.request
import json
import yt_dlp
from typing import List, Dict, Any, Optional
from utils.audio.ytm_engine import YouTubeMusicEngine
from utils.audio.spotify_engine import SpotifyEngine

import os

cookies_file = None
for fname in ["youtube_cookies.txt", "cookies.txt"]:
    if os.path.isfile(fname):
        cookies_file = fname
        break

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# YTDL options for fast metadata extraction
YTDL_SEARCH_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0',
    'skip_download': True,
    'http_headers': {
        'User-Agent': USER_AGENT,
        'Accept-Language': 'en-US,en;q=0.9',
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios'],
            'skip': ['translated_subs']
        }
    }
}

if cookies_file:
    YTDL_SEARCH_OPTIONS['cookiefile'] = cookies_file

def normalize_spotify_url(url: str) -> str:
    """Normalizes country-path Spotify URLs (e.g. /in-en/, /de/, /intl-es/, /intl-ja/) to open.spotify.com."""
    if not url:
        return url
    match = re.search(r'spotify\.com/(?:[a-zA-Z0-9\-_]+/)?(track|playlist|album|artist)/([a-zA-Z0-9]+)', url, re.IGNORECASE)
    if match:
        entity_type, entity_id = match.groups()
        return f"https://open.spotify.com/{entity_type}/{entity_id}"
    return url

def convert_spotify_to_yt_search(search_target: str, song_title: str = "", artist_name: str = "") -> str:
    """Converts a Spotify URL or track info to a YouTube Music search query to prevent DRM errors."""
    if 'spotify.com' in str(search_target).lower():
        query_text = f"{song_title} {artist_name}".strip()
        if not query_text:
            query_text = "spotify song"
        resolved_id = YouTubeMusicEngine.resolve_video_id_sync(
            query_text,
            expected_title=song_title,
            expected_artist=artist_name
        )
        if resolved_id:
            return f"https://www.youtube.com/watch?v={resolved_id}"
        return f"ytsearch5:{query_text} audio"
    return search_target

async def resolve_spotify_track(url: str) -> List[Dict[str, Any]]:
    """Resolves a single Spotify track URL into a searchable track dict."""
    norm_url = normalize_spotify_url(url)
    match = re.search(r'spotify\.com/track/([a-zA-Z0-9]+)', norm_url)
    if not match:
        return []
    
    track_id = match.group(1)
    title = f"Spotify Track {track_id}"
    artist = "Spotify"

    # Fetch track metadata via oembed
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(norm_url)}"
        req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
        def _fetch():
            with urllib.request.urlopen(req, timeout=4) as resp:
                return json.loads(resp.read().decode('utf-8'))
        data = await asyncio.to_thread(_fetch)
        if data and "title" in data:
            title = data.get("title", title)
            artist = data.get("author_name", artist)
    except Exception:
        pass

    # Search YouTube Music for the track
    from cogs.yuna_commands.music.validator import SongValidator
    search_q = f"{title} {artist}".strip()
    ytm_results = await YouTubeMusicEngine.search_tracks(search_q, limit=5)
    if not ytm_results and title:
        ytm_results = await YouTubeMusicEngine.search_tracks(title, limit=5)

    if ytm_results:
        best_match = SongValidator.select_best_music_candidate(ytm_results, target_title=title, target_artist=artist) or ytm_results[0]
        v_id = best_match.get('id')
        track_url = f"https://music.youtube.com/watch?v={v_id}" if v_id else (best_match.get('url') or search_q)
        return [{
            'title': title or best_match.get('title'),
            'search_query': track_url,
            'url': track_url,
            'yt_video_id': v_id,
            'thumbnail': best_match.get('thumbnail'),
            'duration': best_match.get('duration', 0),
            'uploader': artist or best_match.get('uploader'),
            'is_direct': False,
            'source': 'youtubemusic'
        }]

    # Fallback to targeted YouTube Music video ID resolution
    resolved_id = await asyncio.to_thread(YouTubeMusicEngine.resolve_video_id_sync, search_q, expected_title=title, expected_artist=artist)
    if resolved_id:
        track_url = f"https://music.youtube.com/watch?v={resolved_id}"
        return [{
            'title': title,
            'search_query': track_url,
            'url': track_url,
            'yt_video_id': resolved_id,
            'thumbnail': f"https://i.ytimg.com/vi/{resolved_id}/hqdefault.jpg",
            'duration': 0,
            'uploader': artist,
            'is_direct': False,
            'source': 'youtubemusic'
        }]

    return []

async def resolve_track_query(query: str) -> List[Dict[str, Any]]:
    """Universal query resolver handling URLs, Spotify, Apple Music, and search queries."""
    query = query.strip()
    if not query:
        return []

    # 1. Spotify URLs (Track, Playlist, Album, Artist, spotify.link)
    if 'spotify.com' in query.lower() or 'spotify.link' in query.lower():
        from cogs.yuna_commands.music import MusicResolver
        spotify_tracks = await MusicResolver.resolve_spotify(query)
        if spotify_tracks:
            return spotify_tracks
        return await resolve_spotify_track(query)

    # 2. Non-URL text queries: YTM Primary (Immediate on High-Confidence) + Parallel Spotify Authority
    if not (query.startswith("http://") or query.startswith("https://")):
        try:
            ytm_task = asyncio.create_task(YouTubeMusicEngine.search_tracks(query, limit=5))
            spotify_task = asyncio.create_task(SpotifyEngine.search_tracks(query, limit=5))

            # Await YTM first (ultra-fast IPv4 InnerTube connector ~200-400ms)
            ytm_results = await ytm_task
        except Exception as e:
            print(f"[TRACK RESOLVER YTM ERROR] {e}")
            ytm_results = []
            spotify_task = None

        # Check if YTM returned an immediate high-confidence studio hit (>= 50 score)
        from cogs.yuna_commands.music.validator import SongValidator
        best_ytm = None
        ytm_score = 0
        ytm_conf = "LOW"
        if ytm_results:
            for cand in ytm_results:
                score, conf = SongValidator.validate_and_score(cand, target_title=query)
                if score > ytm_score:
                    ytm_score = score
                    ytm_conf = conf
                    best_ytm = cand

        # Fast Path: If YTM has a HIGH-CONFIDENCE studio hit, proceed immediately!
        if best_ytm and ytm_score >= 50 and ytm_conf == "HIGH":
            ordered = [best_ytm] + [e for e in ytm_results if e != best_ytm]
            results = []
            for entry in ordered:
                v_id = entry.get('id')
                track_url = entry.get('url') or (f"https://music.youtube.com/watch?v={v_id}" if v_id else query)
                results.append({
                    'title': entry.get('title', 'Unknown Title'),
                    'search_query': track_url,
                    'url': track_url,
                    'yt_video_id': v_id,
                    'thumbnail': entry.get('thumbnail'),
                    'fallback_thumbnail': f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else None,
                    'duration': entry.get('duration', 0),
                    'uploader': entry.get('uploader') or entry.get('artist', 'Unknown Artist'),
                    'album_name': entry.get('album'),
                    'is_direct': False,
                    'source': 'youtubemusic'
                })
                if len(results) >= 5:
                    break

            # Trigger background Spotify enrichment without blocking playback
            if spotify_task and results:
                async def _enrich_bg(r_list, sp_t):
                    try:
                        sp_res = await asyncio.wait_for(sp_t, timeout=3.0)
                        if sp_res and isinstance(sp_res, list) and len(sp_res) > 0:
                            sp_can = sp_res[0]
                            r0 = r_list[0]
                            if sp_can.get('thumbnail') and 'scdn.co' not in str(r0.get('thumbnail', '')):
                                r0['fallback_thumbnail'] = r0.get('thumbnail')
                                r0['thumbnail'] = sp_can['thumbnail']
                            if sp_can.get('album_name'):
                                r0['album_name'] = sp_can['album_name']
                            if sp_can.get('spotify_id'):
                                r0['spotify_id'] = sp_can['spotify_id']
                            if sp_can.get('url'):
                                r0['spotify_url'] = sp_can['url']
                    except Exception:
                        pass
                asyncio.create_task(_enrich_bg(results, spotify_task))

            return results

        # Ambiguous / Lower-Confidence: Await Spotify for cross-source matching
        try:
            if spotify_task:
                try:
                    spotify_results = await asyncio.wait_for(spotify_task, timeout=2.5)
                except Exception:
                    spotify_results = []
            else:
                spotify_results = []

            canonical_identity = spotify_results[0] if (spotify_results and isinstance(spotify_results, list)) else None

            # Case A: Playable YTM available (cross-match with Spotify canonical identity)
            if ytm_results:
                target_title = (canonical_identity.get('song_name') or canonical_identity.get('title')) if canonical_identity else query
                target_artist = (canonical_identity.get('artists') or canonical_identity.get('uploader')) if canonical_identity else ""
                expected_duration = canonical_identity.get('duration', 0) if canonical_identity else 0

                # Score candidates with SongValidator
                best_match = SongValidator.select_best_music_candidate(
                    ytm_results,
                    target_title=target_title,
                    target_artist=target_artist,
                    expected_duration=expected_duration
                )
                if not best_match and expected_duration > 0:
                    best_match = SongValidator.select_best_music_candidate(
                        ytm_results,
                        target_title=target_title,
                        target_artist=target_artist,
                        expected_duration=0
                    )
                if not best_match:
                    best_match = best_ytm or SongValidator.select_best_music_candidate(ytm_results, target_title=query) or ytm_results[0]

                # Order candidates putting best_match first
                ordered = [best_match] + [e for e in ytm_results if e != best_match]
                results = []
                for entry in ordered:
                    v_id = entry.get('id')
                    track_url = entry.get('url') or (f"https://music.youtube.com/watch?v={v_id}" if v_id else query)
                    # Use canonical identity enrichment for the primary track
                    if entry == best_match and canonical_identity:
                        clean_title = canonical_identity.get('title') or entry.get('title', 'Unknown Title')
                        clean_artist = canonical_identity.get('artists') or entry.get('uploader') or entry.get('artist', 'Unknown Artist')
                        clean_thumb = canonical_identity.get('thumbnail') or entry.get('thumbnail')
                        dur = canonical_identity.get('duration') or entry.get('duration', 0)
                        album = canonical_identity.get('album_name') or entry.get('album')
                    else:
                        clean_title = entry.get('title', 'Unknown Title')
                        clean_artist = entry.get('uploader') or entry.get('artist', 'Unknown Artist')
                        clean_thumb = entry.get('thumbnail')
                        dur = entry.get('duration', 0)
                        album = entry.get('album')

                    track_dict = {
                        'title': clean_title,
                        'search_query': track_url,
                        'url': track_url,
                        'yt_video_id': v_id,
                        'thumbnail': clean_thumb,
                        'fallback_thumbnail': f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else None,
                        'duration': dur,
                        'uploader': clean_artist,
                        'album_name': album,
                        'is_direct': False,
                        'source': 'youtubemusic'
                    }
                    if entry == best_match and canonical_identity:
                        if canonical_identity.get('spotify_id'):
                            track_dict['spotify_id'] = canonical_identity['spotify_id']
                        if canonical_identity.get('url'):
                            track_dict['spotify_url'] = canonical_identity['url']
                    results.append(track_dict)
                    if len(results) >= 5:
                        break
                return results

            # Case B: Only Spotify succeeded
            if canonical_identity:
                clean_song_name = canonical_identity.get('song_name') or canonical_identity.get('title', query)
                clean_artists = canonical_identity.get('artists') or canonical_identity.get('uploader', '')
                clean_target = f"{clean_song_name} {clean_artists}".strip()
                chosen_duration = canonical_identity.get('duration', 0)

                resolved_id = await asyncio.to_thread(
                    YouTubeMusicEngine.resolve_video_id_sync,
                    clean_target,
                    expected_title=clean_song_name,
                    expected_artist=clean_artists,
                    expected_duration=chosen_duration
                )
                if resolved_id:
                    track_url = f"https://music.youtube.com/watch?v={resolved_id}"
                    return [{
                        'title': canonical_identity.get('title', 'Unknown Title'),
                        'search_query': track_url,
                        'url': track_url,
                        'yt_video_id': resolved_id,
                        'thumbnail': canonical_identity.get('thumbnail'),
                        'fallback_thumbnail': f"https://i.ytimg.com/vi/{resolved_id}/hqdefault.jpg",
                        'duration': chosen_duration,
                        'uploader': clean_artists or 'Spotify Artist',
                        'album_name': canonical_identity.get('album_name'),
                        'spotify_id': canonical_identity.get('spotify_id'),
                        'spotify_url': canonical_identity.get('url'),
                        'is_direct': False,
                        'source': 'youtubemusic'
                    }]
        except Exception as e:
            print(f"[TRACK RESOLVER PARALLEL YTM/SPOTIFY ERROR] {e}")

        # Case C: Emergency Fallback: Standard YouTube flat search with strict gate (>= 40 score)
        try:
            def _extract_yt():
                with yt_dlp.YoutubeDL(YTDL_SEARCH_OPTIONS) as ydl:
                    return ydl.extract_info(f"ytsearch5:{query} audio", download=False)

            info = await asyncio.to_thread(_extract_yt)
            if not info or 'entries' not in info or not info['entries']:
                def _extract_yt_raw():
                    with yt_dlp.YoutubeDL(YTDL_SEARCH_OPTIONS) as ydl:
                        return ydl.extract_info(f"ytsearch5:{query}", download=False)
                info = await asyncio.to_thread(_extract_yt_raw)

            if info and 'entries' in info and info['entries']:
                entries = [e for e in info['entries'] if e and e.get('title')]
                validated_entries = []
                for e in entries:
                    if not e.get('source'):
                        e['source'] = 'youtube'
                    score, conf = SongValidator.validate_and_score(e, target_title=query)
                    if conf in ["HIGH", "MEDIUM"] and score >= 40:
                        validated_entries.append((score, e))

                if validated_entries:
                    validated_entries.sort(key=lambda x: x[0], reverse=True)
                    results = []
                    for score, entry in validated_entries:
                        v_id = entry.get('id')
                        track_url = f"https://music.youtube.com/watch?v={v_id}" if v_id else (entry.get('webpage_url') or entry.get('url') or query)
                        thumb = entry.get('thumbnail')
                        if not thumb and entry.get('thumbnails') and isinstance(entry['thumbnails'], list) and len(entry['thumbnails']) > 0:
                            thumb = entry['thumbnails'][-1].get('url')
                        if not thumb and v_id:
                            thumb = f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg"

                        results.append({
                            'title': entry.get('title') or 'Unknown Title',
                            'search_query': track_url,
                            'url': track_url,
                            'yt_video_id': v_id,
                            'thumbnail': thumb,
                            'fallback_thumbnail': f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg" if v_id else None,
                            'duration': entry.get('duration') or 0,
                            'uploader': entry.get('uploader') or entry.get('channel') or 'YouTube Uploader',
                            'is_direct': False,
                            'source': 'youtubemusic' if v_id else 'youtube'
                        })
                        if len(results) >= 5:
                            break
                    if results:
                        return results
                else:
                    print(f"[TRACK RESOLVER EMERGENCY] Rejected YouTube candidates for '{query}' due to score < 40")
        except Exception as e:
            print(f"[TRACK RESOLVER YT EMERGENCY FALLBACK ERROR] {e}")

        return []

    # 3. Direct URL via yt-dlp
    search_target = query

    def _extract():
        with yt_dlp.YoutubeDL(YTDL_SEARCH_OPTIONS) as ydl:
            return ydl.extract_info(search_target, download=False)

    try:
        info = await asyncio.to_thread(_extract)
        if not info:
            return []

        results = []
        entries = info.get('entries', [info]) if 'entries' in info else [info]
        for entry in entries:
            if not entry:
                continue
            title = entry.get('title') or 'Unknown Title'
            web_url = entry.get('webpage_url') or entry.get('url') or query
            duration = entry.get('duration') or 0
            uploader = entry.get('uploader') or entry.get('channel') or 'Unknown Uploader'
            thumb = entry.get('thumbnail')
            if not thumb and entry.get('thumbnails') and isinstance(entry['thumbnails'], list) and len(entry['thumbnails']) > 0:
                thumb = entry['thumbnails'][-1].get('url')
            if not thumb and entry.get('id'):
                thumb = f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg"

            wu = web_url.lower()
            if 'spotify.com' in wu:
                s_platform = 'spotify'
            elif 'music.youtube.com' in wu:
                s_platform = 'youtubemusic'
            elif 'jiosaavn.com' in wu or 'saavn.com' in wu:
                s_platform = 'jiosaavn'
            elif 'apple.com' in wu:
                s_platform = 'applemusic'
            elif 'soundcloud.com' in wu:
                s_platform = 'soundcloud'
            else:
                s_platform = 'youtube'

            results.append({
                'title': title,
                'search_query': web_url if web_url.startswith("http") else search_target,
                'url': web_url,
                'thumbnail': thumb,
                'duration': duration,
                'uploader': uploader,
                'is_direct': False,
                'source': s_platform
            })
            if len(results) >= 5:
                break
        for res in results:
            try:
                await SpotifyEngine.enrich_track_metadata(res)
            except Exception:
                pass
        return results
    except Exception as e:
        # Fallback for plain text search
        return [{
            'title': query,
            'search_query': f"ytsearch5:{query}",
            'url': query,
            'thumbnail': None,
            'duration': 0,
            'uploader': 'Search',
            'is_direct': False
        }]
