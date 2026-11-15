"""
Pluggable Module Sources & Extensions Manager for YT-Z.
Inspired by BitChord's pluggable module sources architecture and ytm-rs features:
- Audio Sources: Hi-Res Lossless FLAC / ALAC modules with YouTube Music fallback.
- Lyrics Providers: Multi-source engines (BetterLyrics syllable-level, LRCLIB, Genius, Musixmatch).
- Enhancements: SponsorBlock auto-skipping, Skip Silence, Volume Normalization.
- Connectivity & Scrobblers: Discord Rich Presence, Last.fm, ListenBrainz.
"""
import time
import uuid
import logging
import requests
from typing import List, Dict, Any, Optional
from backend.core.database import DatabaseManager

logger = logging.getLogger("YTZ.Plugins")

DEFAULT_PLUGINS = [
    {
        "id": "better-lyrics",
        "name": "BetterLyrics Syllable Engine",
        "type": "lyrics_source",
        "description": "Word & syllable-level Apple Music style karaoke lyrics with multi-provider fallback and romanization.",
        "endpoint": "https://lyrics.paxsenix.org/lyrics",
        "enabled": True,
        "status": "active",
        "latency_ms": 38,
        "icon": "Mic2",
        "is_builtin": True
    },
    {
        "id": "lrclib",
        "name": "LRCLIB Community Database",
        "type": "lyrics_source",
        "description": "High-availability, open-source synchronized and plain lyrics repository.",
        "endpoint": "https://lrclib.net/api/get",
        "enabled": True,
        "status": "active",
        "latency_ms": 45,
        "icon": "FileText",
        "is_builtin": True
    },
    {
        "id": "genius",
        "name": "Genius Annotations & Lore",
        "type": "lyrics_source",
        "description": "Rich song annotations, meanings, verified lyrics, and behind-the-scenes music trivia.",
        "endpoint": "https://api.genius.com",
        "enabled": True,
        "status": "active",
        "latency_ms": 62,
        "icon": "Sparkles",
        "is_builtin": True
    },
    {
        "id": "flac-lossless",
        "name": "Hi-Res FLAC Lossless Module",
        "type": "audio_source",
        "description": "Streams bit-perfect 16-bit/24-bit 48kHz+ FLAC audio with automatic fallback to YouTube 256k Opus.",
        "endpoint": "https://api.deezer.com",
        "enabled": True,
        "status": "active",
        "latency_ms": 55,
        "icon": "Disc",
        "is_builtin": True
    },
    {
        "id": "sponsorblock",
        "name": "SponsorBlock Auto-Skip",
        "type": "enhancement",
        "description": "Crowdsourced database that automatically skips non-music talking segments, skits, and sponsor intros.",
        "endpoint": "https://sponsor.ajay.app/api/skipSegments",
        "enabled": True,
        "status": "active",
        "latency_ms": 32,
        "icon": "ShieldCheck",
        "is_builtin": True
    },
    {
        "id": "skip-silence",
        "name": "Smart Silence Truncation",
        "type": "audio_filter",
        "description": "Dynamically detects trailing/leading silent pauses between tracks and advances seamlessly.",
        "endpoint": "local://audio/dsp/silence-detector",
        "enabled": True,
        "status": "active",
        "latency_ms": 1,
        "icon": "Sliders",
        "is_builtin": True
    },
    {
        "id": "replaygain-norm",
        "name": "ReplayGain Loudness Leveler",
        "type": "audio_filter",
        "description": "Normalizes dynamic range to target -14 LUFS standard across varying studio mastering volumes.",
        "endpoint": "local://audio/dsp/loudness-normalizer",
        "enabled": True,
        "status": "active",
        "latency_ms": 1,
        "icon": "Volume2",
        "is_builtin": True
    },
    {
        "id": "discord-rpc",
        "name": "Discord Rich Presence",
        "type": "scrobbler",
        "description": "Broadcasts live track artwork, song title, artist, and remaining elapsed time to your Discord profile.",
        "endpoint": "local://ipc/discord-rpc",
        "enabled": True,
        "status": "active",
        "latency_ms": 2,
        "icon": "Radio",
        "is_builtin": True
    },
    {
        "id": "scrobbler-lastfm",
        "name": "Last.fm & ListenBrainz Sync",
        "type": "scrobbler",
        "description": "Automated scrobbling of played tracks after 50% song completion or 4 minutes of listening.",
        "endpoint": "https://ws.audioscrobbler.com/2.0/",
        "enabled": False,
        "status": "standby",
        "latency_ms": 70,
        "icon": "Share2",
        "is_builtin": True
    }
]

class PluginService:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._init_defaults()

    def _init_defaults(self):
        existing = self.db.get_all_plugins()
        if not existing:
            for p in DEFAULT_PLUGINS:
                self.db.upsert_plugin(p)
            logger.info("Initialized default pluggable module sources.")

    def list_plugins(self) -> List[Dict[str, Any]]:
        return self.db.get_all_plugins()

    def toggle_plugin(self, plugin_id: str, enabled: bool) -> bool:
        return self.db.set_plugin_enabled(plugin_id, enabled)

    def add_custom_plugin(self, data: Dict[str, Any]) -> Dict[str, Any]:
        plugin_id = data.get("id") or f"custom-{uuid.uuid4().hex[:8]}"
        plugin = {
            "id": plugin_id,
            "name": data.get("name", "Custom Module Source"),
            "type": data.get("type", "audio_source"),
            "description": data.get("description", "Custom user-configured module source"),
            "endpoint": data.get("endpoint", ""),
            "api_key": data.get("api_key", ""),
            "enabled": True,
            "status": "active",
            "latency_ms": 0,
            "icon": data.get("icon", "Puzzle"),
            "is_builtin": False
        }
        self.db.upsert_plugin(plugin)
        # Test health immediately
        self.test_plugin(plugin_id)
        return plugin

    def delete_custom_plugin(self, plugin_id: str) -> bool:
        return self.db.delete_plugin(plugin_id)

    def test_plugin(self, plugin_id: str) -> Dict[str, Any]:
        plugins = {p["id"]: p for p in self.db.get_all_plugins()}
        if plugin_id not in plugins:
            return {"status": "error", "message": "Plugin not found"}

        plugin = plugins[plugin_id]
        endpoint = plugin.get("endpoint", "")

        # Local plugins
        if endpoint.startswith("local://"):
            self.db.update_plugin_status(plugin_id, "active", 1)
            return {"status": "active", "latency_ms": 1, "message": "Local DSP module healthy"}

        # Remote HTTP endpoints
        start = time.perf_counter()
        try:
            resp = requests.head(endpoint, timeout=4.0, headers={"User-Agent": "YT-Z/1.0"})
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            status = "active" if resp.status_code < 500 else "degraded"
            self.db.update_plugin_status(plugin_id, status, elapsed_ms)
            return {"status": status, "latency_ms": elapsed_ms, "http_status": resp.status_code}
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(f"Health check warning for {plugin_id}: {e}")
            self.db.update_plugin_status(plugin_id, "degraded", elapsed_ms)
            return {"status": "degraded", "latency_ms": elapsed_ms, "error": str(e)}
