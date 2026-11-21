"""
High-Speed YouTube Video Search Service for YT-Z.
Searches any video across all of YouTube using:
1. Fast YouTube Innertube API (<1.5s, no scraping overhead, all video categories).
2. YouTube Music API fallback.
3. Invidious / Piped mirror fallback.
4. yt-dlp flat extractor safety net.
Includes in-memory cache and direct URL resolution.
"""
import time
import logging
import re
from typing import List, Dict, Any, Optional
import requests
import yt_dlp

logger = logging.getLogger("YTZ.YouTubeSearch")

# In-memory search cache: { "query_str": (timestamp, results) }
_SEARCH_CACHE: Dict[str, tuple[float, List[Dict[str, Any]]]] = {}
CACHE_TTL = 600  # 10 minutes

class YouTubeSearchService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.ydl_opts = {
            "extract_flat": "in_playlist",
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 6,
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

    def _parse_duration_str(self, dur_str: str) -> int:
        if not dur_str:
            return 0
        parts = dur_str.strip().split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 1:
                return int(parts[0])
        except:
            pass
        return 0

    def _extract_video_id(self, text: str) -> Optional[str]:
        """Check if input text is a direct YouTube link or raw 11-char ID"""
        trimmed = text.strip()
        if re.match(r"^[a-zA-Z0-9_-]{11}$", trimmed):
            return trimmed
        m = re.search(r"(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/))([\w-]{11})", trimmed)
        if m:
            return m.group(1)
        return None

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search any video across all of YouTube with instant caching and multi-engine waterfall"""
        q = query.strip()
        if not q:
            return []

        # 0. Direct YouTube URL support: if user pasted a link, resolve it directly
        direct_id = self._extract_video_id(q)
        if direct_id:
            logger.info(f"Direct YouTube ID detected in search query: {direct_id}")
            return [{
                "id": direct_id,
                "videoId": direct_id,
                "title": f"YouTube Video ({direct_id})",
                "artist": "YouTube",
                "uploader": "YouTube",
                "duration": "",
                "durationSeconds": 0,
                "thumbnail": f"https://i.ytimg.com/vi/{direct_id}/hqdefault.jpg",
                "views": "",
                "url": f"https://www.youtube.com/watch?v={direct_id}",
                "resultType": "video",
            }]

        cache_key = f"{q.lower()}_{limit}"
        now = time.time()
        cached = _SEARCH_CACHE.get(cache_key)
        if cached and (now - cached[0]) < CACHE_TTL:
            return cached[1]

        # Tier 1: Fast YouTube Innertube Web Search API (<1.5s)
        results = self._search_innertube(q, limit)
        if results and len(results) > 0:
            _SEARCH_CACHE[cache_key] = (now, results)
            return results

        # Tier 2: YouTube Music API fallback
        results = self._search_ytmusic(q, limit)
        if results and len(results) > 0:
            _SEARCH_CACHE[cache_key] = (now, results)
            return results

        # Tier 3: Invidious Public Mirrors
        results = self._search_invidious(q, limit)
        if results and len(results) > 0:
            _SEARCH_CACHE[cache_key] = (now, results)
            return results

        # Tier 4: Standard yt-dlp flat search (safety net)
        results = self._search_ytdlp(q, limit)
        if results:
            _SEARCH_CACHE[cache_key] = (now, results)
        return results

    def _search_innertube(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Direct call to YouTube's internal Innertube search endpoint"""
        try:
            url = "https://www.youtube.com/youtubei/v1/search"
            payload = {
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20240101.00.00",
                        "hl": "en",
                        "gl": "US"
                    }
                },
                "query": query
            }
            resp = self.session.post(url, json=payload, timeout=4.5)
            if resp.status_code != 200:
                return []

            data = resp.json()
            items = []
            sections = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )

            for sec in sections:
                item_section = sec.get("itemSectionRenderer", {})
                for it in item_section.get("contents", []):
                    if "videoRenderer" in it:
                        vr = it["videoRenderer"]
                        vid = vr.get("videoId")
                        if not vid:
                            continue

                        title_runs = vr.get("title", {}).get("runs", [])
                        title = "".join(r.get("text", "") for r in title_runs) or "YouTube Video"

                        owner_runs = vr.get("ownerText", {}).get("runs", [])
                        uploader = "".join(r.get("text", "") for r in owner_runs) or "YouTube"

                        dur_str = vr.get("lengthText", {}).get("simpleText", "")
                        dur_sec = self._parse_duration_str(dur_str)

                        views_str = vr.get("viewCountText", {}).get("simpleText", "")
                        if not views_str:
                            short_views = vr.get("shortViewCountText", {}).get("simpleText", "")
                            views_str = short_views or ""

                        # High quality thumbnail
                        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                        thumbnails = vr.get("thumbnail", {}).get("thumbnails", [])
                        if thumbnails:
                            thumb = thumbnails[-1].get("url", thumb)

                        items.append({
                            "id": vid,
                            "videoId": vid,
                            "title": title,
                            "artist": uploader,
                            "uploader": uploader,
                            "duration": dur_str,
                            "durationSeconds": dur_sec,
                            "thumbnail": thumb,
                            "views": views_str,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "resultType": "video",
                        })

                        if len(items) >= limit:
                            break
                if len(items) >= limit:
                    break

            logger.info(f"Innertube search for '{query}' returned {len(items)} results")
            return items
        except Exception as e:
            logger.debug(f"Innertube search failed: {e}")
            return []

    def _search_ytmusic(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fallback to YouTube Music videos search"""
        try:
            from ytmusicapi import YTMusic
            yt = YTMusic()
            raw = yt.search(query, filter="videos")
            items = []
            for r in (raw or [])[:limit]:
                vid = r.get("videoId")
                if not vid:
                    continue
                artists = [a.get("name") for a in r.get("artists", []) if a.get("name")]
                uploader = ", ".join(artists) if artists else "YouTube Music"
                dur = r.get("duration", "")
                dur_sec = self._parse_duration_str(dur)
                views = r.get("views", "")

                thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                thumbs = r.get("thumbnails", [])
                if thumbs:
                    thumb = thumbs[-1].get("url", thumb)

                items.append({
                    "id": vid,
                    "videoId": vid,
                    "title": r.get("title", "YouTube Video"),
                    "artist": uploader,
                    "uploader": uploader,
                    "duration": dur,
                    "durationSeconds": dur_sec,
                    "thumbnail": thumb,
                    "views": views,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "resultType": "video",
                })
            return items
        except Exception as e:
            logger.debug(f"YTM search fallback failed: {e}")
            return []

    def _search_invidious(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fallback to fast public Invidious API instances"""
        instances = [
            "https://invidious.nerdvpn.de",
            "https://inv.tux.pizza",
            "https://invidious.private.coffee",
        ]
        for inst in instances:
            try:
                resp = self.session.get(
                    f"{inst}/api/v1/search",
                    params={"q": query, "type": "video"},
                    timeout=3.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = []
                    for item in data[:limit]:
                        vid = item.get("videoId")
                        if not vid:
                            continue
                        dur_sec = item.get("lengthSeconds", 0)
                        items.append({
                            "id": vid,
                            "videoId": vid,
                            "title": item.get("title", ""),
                            "artist": item.get("author", "YouTube"),
                            "uploader": item.get("author", "YouTube"),
                            "duration": self._format_duration(dur_sec),
                            "durationSeconds": dur_sec,
                            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                            "views": self._format_views(item.get("viewCount", 0)),
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "resultType": "video",
                        })
                    if items:
                        return items
            except:
                continue
        return []

    def _search_ytdlp(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Final safety net yt-dlp flat playlist search"""
        try:
            search_query = f"ytsearch{limit}:{query}"
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get("entries", []) if info else []
                items = []
                for e in entries:
                    if not e or not isinstance(e, dict):
                        continue
                    vid = e.get("id")
                    if not vid:
                        continue
                    duration_sec = e.get("duration") or 0
                    view_count = e.get("view_count")
                    thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                    if e.get("thumbnails"):
                        thumb = e["thumbnails"][-1].get("url", thumb)
                    items.append({
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
                return items
        except Exception as err:
            logger.error(f"yt-dlp search error for '{query}': {err}")
            return []
