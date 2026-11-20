"""
Multi-provider Lyrics Engine for YT-Z.
Supports LRCLIB, lrc.red (syllable TTML), KuGou, and Genius.
Parses syllable/word-synced, line-synced LRC, and plain lyrics.
"""
import re
import json
import logging
from typing import Dict, Any, List, Optional
import xml.etree.ElementTree as ET
import requests
from backend.core.database import DatabaseManager

logger = logging.getLogger("YTZ.Lyrics")

# Regex cleaners for song titles
STRIP_PATTERNS = [
    r"\(official\s+video\)",
    r"\(official\s+music\s+video\)",
    r"\(official\s+audio\)",
    r"\(visualizer\)",
    r"\(lyric\s+video\)",
    r"\(lyrics\)",
    r"\(full\s+song\)",
    r"\(audio\)",
    r"\(video\)",
    r"\[official\s+video\]",
    r"\[official\s+music\s+video\]",
    r"\[official\s+audio\]",
    r"\[lyrics\]",
    r"\[full\s+song\]",
    r"\[hd\]",
    r"\[4k\]",
    r"\bft\.?.*$",
    r"\bfeat\.?.*$",
]

KNOWN_RECORD_LABELS = {
    "t-series", "tseries", "zee music company", "sony music india", "yrf",
    "tips official", "speed records", "saregama", "saregama music", "wave music",
    "aditya music", "lahari music", "geet mp3", "vevo", "universal music",
    "warner music", "def jam", "atlantic records", "columbia records", "interscope"
}

def clean_title(title: str) -> str:
    cleaned = title
    for p in STRIP_PATTERNS:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("&", "and").strip()
    if " - " in cleaned:
        cleaned = cleaned.split(" - ", 1)[1]
    return cleaned.strip()

def clean_artist(artist: str) -> str:
    cleaned = artist.strip()
    if cleaned.lower().endswith(" - topic"):
        cleaned = cleaned[:-8].strip()
    for sep in [",", "&", "feat.", "ft.", "/"]:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0]
    return cleaned.strip()

