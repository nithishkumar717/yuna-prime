import discord
from typing import Dict, Any, Optional

def format_duration(seconds: float | int) -> str:
    """Formats seconds into MM:SS or HH:MM:SS string."""
    if not seconds or seconds < 0:
        return "00:00"
    sec = int(seconds)
    hours, rem = divmod(sec, 3600)
    mins, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def create_progress_bar(current_sec: float | int, total_sec: float | int, length: int = 15) -> str:
    """Generates a static/dynamic text progress bar."""
    if not total_sec or total_sec <= 0:
        return f"00:00 ⚪{'─' * length} Live Stream"
    
    ratio = min(1.0, max(0.0, float(current_sec) / float(total_sec)))
    index = int(ratio * length)
    
    bar = ['─'] * length
    if 0 <= index < length:
        bar[index] = '⚪'
    
    cur_str = format_duration(current_sec)
    tot_str = format_duration(total_sec)
    return f"{cur_str} {''.join(bar)} {tot_str}"

def build_nowplaying_embed(song: Dict[str, Any], current_sec: float = 0, color: int = 0xD4AF37) -> discord.Embed:
    """Builds a clean Now Playing embed for the current song."""
    title = song.get("title", "Unknown Title")
    url = song.get("url", "https://discord.com")
    uploader = song.get("uploader", "Unknown Artist")
    duration = song.get("duration", 0)
    requested_by = song.get("requested_by", "Auto")
    thumbnail = song.get("thumbnail")

    prog_bar = create_progress_bar(current_sec, duration)

    embed = discord.Embed(
        title="Now Playing",
        description=f"**[{title}]({url})**\n\nArtist: `{uploader}`\nRequested By: {requested_by}\n\n{prog_bar}",
        color=color
    )
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    embed.set_footer(text="Yuna Music System")
    return embed

def build_queue_embed(queue_list: list, current_song: Optional[Dict[str, Any]] = None, page: int = 1, color: int = 0xD4AF37) -> discord.Embed:
    """Builds a formatted Queue embed."""
    embed = discord.Embed(
        title="Music Queue",
        color=color
    )
    
    desc_lines = []
    if current_song:
        desc_lines.append(f"**Now Playing:** [{current_song.get('title', 'Unknown')}]({current_song.get('url', '')})")
        desc_lines.append("")

    if not queue_list:
        desc_lines.append("*The queue is currently empty. Add songs using $play!*")
    else:
        start_idx = (page - 1) * 10
        end_idx = start_idx + 10
        for i, track in enumerate(queue_list[start_idx:end_idx], start=start_idx + 1):
            t_title = track.get('title', 'Unknown')
            t_url = track.get('url', '')
            desc_lines.append(f"`#{i}` [{t_title}]({t_url})")

    embed.description = "\n".join(desc_lines)
    embed.set_footer(text=f"Total Songs in Queue: {len(queue_list)} • Page {page}")
    return embed
