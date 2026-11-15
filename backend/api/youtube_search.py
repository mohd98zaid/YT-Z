"""
Separate YouTube Video Search Service for YT-Z.
Performs general YouTube video search across all of YouTube (not limited to YouTube Music).
Uses yt_dlp flat playlist extraction for fast, accurate results without downloading.
"""
import logging
from typing import List, Dict, Any
import yt_dlp

logger = logging.getLogger("YTZ.YouTubeSearch")

class YouTubeSearchService:
    def __init__(self):
        self.ydl_opts = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 8,
        }

    def _format_duration(self, seconds: int = 0) -> str:
        if not seconds or seconds <= 0:
            return ""
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"

    def _format_views(self, views: int = 0) -> str:
        if not views:
            return ""
        if views >= 1_000_000_000:
            return f"{views / 1_000_000_000:.1f}B views"
        if views >= 1_000_000:
            return f"{views / 1_000_000:.1f}M views"
        if views >= 1_000:
            return f"{views / 1_000:.1f}K views"
        return f"{views} views"

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search any video across all of YouTube"""
        query = query.strip()
        if not query:
            return []

        search_query = f"ytsearch{limit}:{query}"
        results = []

        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get("entries", []) if info else []

                for e in entries:
                    if not e or not isinstance(e, dict):
                        continue

                    vid = e.get("id")
                    if not vid:
                        continue

                    duration_sec = e.get("duration") or 0
                    view_count = e.get("view_count")

                    # Best thumbnail
                    thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                    if e.get("thumbnails"):
                        thumb = e["thumbnails"][-1].get("url", thumb)

                    results.append({
                        "id": vid,
                        "videoId": vid,
                        "title": e.get("title", "YouTube Video"),
                        "artist": e.get("uploader") or e.get("channel") or "YouTube",
                        "uploader": e.get("uploader") or e.get("channel") or "YouTube",
                        "duration": self._format_duration(duration_sec),
                        "durationSeconds": duration_sec,
                        "thumbnail": thumb,
                        "views": self._format_views(view_count),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "resultType": "video",
                    })

            return results
        except Exception as err:
            logger.error(f"Error during YouTube video search for '{query}': {err}")
            return []
