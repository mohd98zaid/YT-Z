"""
Configuration management for YT-Z.
Stores settings in user's home directory: ~/.ytz/config.json
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("YTZ.Config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "theme": "apple-music",
    "theme_mode": "dark",
    "download_dir": str(Path.home() / "Music" / "YT-Z Downloads"),
    "default_audio_format": "mp3",
    "default_audio_quality": "320",
    "default_video_quality": "1080p",
    "concurrent_downloads": 3,
    "embed_thumbnail": True,
    "embed_metadata": True,
    "embed_lyrics": True,
    "embed_subtitles": False,
    "crossfade_seconds": 3,
    "gapless_playback": True,
    "volume": 0.85,
    "eq_preset": "Flat",
    "eq_bands": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "playback_speed": 1.0,
    "sponsorblock_enabled": True,
    "sponsorblock_categories": ["sponsor", "intro", "outro", "music_offtopic"],
    "lyrics_provider_preference": "auto",
    "discord_rpc_enabled": True,
    "notifications_enabled": True,
}

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".ytz"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = {}
        self.load()
        # Ensure default download directory exists
        Path(self.get("download_dir")).mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._config = {**DEFAULT_CONFIG, **saved}
                    return self._config
            except Exception as e:
                logger.error(f"Failed to read config file: {e}")
        self._config = DEFAULT_CONFIG.copy()
        self.save()
        return self._config

    def save(self) -> bool:
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        self._config.update(updates)
        self.save()
        return self._config

    def all(self) -> Dict[str, Any]:
        return self._config.copy()
