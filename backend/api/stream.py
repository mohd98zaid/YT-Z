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
from backend.api.addon_source import AddonSourceResolver

logger = logging.getLogger("YTZ.Stream")

# In-memory stream cache: { video_id: { url: str, expires_at: float, info: dict } }
_STREAM_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 3600 * 3  # 3 hours (YouTube stream URLs are valid for ~6 hours)

class StreamResolver:
    def __init__(self, addon_resolver: Optional[AddonSourceResolver] = None):
        self.addon_resolver = addon_resolver
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'nocheckcertificate': True,
        }

    def resolve_audio(
        self,
        video_id: str,
        title: str = "",
        artist: str = "",
        duration: int = 0,
        quality: str = "auto"
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve highest quality audio stream for a track.
        Prioritizes configured Hi-Res Lossless (FLAC/ALAC) add-ons,
        falling back gracefully to YouTube Music Opus.
        """
        now = time.time()
        cache_key = f"{video_id}_{quality}"
        cached = _STREAM_CACHE.get(cache_key)
        if cached and cached.get("expires_at", 0) > now:
            return cached["data"]

        # 1. Check enabled Lossless Module Source Add-ons
        if self.addon_resolver and quality in ("lossless", "high", "auto") and title:
            addon_stream = self.addon_resolver.resolve_lossless_stream(
                title=title,
                artist=artist,
                duration=duration,
                quality_preference=quality
            )
            if addon_stream:
                stream_url = addon_stream.get("streamUrl", "")
                if stream_url.startswith("http://") or stream_url.startswith("https://"):
                    result = {
                        "videoId": video_id,
                        "streamUrl": stream_url,
                        "title": addon_stream.get("title", title),
                        "artist": addon_stream.get("artist", artist),
                        "duration": duration,
                        "codec": addon_stream["codec"],
                        "format": addon_stream["format"],
                        "bitrate": addon_stream["bitrate"],
                        "sampleRate": addon_stream.get("sampleRate", 44100),
                        "bitDepth": addon_stream.get("bitDepth", 16),
                        "isLossless": addon_stream.get("is_lossless", True),
                        "qualityTier": addon_stream.get("quality_tier", "lossless"),
                        "source": "addon",
                        "addonName": addon_stream.get("addon_name", "Hi-Res FLAC Addon"),
                    }
                    _STREAM_CACHE[cache_key] = {
                        "data": result,
                        "expires_at": now + CACHE_TTL
                    }
                    return result

        # 2. Fallback to YouTube Music Stream
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                stream_url = info.get("url")
                formats = info.get("formats", [])
                audio_formats = [
                    f for f in formats 
                    if f.get("acodec") != "none" and (f.get("vcodec") == "none" or not f.get("vcodec"))
                ]
                
                if audio_formats:
                    best_audio = sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True)[0]
                    stream_url = best_audio.get("url") or stream_url
                    codec = best_audio.get("acodec", "opus")
                    bitrate = best_audio.get("abr", 160)
                else:
                    codec = "opus"
                    bitrate = 128

                result = {
                    "videoId": video_id,
                    "streamUrl": stream_url,
                    "title": info.get("title", ""),
                    "artist": info.get("uploader", "") or info.get("artist", ""),
                    "duration": info.get("duration", 0),
                    "codec": codec,
                    "format": "OPUS",
                    "bitrate": bitrate,
                    "sampleRate": 48000,
                    "bitDepth": 16,
                    "isLossless": False,
                    "qualityTier": "high",
                    "source": "youtube",
                    "thumbnail": info.get("thumbnail", "")
                }

                _STREAM_CACHE[cache_key] = {
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
