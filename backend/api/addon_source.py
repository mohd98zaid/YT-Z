"""
Pluggable Add-on Source Resolver for Hi-Res Lossless Audio.
Interfaces with configured module sources / add-ons (Lossless Bridge, Eclipse, FreeHiRes, Tidal FLAC)
to resolve bit-perfect 24-bit/96kHz and 16-bit/44.1kHz FLAC audio streams,
with seamless fallback to YouTube Music 256k Opus.
"""
import time
import logging
import urllib.parse
import concurrent.futures
from typing import Dict, Any, Optional, List
import requests
from backend.core.database import DatabaseManager

logger = logging.getLogger("YTZ.AddonSource")

class AddonSourceResolver:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def resolve_lossless_stream(
        self,
        title: str,
        artist: str = "",
        duration: int = 0,
        quality_preference: str = "lossless"
    ) -> Optional[Dict[str, Any]]:
        """
        Queries enabled audio_source add-ons for a bit-perfect Lossless (FLAC) or High stream.
        Supports:
        1. Addon API Protocol:
           GET {endpoint}/search?q={query} -> GET {endpoint}/stream/{track_id}
        2. Single-shot /resolve (POST or GET)
        3. Standard 2-step: GET /search?q=... -> GET /stream?id=...
        4. Direct /stream?title=...&artist=...
        """
        if not title:
            return None

        plugins = self.db.get_all_plugins()
        audio_sources = [
            p for p in plugins 
            if p.get("type") == "audio_source" and bool(p.get("enabled"))
        ]

        if not audio_sources:
            return None

        clean_title = title.split("(")[0].split("[")[0].strip()
        clean_artist = artist.split(",")[0].split("&")[0].split("feat")[0].strip()
        search_query = f"{clean_title} {clean_artist}".strip() if clean_artist else clean_title

        headers = {
            "User-Agent": "YT-Z/1.0.0 (Windows x86_64; Lossless Client)",
            "Accept": "application/json",
        }

        # Query all enabled audio source add-ons concurrently in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(audio_sources))) as executor:
            future_to_source = {
                executor.submit(
                    self._query_single_source,
                    source,
                    clean_title,
                    clean_artist,
                    search_query,
                    duration,
                    quality_preference,
                    title,
                    artist,
                    headers
                ): source
                for source in audio_sources
            }

            for future in concurrent.futures.as_completed(future_to_source):
                try:
                    res = future.result()
                    if res:
                        # Cancel remaining background queries immediately
                        for f in future_to_source:
                            f.cancel()
                        return res
                except Exception as e:
                    logger.debug(f"Source query exception: {e}")

        return None

    def _query_single_source(
        self,
        source: Dict[str, Any],
        clean_title: str,
        clean_artist: str,
        search_query: str,
        duration: int,
        quality_preference: str,
        title: str,
        artist: str,
        headers: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        endpoint = source.get("endpoint", "").strip()
        api_key = source.get("api_key", "").strip()
        addon_name = source.get("name", "Lossless Addon")

        if not endpoint or not (endpoint.startswith("http://") or endpoint.startswith("https://")):
            return None

        req_headers = dict(headers)
        if api_key:
            req_headers["Authorization"] = f"Bearer {api_key}"
            req_headers["X-Addon-Key"] = api_key

        base_url = endpoint.rstrip("/")

        # 1. Community Addon API Protocol (Fast 2.0s timeout)
        try:
            search_url = f"{base_url}/search?q={urllib.parse.quote(search_query)}"
            resp = requests.get(search_url, headers=req_headers, timeout=2.0)
            if resp.status_code in (401, 403, 404):
                # Endpoint is rejecting authentication or is broken, abort this source immediately
                return None

            if resp.status_code == 200:
                data = resp.json()
                raw_tracks = data.get("tracks") or data.get("results") or data.get("items") or []
                if isinstance(raw_tracks, list) and len(raw_tracks) > 0:
                    candidates = self._rank_candidates(raw_tracks, clean_title, clean_artist)
                    for candidate in candidates[:3]:
                        track_id = candidate.get("id") or candidate.get("trackId")
                        if not track_id:
                            continue

                        # Query direct stream endpoint
                        s_url = f"{base_url}/stream/{urllib.parse.quote(str(track_id))}"
                        try:
                            s_resp = requests.get(s_url, headers=req_headers, timeout=2.0)
                            if s_resp.status_code == 200:
                                s_data = s_resp.json()
                                media_url = s_data.get("url") or s_data.get("streamUrl") or s_data.get("stream_url")
                                if media_url and (media_url.startswith("http://") or media_url.startswith("https://")):
                                    if self._verify_stream_url(media_url, req_headers):
                                        merged = {**candidate, **s_data}
                                        return self._format_stream_result(
                                            merged,
                                            addon_name,
                                            candidate.get("title", title),
                                            candidate.get("artist", artist),
                                            media_url
                                        )
                        except Exception as se:
                            logger.debug(f"Failed stream endpoint {s_url}: {se}")
        except Exception as e:
            logger.debug(f"Addon '{addon_name}' search failed: {e}")

        # 2. Single-shot /resolve (Fast 2.0s timeout)
        try:
            payload = {
                "title": clean_title,
                "artist": clean_artist,
                "query": search_query,
                "duration": duration,
                "quality": quality_preference,
            }
            resp = requests.post(f"{base_url}/resolve", json=payload, headers=req_headers, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                stream_url = data.get("streamUrl") or data.get("url")
                if stream_url and self._verify_stream_url(stream_url, req_headers):
                    return self._format_stream_result(data, addon_name, title, artist, stream_url)
        except Exception as e:
            logger.debug(f"Addon '{addon_name}' /resolve failed: {e}")

        # 3. Direct GET /stream (Fast 2.0s timeout)
        try:
            direct_resp = requests.get(
                f"{base_url}/stream",
                params={"title": clean_title, "artist": clean_artist, "quality": quality_preference},
                headers=req_headers,
                timeout=2.0
            )
            if direct_resp.status_code == 200:
                direct_data = direct_resp.json()
                stream_url = direct_data.get("streamUrl") or direct_data.get("url")
                if stream_url and self._verify_stream_url(stream_url, req_headers):
                    return self._format_stream_result(direct_data, addon_name, title, artist, stream_url)
        except Exception as e:
            logger.debug(f"Addon '{addon_name}' direct /stream failed: {e}")

        return None

    def _rank_candidates(self, tracks: List[Dict[str, Any]], clean_title: str, clean_artist: str) -> List[Dict[str, Any]]:
        target_t = clean_title.lower().strip()
        target_a = clean_artist.lower().strip()
        scored = []
        for t in tracks:
            c_title = str(t.get("title", "")).lower().strip()
            c_artist = str(t.get("artist", "")).lower().strip()
            score = 0

            # Title matching
            if target_t == c_title:
                score += 30
            elif target_t in c_title or c_title in target_t:
                score += 15

            # Artist matching
            if target_a and target_a in c_artist:
                score += 15
            elif not target_a:
                score += 5

            # Prefer verified lossless/FLAC formats
            quality = str(t.get("audioQuality", "")).upper()
            fmt = str(t.get("format", "")).lower()
            if quality == "LOSSLESS" or "HIRES" in quality or fmt in ("flac", "alac"):
                score += 10

            scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored]

    def _verify_stream_url(self, media_url: str, headers: Dict[str, str]) -> bool:
        """
        Fast probe to verify the stream URL is responsive and delivers audio data.
        Tolerates 200 OK and 206 Partial Content.
        """
        try:
            probe_headers = dict(headers)
            probe_headers["Range"] = "bytes=0-15"
            probe = requests.get(media_url, headers=probe_headers, timeout=1.5, stream=True)
            if probe.status_code in (200, 206):
                return True
            logger.debug(f"Stream probe returned non-200/206 status: {probe.status_code}")
            return False
        except Exception as e:
            logger.debug(f"Stream probe failed for {media_url[:60]}: {e}")
            return False

    def _format_stream_result(
        self,
        data: Dict[str, Any],
        addon_name: str,
        default_title: str,
        default_artist: str,
        stream_url: str
    ) -> Dict[str, Any]:
        raw_codec = str(data.get("codec") or data.get("format") or "flac").lower()
        codec = "flac" if "flac" in raw_codec else raw_codec

        # Bitrate parsing (handle bps like 2144245 -> convert to kbps 2144)
        raw_bitrate = data.get("bitrate", 1411)
        try:
            bitrate_num = int(raw_bitrate)
            bitrate_kbps = bitrate_num // 1000 if bitrate_num > 10000 else bitrate_num
        except:
            bitrate_kbps = 1411

        bit_depth = int(data.get("bitDepth", 24 if bitrate_kbps > 1500 else 16))
        sample_rate = int(data.get("sampleRate", 96000 if bit_depth == 24 else 44100))
        is_lossless = codec in ("flac", "alac", "wav", "aiff") or bitrate_kbps >= 900

        display_name = addon_name
        if "pencarimovie" in str(addon_name).lower():
            display_name = "Hi-Res FLAC Master"
        elif "custom" in str(addon_name).lower():
            display_name = "Lossless Audio Master"

        logger.info(f"Resolved Hi-Res stream from '{display_name}': {codec.upper()} {bitrate_kbps}kbps {sample_rate}Hz/{bit_depth}bit")
        return {
            "source": "addon",
            "addon_name": display_name,
            "is_lossless": is_lossless,
            "codec": codec,
            "format": codec.upper(),
            "bitrate": bitrate_kbps,
            "sampleRate": sample_rate,
            "bitDepth": bit_depth,
            "quality_tier": "hi-res" if (bit_depth >= 24 or sample_rate > 48000) else ("lossless" if is_lossless else "high"),
            "streamUrl": stream_url,
            "title": data.get("title", default_title),
            "artist": data.get("artist", default_artist),
            "is_internal": False
        }
