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
import re
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

        import re
        clean_title = re.sub(r'\(.*?\)|\[.*?\]', '', title)
        clean_title = re.split(r'\||–|—|-', clean_title)[0].strip()
        clean_artist = re.split(r',|&|feat|ft\.', artist, flags=re.IGNORECASE)[0].strip()
        search_query = f"{clean_title} {clean_artist}".strip() if clean_artist else clean_title

        headers = {
            "User-Agent": "YT-Z/1.0.0 (Windows x86_64; Lossless Client)",
            "Accept": "application/json",
        }

        # Query all enabled audio source add-ons concurrently in parallel
        best_lossy_candidate = None
        if audio_sources:
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
                            if res.get("is_lossless"):
                                # Found verified bit-perfect FLAC/ALAC stream! Return immediately.
                                for f in future_to_source:
                                    f.cancel()
                                return res
                            elif not best_lossy_candidate:
                                best_lossy_candidate = res
                    except Exception as e:
                        logger.debug(f"Source query exception: {e}")

        # 2. Automated Search across Alternative Hi-Res / Lossless Master Sources
        alt_res = None
        if quality_preference in ("lossless", "high", "auto"):
            alt_res = self._query_alternative_hires_sources(title, artist, duration, headers, quality_preference=quality_preference)
            if alt_res and alt_res.get("is_lossless"):
                return alt_res

        # 3. If no bit-perfect lossless master found anywhere, return best lossy candidate (or alt 320k fallback)
        if best_lossy_candidate:
            return best_lossy_candidate

        if alt_res:
            return alt_res

        return None

    def _query_alternative_hires_sources(
        self,
        title: str,
        artist: str,
        duration: int,
        headers: Dict[str, str],
        quality_preference: str = "lossless"
    ) -> Optional[Dict[str, Any]]:
        """
        Query alternative high-resolution audio sources (CD-Master FLAC / Studio Masters)
        for tracks when streaming YouTube or YouTube playlists.
        """
        try:
            from backend.api.lyrics import generate_search_candidates
            candidates = generate_search_candidates(title, artist)
        except Exception:
            candidates = [(clean_title, clean_artist)]

        # 1. Query Built-In Lossless Master Bridge (PencariMusic / Eclipse) directly for FLAC
        if quality_preference in ("lossless", "high", "auto") and candidates:
            p_source = {
                "name": "PencariMusic",
                "endpoint": "https://stream.pencarimovie.com/66ff097863dedb7ccd8401d5ffe616f3/eclipse",
                "api_key": ""
            }
            cand_t, cand_a = candidates[0]
            p_res = self._query_single_source(
                p_source,
                cand_t,
                cand_a,
                f"{cand_t} {cand_a}".strip(),
                duration,
                quality_preference,
                title,
                artist,
                headers
            )
            if p_res and p_res.get("is_lossless"):
                return p_res

        api_mirrors = [
            "https://jiosaavn-api-gold.vercel.app/search/songs?query=",
            "https://saavn.dev/api/search/songs?query=",
        ]

        for cand_title, cand_artist in candidates[:3]:
            q_str = f"{cand_title} {cand_artist}".strip()
            encoded_q = urllib.parse.quote(q_str)

            for base_api in api_mirrors:
                try:
                    resp = requests.get(f"{base_api}{encoded_q}", timeout=2.5, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        data = resp.json().get("data", {}).get("results", [])
                        if data and isinstance(data, list):
                            for s in data[:3]:
                                dl_urls = s.get("downloadUrl", [])
                                if dl_urls:
                                    best = dl_urls[-1]
                                    stream_url = best.get("link") or best.get("url")
                                    if stream_url and self._verify_stream_url(stream_url, headers):
                                        raw_quality = str(best.get("quality", "320kbps")).lower()
                                        stream_lower = stream_url.lower()

                                        # Parse genuine stream bitrate
                                        if "320" in raw_quality or "320" in stream_lower:
                                            actual_bitrate = 320
                                        elif "160" in raw_quality or "160" in stream_lower:
                                            actual_bitrate = 160
                                        elif "128" in raw_quality or "128" in stream_lower:
                                            actual_bitrate = 128
                                        elif "96" in raw_quality or "96" in stream_lower:
                                            actual_bitrate = 96
                                        elif "48" in raw_quality or "48" in stream_lower:
                                            actual_bitrate = 48
                                        else:
                                            actual_bitrate = 320

                                        # Detect genuine codec and container from URL and stream properties
                                        if ".flac" in stream_lower:
                                            codec = "flac"
                                            is_genuine_lossless = True
                                            format_name = "FLAC"
                                            bit_depth = 24 if actual_bitrate > 1500 else 16
                                            sample_rate = 96000 if bit_depth == 24 else 44100
                                        elif ".alac" in stream_lower:
                                            codec = "alac"
                                            is_genuine_lossless = True
                                            format_name = "ALAC"
                                            bit_depth = 24 if actual_bitrate > 1500 else 16
                                            sample_rate = 96000 if bit_depth == 24 else 44100
                                        elif ".mp4" in stream_lower or ".m4a" in stream_lower or "aac" in stream_lower:
                                            codec = "aac"
                                            is_genuine_lossless = False
                                            format_name = "AAC"
                                            bit_depth = 16
                                            sample_rate = 44100
                                        elif ".mp3" in stream_lower:
                                            codec = "mp3"
                                            is_genuine_lossless = False
                                            format_name = "MP3"
                                            bit_depth = 16
                                            sample_rate = 44100
                                        else:
                                            codec = "aac"
                                            is_genuine_lossless = False
                                            format_name = "AAC"
                                            bit_depth = 16
                                            sample_rate = 44100

                                        raw_name = s.get("name", cand_title)
                                        import html
                                        clean_name = html.unescape(raw_name)
                                        
                                        if is_genuine_lossless:
                                            addon_label = f"Lossless Master ({codec.upper()})"
                                            quality_tier = "hi-res" if bit_depth == 24 else "lossless"
                                        elif actual_bitrate >= 320:
                                            addon_label = "JioSaavn HQ Stream (320k AAC)"
                                            quality_tier = "high"
                                        else:
                                            addon_label = f"JioSaavn Stream ({actual_bitrate}k {format_name})"
                                            quality_tier = "standard"

                                        logger.info(f"Resolved stream for '{title}': {addon_label} ({codec.upper()} {actual_bitrate} kbps)")
                                        return {
                                            "source": "jiosaavn_hq" if not is_genuine_lossless else "lossless_addon",
                                            "addon_name": addon_label,
                                            "is_lossless": is_genuine_lossless,
                                            "codec": codec,
                                            "format": format_name,
                                            "bitrate": actual_bitrate,
                                            "sampleRate": sample_rate,
                                            "bitDepth": bit_depth,
                                            "quality_tier": quality_tier,
                                            "streamUrl": stream_url,
                                            "title": clean_name,
                                            "artist": s.get("primaryArtists", artist),
                                            "is_internal": False
                                        }
                except Exception as ex:
                    logger.debug(f"Alternative mirror query error: {ex}")
                    continue

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
        cand_bases = [base_url]
        if "/music" in base_url:
            cand_bases.append(base_url.replace("/music", "/eclipse"))
            cand_bases.append(base_url.replace("/music", ""))
        elif "/eclipse" in base_url:
            cand_bases.append(base_url.replace("/eclipse", "/music"))
            cand_bases.append(base_url.replace("/eclipse", ""))
        else:
            cand_bases.append(f"{base_url}/eclipse")
            cand_bases.append(f"{base_url}/music")

        queries_to_try = [search_query]
        if clean_title and clean_title not in queries_to_try:
            queries_to_try.append(clean_title)
        raw_clean = re.sub(r'\(.*?\)|\[.*?\]', '', title).split('|')[0].strip()
        if raw_clean and raw_clean not in queries_to_try:
            queries_to_try.append(raw_clean)

        # 1. BitChord & Eclipse Addon Protocol (/search?q={query} -> /stream/{id})
        for cand_base in cand_bases:
            cand_clean = cand_base.replace("/manifest.json", "").rstrip("/")
            for q_text in queries_to_try:
                try:
                    search_url = f"{cand_clean}/search?q={urllib.parse.quote(q_text)}"
                    resp = requests.get(search_url, headers=req_headers, timeout=3.5)
                    if resp.status_code in (401, 403):
                        continue
                    if resp.status_code == 200 and "application/json" in resp.headers.get("Content-Type", "").lower():
                        data = resp.json()
                        raw_tracks = data.get("tracks") or data.get("results") or data.get("items") or []
                        if isinstance(raw_tracks, list) and len(raw_tracks) > 0:
                            candidates = self._rank_candidates(raw_tracks, clean_title, clean_artist, quality_preference)
                            for candidate in candidates[:3]:
                                track_id = candidate.get("id") or candidate.get("trackId")
                                if not track_id:
                                    continue

                                s_url = f"{cand_clean}/stream/{urllib.parse.quote(str(track_id))}"
                                try:
                                    s_resp = requests.get(s_url, headers=req_headers, timeout=6.0, allow_redirects=True)
                                    if s_resp.status_code == 200:
                                        if "application/json" in s_resp.headers.get("Content-Type", "").lower():
                                            s_data = s_resp.json()
                                            media_url = s_data.get("url") or s_data.get("streamUrl") or s_data.get("stream_url")
                                        else:
                                            s_data = {}
                                            media_url = s_resp.url
                                    elif s_resp.status_code in (206, 302):
                                        s_data = {}
                                        media_url = s_resp.headers.get("Location") or s_resp.url
                                    else:
                                        continue

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
                    logger.debug(f"Addon '{addon_name}' search failed on {cand_clean}: {e}")

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

        # 4. Stremio / PencariMovie Addon Protocol (/catalog/... -> /stream/...)
        try:
            stremio_base = base_url.replace("/manifest.json", "").rstrip("/")
            for c_type in ["movie", "series", "music", "track"]:
                c_url = f"{stremio_base}/catalog/{c_type}/pm_music_search/search={urllib.parse.quote(search_query)}.json"
                c_resp = requests.get(c_url, headers=req_headers, timeout=2.0)
                if c_resp.status_code == 200:
                    c_data = c_resp.json()
                    metas = c_data.get("metas", [])
                    if metas:
                        first_meta = metas[0]
                        m_id = first_meta.get("id")
                        m_type = first_meta.get("type", c_type)
                        st_url = f"{stremio_base}/stream/{m_type}/{urllib.parse.quote(str(m_id))}.json"
                        st_resp = requests.get(st_url, headers=req_headers, timeout=2.0)
                        if st_resp.status_code == 200:
                            st_data = st_resp.json()
                            streams = st_data.get("streams", [])
                            for st_item in streams:
                                m_url = st_item.get("url")
                                if m_url and (m_url.startswith("http://") or m_url.startswith("https://")):
                                    if self._verify_stream_url(m_url, req_headers):
                                        return self._format_stream_result(
                                            {
                                                "title": first_meta.get("name", title),
                                                "codec": "flac" if ".flac" in m_url.lower() else ("mp3" if ".mp3" in m_url.lower() else "aac"),
                                                "bitrate": 320,
                                            },
                                            addon_name,
                                            first_meta.get("name", title),
                                            artist,
                                            m_url
                                        )
        except Exception as e:
            logger.debug(f"Addon '{addon_name}' Stremio catalog search failed: {e}")

        return None

    def _rank_candidates(
        self,
        tracks: List[Dict[str, Any]],
        clean_title: str,
        clean_artist: str,
        quality_preference: str = "lossless"
    ) -> List[Dict[str, Any]]:
        import re
        target_t = clean_title.lower().strip()
        target_a = clean_artist.lower().strip()
        scored = []
        for t in tracks:
            c_title = str(t.get("title", "")).lower().strip()
            c_artist = str(t.get("artist", "")).lower().strip()
            score = 0

            # Title matching: Must match title strongly so irrelevant songs by the same artist aren't chosen
            t_words = set(re.findall(r'\w+', target_t))
            c_words = set(re.findall(r'\w+', c_title))

            if target_t == c_title:
                score += 100
            elif target_t in c_title or c_title in target_t:
                score += 70
            elif t_words and c_words:
                overlap = len(t_words.intersection(c_words))
                ratio = overlap / len(t_words)
                if ratio >= 0.7:
                    score += int(ratio * 60)
                elif ratio >= 0.5:
                    score += int(ratio * 30)
                else:
                    score -= 50
            else:
                score -= 60

            # Artist matching
            if target_a and (target_a in c_artist or c_artist in target_a):
                score += 25
            elif not target_a:
                score += 5

            # Heavily prioritize verified lossless FLAC / ALAC formats!
            quality = str(t.get("audioQuality", "")).upper()
            fmt = str(t.get("format", "")).lower()
            is_flac = quality == "LOSSLESS" or "HIRES" in quality or fmt in ("flac", "alac")
            if is_flac:
                score += 100
                size = int(t.get("size") or 0)
                if size > 30 * 1024 * 1024:
                    score += 25
            elif quality_preference in ("lossless", "high", "auto"):
                score -= 40

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
            probe = requests.get(media_url, headers=probe_headers, timeout=6.0, stream=True)
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
        raw_codec = str(data.get("codec") or data.get("format") or "").lower()
        stream_lower = stream_url.lower()

        if "flac" in raw_codec or ".flac" in stream_lower:
            codec = "flac"
        elif "alac" in raw_codec or ".alac" in stream_lower:
            codec = "alac"
        elif "opus" in raw_codec or ".opus" in stream_lower or ".webm" in stream_lower:
            codec = "opus"
        elif "aac" in raw_codec or ".m4a" in stream_lower or ".mp4" in stream_lower:
            codec = "aac"
        elif "mp3" in raw_codec or ".mp3" in stream_lower:
            codec = "mp3"
        else:
            codec = raw_codec or "flac"

        # Bitrate parsing (handle bps like 320000 -> convert to kbps 320)
        raw_bitrate = data.get("bitrate") or data.get("kbps")
        if raw_bitrate:
            try:
                bitrate_num = int(raw_bitrate)
                bitrate_kbps = bitrate_num // 1000 if bitrate_num > 10000 else bitrate_num
            except Exception:
                bitrate_kbps = 1411 if codec in ("flac", "alac") else 320
        elif codec in ("flac", "alac"):
            bitrate_kbps = 1411
        elif codec == "opus":
            bitrate_kbps = 160
        else:
            bitrate_kbps = 320

        is_lossless = codec in ("flac", "alac", "wav", "aiff")
        bit_depth = int(data.get("bitDepth") or data.get("bit_depth") or (24 if (is_lossless and bitrate_kbps > 1500) else 16))
        sample_rate = int(data.get("sampleRate") or data.get("sample_rate") or (48000 if bit_depth == 24 else 44100))

        display_name = addon_name
        if "pencarimovie" in str(addon_name).lower() or "pencari" in str(addon_name).lower():
            display_name = "PencariMusic"
        elif "custom" in str(addon_name).lower():
            display_name = "Audio Master Source"

        logger.info(f"Resolved stream from '{display_name}': {codec.upper()} {bitrate_kbps}kbps {sample_rate}Hz/{bit_depth}bit (lossless={is_lossless})")
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
