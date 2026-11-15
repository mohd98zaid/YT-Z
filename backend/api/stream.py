"""
Audio Stream Resolver & Proxy for YT-Z.
Extracts high-bitrate Opus/AAC audio streams via yt-dlp with caching,
and fetches SponsorBlock skip segments for seamless music listening.
"""
import time
import logging
from typing import Dict, Any, Optional, List
import requests
import yt_dlp

logger = logging.getLogger("YTZ.Stream")

# In-memory stream cache: { video_id: { url: str, expires_at: float, info: dict } }
_STREAM_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 3600 * 3  # 3 hours (YouTube stream URLs are valid for ~6 hours)

class StreamResolver:
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'nocheckcertificate': True,
        }

    def resolve_audio(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Resolve highest quality audio stream for a given video ID"""
        now = time.time()
        cached = _STREAM_CACHE.get(video_id)
        if cached and cached.get("expires_at", 0) > now:
            return cached["data"]

        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                stream_url = info.get("url")
                # If manifest, pick best direct format
                formats = info.get("formats", [])
                audio_formats = [
                    f for f in formats 
                    if f.get("acodec") != "none" and (f.get("vcodec") == "none" or not f.get("vcodec"))
                ]
                
                # Sort audio formats by abr (average bit rate) descending
                if audio_formats:
                    best_audio = sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True)[0]
                    stream_url = best_audio.get("url") or stream_url
                    codec = best_audio.get("acodec", "opus")
                    bitrate = best_audio.get("abr", 160)
                else:
                    codec = "unknown"
                    bitrate = 128

                result = {
                    "videoId": video_id,
                    "streamUrl": stream_url,
                    "title": info.get("title", ""),
                    "artist": info.get("uploader", "") or info.get("artist", ""),
                    "duration": info.get("duration", 0),
                    "codec": codec,
                    "bitrate": bitrate,
                    "thumbnail": info.get("thumbnail", "")
                }

                _STREAM_CACHE[video_id] = {
                    "data": result,
                    "expires_at": now + CACHE_TTL
                }
                return result

        except Exception as e:
            logger.error(f"Error resolving stream for {video_id}: {e}")
            return None

    def get_sponsorblock_segments(self, video_id: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch SponsorBlock segments (intros, outros, music video dialog)"""
        if not categories:
            categories = ["sponsor", "intro", "outro", "music_offtopic"]
        try:
            cat_param = '["' + '","'.join(categories) + '"]'
            resp = requests.get(
                "https://sponsor.ajay.app/api/skipSegments",
                params={"videoID": video_id, "categories": cat_param},
                timeout=4
            )
            if resp.status_code == 200:
                data = resp.json()
                segments = []
                for s in data:
                    segment = s.get("segment", [])
                    if len(segment) >= 2:
                        segments.append({
                            "category": s.get("category"),
                            "start": segment[0],
                            "end": segment[1],
                            "actionType": s.get("actionType", "skip")
                        })
                return segments
            return []
        except Exception:
            return []
