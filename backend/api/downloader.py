"""
Industrial yt-dlp Downloader Engine for YT-Z.
Concurrent downloads, video (4K/1080p/720p) and audio (MP3 320k/FLAC/M4A/OPUS/WAV),
metadata, thumbnail, and lyrics embedding, progress event hooks.
"""
import time
import uuid
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Callable

import yt_dlp
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, APIC, USLT
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.flac import FLAC, Picture
except ImportError:
    mutagen = None

from backend.core.database import DatabaseManager
from backend.core.config import ConfigManager

logger = logging.getLogger("YTZ.Downloader")

class DownloaderEngine:
    def __init__(
        self,
        db: DatabaseManager,
        config: ConfigManager,
        broadcast_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
        stream_resolver: Any = None
    ):
        self.db = db
        self.config = config
        self.broadcast_fn = broadcast_fn
        self.stream_resolver = stream_resolver
        self.max_workers = int(config.get("concurrent_downloads", 3))
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="YTZ_Worker")
        self.active_tasks: Dict[str, Any] = {}
        self.cancelled_tasks: set = set()
        self.lock = threading.Lock()

    def set_broadcast_fn(self, fn: Callable[[Dict[str, Any]], None]):
        self.broadcast_fn = fn

    def emit(self, event_type: str, data: Dict[str, Any]):
        if self.broadcast_fn:
            try:
                self.broadcast_fn({"type": event_type, "data": data})
            except Exception as e:
                logger.debug(f"Broadcast emit error: {e}")

    def inspect_url(self, url: str) -> Dict[str, Any]:
        """Inspects URL metadata, format choices, or playlist entries"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("Could not extract metadata from URL")

            is_playlist = "entries" in info
            if is_playlist:
                entries = []
                for entry in (info.get("entries") or []):
                    if entry:
                        entries.append({
                            "id": entry.get("id"),
                            "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            "title": entry.get("title", "Untitled"),
                            "duration": entry.get("duration", 0),
                            "uploader": entry.get("uploader", ""),
                        })
                return {
                    "is_playlist": True,
                    "title": info.get("title", "Playlist"),
                    "count": len(entries),
                    "entries": entries
                }
            else:
                formats = []
                for f in info.get("formats", []):
                    note = f.get("format_note") or f.get("resolution") or ""
                    vcodec = f.get("vcodec")
                    acodec = f.get("acodec")
                    if vcodec != "none" and acodec != "none":
                        formats.append({
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "resolution": f.get("resolution"),
                            "note": note,
                            "filesize": f.get("filesize") or f.get("filesize_approx", 0)
                        })
                return {
                    "is_playlist": False,
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "uploader": info.get("uploader") or info.get("artist"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "formats": formats
                }

    def queue_download(
        self,
        url: str,
        download_type: str = "audio",  # 'audio' or 'video'
        output_format: str = "mp3",   # 'mp3', 'm4a', 'flac', 'opus', 'wav', 'mp4', 'mkv'
        quality: str = "320",         # '320', '256', '1080p', '4K', etc.
        title: Optional[str] = None,
        artist: Optional[str] = None,
        thumbnail: Optional[str] = None
    ) -> str:
        """Enqueue a new download task"""
        task_id = str(uuid.uuid4())
        item = {
            "id": task_id,
            "url": url,
            "title": title or "Extracting...",
            "artist": artist or "",
            "thumbnail": thumbnail or "",
            "download_type": download_type,
            "format": output_format,
            "quality": quality,
            "status": "pending",
            "progress": 0.0,
            "speed": "0 MB/s",
            "eta": "00:00",
            "file_size": 0,
            "file_path": None,
            "error_message": None,
        }
        self.db.add_download(item)
        self.emit("download_queued", item)

        # Submit to thread pool
        future = self.executor.submit(self._run_download, task_id, url, download_type, output_format, quality)
        with self.lock:
            self.active_tasks[task_id] = future
        return task_id

    def _progress_hook(self, d: Dict[str, Any], task_id: str):
        if task_id in self.cancelled_tasks:
            raise Exception("Download cancelled by user")

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100.0) if total > 0 else 0.0
            
            speed_val = d.get("speed") or 0
            if speed_val > 1024 * 1024:
                speed_str = f"{speed_val / (1024 * 1024):.2f} MB/s"
            elif speed_val > 1024:
                speed_str = f"{speed_val / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed_val:.0f} B/s"

            eta_seconds = d.get("eta") or 0
            mins, secs = divmod(int(eta_seconds), 60)
            eta_str = f"{mins:02d}:{secs:02d}"

            updates = {
                "status": "downloading",
                "progress": round(percent, 1),
                "speed": speed_str,
                "eta": eta_str,
                "file_size": total
            }
            self.db.update_download(task_id, updates)
            self.emit("download_progress", {"id": task_id, **updates})

        elif status == "finished":
            updates = {
                "status": "processing",
                "progress": 100.0,
                "speed": "Processing...",
                "eta": "00:00"
            }
            self.db.update_download(task_id, updates)
            self.emit("download_progress", {"id": task_id, **updates})

    def _run_download(self, task_id: str, url: str, download_type: str, output_format: str, quality: str):
        download_dir = Path(self.config.get("download_dir"))
        download_dir.mkdir(parents=True, exist_ok=True)
        out_template = str(download_dir / "%(title)s [%(id)s].%(ext)s")

        existing_info = self.db.get_download(task_id) or {}
        item_title = existing_info.get("title") or ""
        item_artist = existing_info.get("artist") or ""

        download_url = url
        # Download at original audio which is playing (Lossless FLAC Master resolution)
        if download_type == "audio" and (output_format == "flac" or quality in ("lossless", "original", "flac")) and self.stream_resolver:
            video_id = None
            if "watch?v=" in url:
                video_id = url.split("watch?v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]
            elif len(url) == 11 and not url.startswith("http"):
                video_id = url

            if video_id:
                try:
                    resolved = self.stream_resolver.resolve_audio(
                        video_id=video_id,
                        title=item_title,
                        artist=item_artist,
                        quality="lossless"
                    )
                    if resolved and resolved.get("isLossless") and resolved.get("streamUrl"):
                        s_target = resolved["streamUrl"]
                        if s_target.startswith("http://") or s_target.startswith("https://"):
                            download_url = s_target
                            output_format = "flac"
                            logger.info(f"Targeting original Hi-Res FLAC master stream for download: {s_target[:60]}...")
                except Exception as ex:
                    logger.warning(f"Could not resolve direct lossless stream for download: {ex}")

        ydl_opts: Dict[str, Any] = {
            'outtmpl': out_template,
            'progress_hooks': [lambda d: self._progress_hook(d, task_id)],
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
        }

        # Embed thumbnail & metadata options
        if self.config.get("embed_thumbnail", True):
            ydl_opts['writethumbnail'] = True

        # Configure Audio vs Video
        if download_type == "audio":
            bitrate_map = {"320": "320K", "256": "256K", "192": "192K", "128": "128K"}
            target_bitrate = bitrate_map.get(str(quality), "320K")
            
            postprocessors: List[Dict[str, Any]] = [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': output_format,
                    'preferredquality': target_bitrate.replace("K", "") if output_format == "mp3" else None,
                }
            ]
            if self.config.get("embed_metadata", True):
                postprocessors.append({'key': 'FFmpegMetadata', 'add_metadata': True})
            if self.config.get("embed_thumbnail", True) and output_format in ("mp3", "m4a", "flac"):
                postprocessors.append({'key': 'EmbedThumbnail'})

            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = postprocessors

        else: # Video
            res_height = quality.replace("p", "").replace("K", "2160")
            if res_height == "4":
                res_height = "2160"
            ydl_opts['format'] = f"bestvideo[height<={res_height}]+bestaudio/best[height<={res_height}]/best"
            
            postprocessors = []
            if self.config.get("embed_metadata", True):
                postprocessors.append({'key': 'FFmpegMetadata', 'add_metadata': True})
            if self.config.get("embed_subtitles", False):
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                postprocessors.append({'key': 'FFmpegEmbedSubtitle'})
            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors

        try:
            self.db.update_download(task_id, {"status": "downloading"})
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(download_url, download=True)
                title = info.get("title") or item_title or "Downloaded Media"
                artist = info.get("uploader") or info.get("artist") or item_artist or ""
                thumbnail = info.get("thumbnail") or ""
                duration = info.get("duration") or 0

                # Find final downloaded file
                expected_filename = ydl.prepare_filename(info)
                final_path = Path(expected_filename)
                if not final_path.exists():
                    # Check for converted extension
                    final_path = final_path.with_suffix(f".{output_format}")

                file_size = final_path.stat().st_size if final_path.exists() else 0

                # Embed extra ID3 tags if mutagen is available
                if mutagen and final_path.exists() and output_format == "mp3":
                    try:
                        audio_tags = EasyID3(str(final_path))
                        audio_tags["title"] = title
                        if artist:
                            audio_tags["artist"] = artist
                        audio_tags.save()
                    except Exception:
                        pass

                updates = {
                    "title": title,
                    "artist": artist,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "status": "completed",
                    "progress": 100.0,
                    "file_size": file_size,
                    "file_path": str(final_path),
                    "completed_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.db.update_download(task_id, updates)
                self.emit("download_completed", {"id": task_id, **updates})

        except Exception as e:
            if task_id in self.cancelled_tasks:
                self.db.update_download(task_id, {"status": "cancelled", "error_message": "Cancelled by user"})
                self.emit("download_cancelled", {"id": task_id})
            else:
                logger.error(f"Download task {task_id} failed: {e}")
                err_msg = str(e)
                self.db.update_download(task_id, {"status": "failed", "error_message": err_msg})
                self.emit("download_failed", {"id": task_id, "error": err_msg})
        finally:
            with self.lock:
                self.active_tasks.pop(task_id, None)
                self.cancelled_tasks.discard(task_id)

    def cancel_download(self, task_id: str) -> bool:
        """Cancel an ongoing download"""
        with self.lock:
            self.cancelled_tasks.add(task_id)
            future = self.active_tasks.get(task_id)
            if future:
                future.cancel()
        self.db.update_download(task_id, {"status": "cancelled"})
        self.emit("download_cancelled", {"id": task_id})
        return True

    def retry_download(self, task_id: str) -> bool:
        """Retry a failed or cancelled download"""
        item = self.db.get_download(task_id)
        if not item:
            return False
        return bool(self.queue_download(
            url=item["url"],
            download_type=item["download_type"],
            output_format=item["format"],
            quality=item["quality"],
            title=item.get("title"),
            artist=item.get("artist"),
            thumbnail=item.get("thumbnail")
        ))
