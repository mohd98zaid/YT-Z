"""
High-Performance Local Disk Audio Cache for YT-Z.
Stores streamed audio files on disk with HTTP 206 Partial Content support,
enabling 0ms instant playback for cached tracks, scrubbing without network latency,
and seamless gapless 2-song caching.
"""
import time
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Generator, Tuple
from fastapi.responses import StreamingResponse

logger = logging.getLogger("YTZ.AudioCache")

CACHE_DIR = Path.home() / ".ytz" / "audio_cache"
MAX_CACHE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
TARGET_CACHE_BYTES = 1536 * 1024 * 1024   # 1.5 GB target when evicting

class AudioCacheManager:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._active_downloads: Dict[str, threading.Event] = {}
        # Clean up orphaned .part temp files left by interrupted runs
        try:
            for part_f in self.cache_dir.glob("*.part"):
                part_f.unlink(missing_ok=True)
        except Exception:
            pass

    def invalidate(self, video_id: str) -> None:
        """Delete any cached audio and metadata for a track (e.g. on stream recovery)."""
        audio_file, meta_file, _ = self.get_file_paths(video_id)
        try:
            with self._lock:
                audio_file.unlink(missing_ok=True)
                meta_file.unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"Cache invalidation note for {video_id}: {e}")

    def get_file_paths(self, video_id: str) -> Tuple[Path, Path, Path]:
        safe_id = "".join(c for c in video_id if c.isalnum() or c in ("-", "_"))
        audio_file = self.cache_dir / f"{safe_id}.audio"
        meta_file = self.cache_dir / f"{safe_id}.meta.json"
        part_file = self.cache_dir / f"{safe_id}.part"
        return audio_file, meta_file, part_file

    def is_cached(self, video_id: str) -> bool:
        audio_file, meta_file, _ = self.get_file_paths(video_id)
        return audio_file.exists() and meta_file.exists() and audio_file.stat().st_size > 32 * 1024

    def get_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        audio_file, meta_file, _ = self.get_file_paths(video_id)
        if not (audio_file.exists() and meta_file.exists()):
            return None
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            # Update access time for LRU
            meta["last_accessed"] = time.time()
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f)
            return meta
        except Exception as e:
            logger.debug(f"Error reading meta for {video_id}: {e}")
            return None

    def store_file(self, video_id: str, temp_path: Path, metadata: Dict[str, Any]) -> bool:
        """Atomically promote a downloaded temp file into the cache with Windows locking resilience."""
        audio_file, meta_file, _ = self.get_file_paths(video_id)
        try:
            with self._lock:
                if temp_path.exists() and temp_path.stat().st_size > 32 * 1024:
                    if audio_file.exists():
                        try:
                            audio_file.unlink(missing_ok=True)
                        except Exception:
                            pass
                    # On Windows, try atomic rename, falling back to copy+unlink if handles are still releasing
                    try:
                        temp_path.rename(audio_file)
                    except (PermissionError, OSError):
                        import shutil
                        shutil.copy2(str(temp_path), str(audio_file))
                        try:
                            temp_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    metadata["size_bytes"] = audio_file.stat().st_size
                    metadata["last_accessed"] = time.time()
                    metadata["cached_at"] = time.time()
                    with open(meta_file, "w", encoding="utf-8") as f:
                        json.dump(metadata, f, indent=2)
                    logger.info(f"Successfully cached audio for {video_id} ({metadata['size_bytes'] / (1024*1024):.2f} MB)")
                    self._evict_if_needed_locked()
                    return True
        except Exception as e:
            logger.error(f"Failed to store cached file for {video_id}: {e}")
        return False

    def serve_cached(self, video_id: str, range_header: Optional[str] = None) -> Optional[StreamingResponse]:
        """
        Serve cached audio file with HTTP 206 Partial Content Range support.
        Allows instant seeking and scrubbing with zero latency.
        """
        audio_file, meta_file, _ = self.get_file_paths(video_id)
        if not audio_file.exists():
            return None

        meta = self.get_metadata(video_id) or {}
        content_type = meta.get("content_type", "audio/webm")
        file_size = audio_file.stat().st_size

        if not range_header:
            def full_generator() -> Generator[bytes, None, None]:
                with open(audio_file, "rb") as f:
                    while chunk := f.read(128 * 1024):
                        yield chunk

            headers = {
                "Accept-Ranges": "bytes",
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Cache-Control": "public, max-age=86400",
                "X-Audio-Cache": "HIT",
                "X-Audio-Codec": str(meta.get("codec", "opus")),
                "X-Audio-Bitrate": str(meta.get("bitrate", 256)),
                "X-Audio-Lossless": "true" if meta.get("isLossless") else "false",
                "X-Audio-Source": str(meta.get("source", "cache")),
            }
            return StreamingResponse(full_generator(), status_code=200, headers=headers, media_type=content_type)

        # Parse HTTP Range Header: bytes=START-END
        try:
            from fastapi.responses import Response
            byte_range = range_header.replace("bytes=", "").strip()
            parts = byte_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            if start >= file_size:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
            if end >= file_size:
                end = file_size - 1
            if start > end:
                start = 0
            content_length = (end - start) + 1

            def range_generator() -> Generator[bytes, None, None]:
                with open(audio_file, "rb") as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(128 * 1024, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            headers = {
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Content-Type": content_type,
                "Cache-Control": "public, max-age=86400",
                "X-Audio-Cache": "HIT-PARTIAL",
                "X-Audio-Codec": str(meta.get("codec", "opus")),
                "X-Audio-Bitrate": str(meta.get("bitrate", 256)),
                "X-Audio-Lossless": "true" if meta.get("isLossless") else "false",
                "X-Audio-Source": str(meta.get("source", "cache")),
            }
            return StreamingResponse(range_generator(), status_code=206, headers=headers, media_type=content_type)
        except Exception as e:
            logger.error(f"Error serving range for cached file {video_id}: {e}")
            return None

    def _evict_if_needed_locked(self):
        """LRU eviction of old cache files if size limit exceeded."""
        try:
            audio_files = list(self.cache_dir.glob("*.audio"))
            total_bytes = sum(f.stat().st_size for f in audio_files)
            if total_bytes <= MAX_CACHE_BYTES:
                return

            logger.info(f"Audio cache size ({total_bytes / (1024*1024):.1f} MB) exceeds limit. Evicting LRU tracks...")
            # Sort files by last_accessed from metadata or mtime
            file_access = []
            for af in audio_files:
                stem = af.stem
                meta_f = self.cache_dir / f"{stem}.meta.json"
                last_time = af.stat().st_mtime
                if meta_f.exists():
                    try:
                        with open(meta_f, "r", encoding="utf-8") as f:
                            m = json.load(f)
                            last_time = m.get("last_accessed", last_time)
                    except:
                        pass
                file_access.append((last_time, af, meta_f))

            file_access.sort(key=lambda x: x[0])  # Oldest first

            for _, af, mf in file_access:
                if total_bytes <= TARGET_CACHE_BYTES:
                    break
                sz = af.stat().st_size
                af.unlink(missing_ok=True)
                mf.unlink(missing_ok=True)
                total_bytes -= sz
                logger.info(f"Evicted old cached audio: {af.name} ({sz / (1024*1024):.2f} MB)")
        except Exception as e:
            logger.error(f"Cache eviction error: {e}")

# Global audio cache singleton
audio_cache = AudioCacheManager()
