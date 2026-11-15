"""
Local Music Library Scanner & File Bridge for YT-Z.
Scans downloaded audio files and local music folders,
extracts tags, and provides endpoints to stream or reveal in Explorer.
"""
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3
    from mutagen.mp4 import MP4
    from mutagen.flac import FLAC
except ImportError:
    mutagen = None

from backend.core.config import ConfigManager

logger = logging.getLogger("YTZ.LocalLibrary")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".opus", ".wav", ".aac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}

class LocalLibrary:
    def __init__(self, config: ConfigManager):
        self.config = config

    def scan_directory(self, target_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scan directory for audio and video files and extract metadata"""
        folder_path = Path(target_dir) if target_dir else Path(self.config.get("download_dir"))
        if not folder_path.exists():
            return []

        items = []
        try:
            for entry in folder_path.rglob("*"):
                if entry.is_file():
                    ext = entry.suffix.lower()
                    if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
                        item = self._extract_file_info(entry)
                        items.append(item)
        except Exception as e:
            logger.error(f"Error scanning directory {folder_path}: {e}")

        # Sort by last modified descending
        items.sort(key=lambda x: x.get("modifiedTime", 0), reverse=True)
        return items

    def _extract_file_info(self, file_path: Path) -> Dict[str, Any]:
        stat = file_path.stat()
        ext = file_path.suffix.lower()
        media_type = "video" if ext in VIDEO_EXTENSIONS else "audio"
        title = file_path.stem
        artist = "Local Media"
        album = "Local Library"
        duration_seconds = 0

        if mutagen:
            try:
                if ext == ".mp3":
                    tags = EasyID3(str(file_path))
                    title = tags.get("title", [title])[0]
                    artist = tags.get("artist", [artist])[0]
                    album = tags.get("album", [album])[0]
                    m = mutagen.File(str(file_path))
                    duration_seconds = int(m.info.length) if m and m.info else 0
                elif ext in (".m4a", ".mp4"):
                    tags = MP4(str(file_path))
                    title = tags.get("\xa9nam", [title])[0]
                    artist = tags.get("\xa9ART", [artist])[0]
                    album = tags.get("\xa9alb", [album])[0]
                    duration_seconds = int(tags.info.length) if tags.info else 0
                elif ext == ".flac":
                    tags = FLAC(str(file_path))
                    title = tags.get("title", [title])[0]
                    artist = tags.get("artist", [artist])[0]
                    album = tags.get("album", [album])[0]
                    duration_seconds = int(tags.info.length) if tags.info else 0
                else:
                    m = mutagen.File(str(file_path))
                    if m and m.info:
                        duration_seconds = int(m.info.length)
            except Exception:
                pass

        mins, secs = divmod(duration_seconds, 60)
        duration_str = f"{mins}:{secs:02d}" if duration_seconds > 0 else "--:--"

        return {
            "id": f"local_{abs(hash(str(file_path)))}",
            "title": title,
            "artist": artist,
            "album": album,
            "duration": duration_str,
            "durationSeconds": duration_seconds,
            "filePath": str(file_path),
            "fileName": file_path.name,
            "fileSize": stat.st_size,
            "modifiedTime": stat.st_mtime,
            "extension": ext.replace(".", ""),
            "mediaType": media_type,
            "isLocal": True,
            "thumbnail": ""  # Handled by local cover extraction endpoint
        }

    def open_in_explorer(self, file_path_str: str) -> bool:
        """Open Windows Explorer with file or directory selected"""
        try:
            target = Path(file_path_str)
            if not target.exists():
                return False

            if sys.platform == "win32":
                if target.is_file():
                    subprocess.run(["explorer", f"/select,{target}"], check=False)
                else:
                    subprocess.run(["explorer", str(target)], check=False)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Failed to open explorer for {file_path_str}: {e}")
            return False