def generate_search_candidates(title: str, artist: str) -> List[tuple]:
    """
    Generate ordered candidate pairs of (track_name, artist_name) to maximize
    matches across YouTube's movie titles, record labels, and collaborative tags.
    """
    candidates = []

    # Clean artist and detect if artist is a record label
    raw_artist = artist.strip()
    if raw_artist.lower().endswith(" - topic"):
        raw_artist = raw_artist[:-8].strip()
    is_label = raw_artist.lower() in KNOWN_RECORD_LABELS
    primary_artist = "" if is_label else clean_artist(raw_artist)

    # Clean title from media tags
    t = title
    for p in STRIP_PATTERNS:
        t = re.sub(p, "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()

    # Split pipe '|' common in Bollywood / YouTube titles (e.g. "Song | Movie | Singers")
    pipe_parts = [p.strip() for p in t.split("|") if p.strip()]
    first_segment = pipe_parts[0] if pipe_parts else t

    # Handle Colon ':' in first segment (e.g. "KING: Tu Mil Jaaye")
    if ":" in first_segment:
        prefix, post = first_segment.split(":", 1)
        prefix = prefix.strip()
        post = post.strip()
        # post is song title, prefix might be singer or movie
        candidates.append((post, prefix))
        if primary_artist:
            candidates.append((post, primary_artist))
        candidates.append((post, ""))
        candidates.append((first_segment, primary_artist))
    else:
        candidates.append((first_segment, primary_artist))
        if primary_artist:
            candidates.append((first_segment, ""))

    # Handle Hyphen ' - ' (e.g. "Artist - Song" or "Movie - Song")
    if " - " in first_segment:
        left, right = first_segment.split(" - ", 1)
        candidates.append((right.strip(), left.strip()))
        candidates.append((right.strip(), primary_artist))
        candidates.append((right.strip(), ""))
        candidates.append((left.strip(), primary_artist))

    # Strip parentheses/brackets like "(From 'KING')"
    clean_no_parens = re.sub(r"[\(\[].*?[\)\]]", "", first_segment).strip()
    if clean_no_parens and clean_no_parens != first_segment:
        candidates.append((clean_no_parens, primary_artist))
        candidates.append((clean_no_parens, ""))

    # Fallback with raw title cleaned
    c_title = clean_title(title)
    candidates.append((c_title, primary_artist))

    # Deduplicate while preserving priority order
    seen = set()
    unique_candidates = []
    for track, art in candidates:
        track = track.strip()
        art = art.strip()
        if not track:
            continue
        key = (track.lower(), art.lower())
        if key not in seen:
            seen.add(key)
            unique_candidates.append((track, art))

    return unique_candidates

def parse_time_tag(tag: str) -> float:
    """Converts mm:ss.xx or hh:mm:ss.xx to seconds"""
    parts = tag.split(":")
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0

def parse_lrc(lrc_text: str) -> List[Dict[str, Any]]:
    """Parse standard or enhanced LRC lyrics into structured lines"""
    lines = []
    # Enhanced LRC pattern: <mm:ss.xx> word <mm:ss.xx> word
    enhanced_word_pattern = re.compile(r"<(\d{2}:\d{2}(?:\.\d+)?)>\s*([^<]+)")
    line_pattern = re.compile(r"^\[(\d{2}:\d{2}(?:\.\d+)?)\](.*)$")

    for raw_line in lrc_text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        match = line_pattern.match(raw_line)
        if match:
            time_str, content = match.groups()
            line_time = parse_time_tag(time_str)
            
            # Check for syllable / word-level timing
            word_matches = enhanced_word_pattern.findall(content)
            words = []
            if word_matches:
                for w_time_str, w_text in word_matches:
                    words.append({
                        "time": parse_time_tag(w_time_str),
                        "text": w_text
                    })
                plain_text = re.sub(r"<\d{2}:\d{2}(?:\.\d+)?>", "", content).strip()
            else:
                plain_text = content.strip()

            lines.append({
                "time": round(line_time, 2),
                "text": plain_text,
                "words": words if words else None
            })

    # Sort lines by time
    lines.sort(key=lambda x: x["time"])
    return lines

def parse_ttml(xml_text: str) -> List[Dict[str, Any]]:
    """Parse Apple Music TTML with syllable/word timestamps"""
    lines = []
    try:
        # Strip namespaces for easy parsing
        xml_clean = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_text)
        root = ET.fromstring(xml_clean)
        for p in root.findall(".//p"):
            begin_str = p.attrib.get("begin", "0")
            begin_sec = parse_time_tag(begin_str.replace("s", ""))
            
            words = []
            for span in p.findall(".//span"):
                span_begin = span.attrib.get("begin")
                span_text = span.text or ""
                if span_begin and span_text:
                    words.append({
                        "time": round(parse_time_tag(span_begin.replace("s", "")), 2),
                        "text": span_text
                    })

            line_text = "".join(p.itertext()).strip()
            lines.append({
                "time": round(begin_sec, 2),
                "text": line_text,
                "words": words if words else None
            })
    except Exception as e:
        logger.error(f"Failed to parse TTML lyrics: {e}")
    return lines

class LyricsEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_lyrics(self, title: str, artist: str, duration: int = 0) -> Dict[str, Any]:
        """Fetch lyrics with cascading provider fallbacks & caching"""
        cache_key = f"{artist.lower().strip()}_{title.lower().strip()}"
        cached = self.db.get_cached_lyrics(cache_key)
        if cached:
            return {
                "synced": True,
                "provider": cached["provider"],
                "lines": cached["lyrics"]
            }

        candidates = generate_search_candidates(title, artist)
        plain_fallback = None

        for cand_title, cand_artist in candidates:
            # 1. Try LRCLIB
            lrclib_res = self._fetch_lrclib(cand_title, cand_artist, duration)
            if lrclib_res:
                if lrclib_res.get("synced"):
                    self.db.cache_lyrics(cache_key, lrclib_res["lines"], "LRCLIB")
                    return lrclib_res
                elif not plain_fallback:
                    plain_fallback = lrclib_res

            # 2. Try lrc.red (search for track isrc or title)
            lrcred_res = self._fetch_lrcred(cand_title, cand_artist)
            if lrcred_res:
                self.db.cache_lyrics(cache_key, lrcred_res["lines"], "lrc.red")
                return lrcred_res

            # 3. Try KuGou
            kugou_res = self._fetch_kugou(cand_title, cand_artist)
            if kugou_res:
                self.db.cache_lyrics(cache_key, kugou_res["lines"], "KuGou")
                return kugou_res

        if plain_fallback:
            return plain_fallback

        return {
            "synced": False,
            "provider": "None",
            "lines": [{"time": 0, "text": "No synchronized lyrics found for this track.", "words": None}]
        }

    def _fetch_lrclib(self, title: str, artist: str, duration: int) -> Optional[Dict[str, Any]]:
        try:
            params = {"track_name": title}
            if artist:
                params["artist_name"] = artist
            if duration > 0:
                params["duration"] = str(duration)
            resp = requests.get("https://lrclib.net/api/get", params=params, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                synced = data.get("syncedLyrics")
                if synced:
                    parsed_lines = parse_lrc(synced)
                    if parsed_lines:
                        return {"synced": True, "provider": "LRCLIB", "lines": parsed_lines}
                plain = data.get("plainLyrics")
                if plain:
                    plain_lines = [{"time": 0, "text": line, "words": None} for line in plain.splitlines() if line.strip()]
                    return {"synced": False, "provider": "LRCLIB (Plain)", "lines": plain_lines}
            
            # If exact match failed, try search endpoint
            query = f"{title} {artist}".strip()
            search_resp = requests.get("https://lrclib.net/api/search", params={"q": query}, timeout=4)
            if search_resp.status_code == 200:
                items = search_resp.json()
                if items and isinstance(items, list):
                    # Priority to synced
                    for item in items[:4]:
                        synced = item.get("syncedLyrics")
                        if synced:
                            parsed_lines = parse_lrc(synced)
                            if parsed_lines:
                                return {"synced": True, "provider": "LRCLIB", "lines": parsed_lines}
                    # Fallback to plain
                    for item in items[:4]:
                        plain = item.get("plainLyrics")
                        if plain:
                            plain_lines = [{"time": 0, "text": line, "words": None} for line in plain.splitlines() if line.strip()]
                            return {"synced": False, "provider": "LRCLIB (Plain)", "lines": plain_lines}
        except Exception as e:
            logger.debug(f"LRCLIB fetch error: {e}")
        return None

    def _fetch_lrcred(self, title: str, artist: str) -> Optional[Dict[str, Any]]:
        try:
            # Search lrc.red API
            resp = requests.get(
                "https://lrc.red/api/search",
                params={"query": f"{title} {artist}"},
                timeout=4
            )
            if resp.status_code == 200:
                hits = resp.json()
                if isinstance(hits, list) and hits:
                    best_isrc = hits[0].get("isrc")
                    if best_isrc:
                        ttml_resp = requests.get(f"https://lrc.red/s/{best_isrc}.ttml", timeout=4)
                        if ttml_resp.status_code == 200:
                            parsed = parse_ttml(ttml_resp.text)
                            if parsed:
                                return {"synced": True, "provider": "lrc.red (Apple Syllable)", "lines": parsed}
        except Exception as e:
            logger.debug(f"lrc.red fetch error: {e}")
        return None

    def _fetch_kugou(self, title: str, artist: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"http://lyrics.kugou.com/search?ver=1&man=yes&client=pc&keyword={title} {artist}&duration=0&hash="
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    candidate = candidates[0]
                    c_id = candidate.get("id")
                    accesskey = candidate.get("accesskey")
                    if c_id and accesskey:
                        lrc_url = f"http://lyrics.kugou.com/download?ver=1&client=pc&id={c_id}&accesskey={accesskey}&fmt=lrc&charset=utf8"
                        l_resp = requests.get(lrc_url, timeout=4)
                        if l_resp.status_code == 200:
                            l_data = l_resp.json()
                            content = l_data.get("content", "")
                            if content:
                                import base64
                                decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
                                parsed = parse_lrc(decoded)
                                if parsed:
                                    return {"synced": True, "provider": "KuGou", "lines": parsed}
        except Exception as e:
            logger.debug(f"KuGou fetch error: {e}")
        return None
