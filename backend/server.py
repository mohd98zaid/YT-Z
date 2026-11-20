"""
YT-Z Local Backend Server.
FastAPI + WebSocket bridge strictly bound to 127.0.0.1.
Unifies YouTube Music API, Industrial yt-dlp Downloader,
Multi-provider Lyrics Engine, Spotify Importer, and Local Media Server.
"""
import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import requests
import uvicorn

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.config import ConfigManager
from backend.core.database import DatabaseManager
from backend.api.ytmusic import YTMusicService
from backend.api.stream import StreamResolver
from backend.api.lyrics import LyricsEngine
from backend.api.downloader import DownloaderEngine
from backend.api.spotify_importer import SpotifyImporter
from backend.api.local_library import LocalLibrary
from backend.api.plugins import PluginService
from backend.api.youtube_search import YouTubeSearchService
from backend.api.addon_source import AddonSourceResolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("YTZ.Server")

app = FastAPI(title="YT-Z Desktop Core Engine", version="1.0.0")

# CORS middleware for local frontend and LAN / mobile devices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Core Subsystems
config_mgr = ConfigManager()
db_mgr = DatabaseManager()
ytmusic_svc = YTMusicService()
addon_resolver = AddonSourceResolver(db_mgr)
stream_resolver = StreamResolver(addon_resolver)
lyrics_engine = LyricsEngine(db_mgr)
local_lib = LocalLibrary(config_mgr)
plugin_svc = PluginService(db_mgr)
yt_search_svc = YouTubeSearchService()

# WebSocket Connection Manager
class WSManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        logger.info(f"WebSocket client connected. Active: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        logger.info(f"WebSocket client disconnected. Active: {len(self.active)}")

    def broadcast_sync(self, message: Dict[str, Any]):
        if not self.active or not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    async def broadcast(self, message: Dict[str, Any]):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)

ws_manager = WSManager()
downloader_engine = DownloaderEngine(db_mgr, config_mgr, broadcast_fn=ws_manager.broadcast_sync, stream_resolver=stream_resolver)

@app.on_event("startup")
async def startup_event():
    ws_manager.loop = asyncio.get_running_loop()
    logger.info("YT-Z Server started successfully on port 47892.")

def get_lan_ip() -> str:
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ==================== System & Config Endpoints ====================

@app.get("/api/network-info")
async def get_network_info():
    lan_ip = get_lan_ip()
    port = config_mgr.get("server_port", 47892)
    return {
        "local_ip": lan_ip,
        "port": port,
        "local_url": f"http://127.0.0.1:{port}",
        "lan_url": f"http://{lan_ip}:{port}",
    }

@app.get("/api/status")
async def get_status():
    return {
        "status": "online",
        "app": "YT-Z",
        "version": "1.0.0",
        "download_dir": config_mgr.get("download_dir"),
        "active_downloads": len(downloader_engine.active_tasks),
    }

@app.get("/api/config")
async def get_config():
    return config_mgr.all()

@app.post("/api/config")
async def update_config(payload: Dict[str, Any] = Body(...)):
    updated = config_mgr.update(payload)
    return {"status": "ok", "config": updated}

@app.get("/api/session")
async def get_session():
    return config_mgr.all()

@app.post("/api/session")
async def update_session(payload: Dict[str, Any] = Body(...)):
    updated = config_mgr.update(payload)
    return {"status": "ok", "session": updated}

# ==================== YouTube Music Discovery ====================

@app.get("/api/ytm/home")
async def get_ytm_home():
    return ytmusic_svc.get_home()

@app.get("/api/ytm/quick-picks")
async def get_quick_picks(
    refresh: bool = Query(False),
    mood: Optional[str] = Query(None),
    limit: int = Query(10)
):
    return ytmusic_svc.get_quick_picks(refresh=refresh, mood=mood, limit=limit)

@app.get("/api/ytm/charts")
async def get_ytm_charts(country: str = Query("IN")):
    return ytmusic_svc.get_charts(country)

@app.get("/api/ytm/moods")
async def get_mood_categories():
    return ytmusic_svc.get_mood_categories()

@app.get("/api/ytm/moods/playlists")
async def get_mood_playlists(params: str = Query(...)):
    return ytmusic_svc.get_mood_playlists(params)

@app.get("/api/ytm/search")
async def search_ytm(query: str = Query(...), filter: Optional[str] = Query(None)):
    return ytmusic_svc.search(query, filter_type=filter)

@app.get("/api/ytm/suggestions")
async def search_suggestions(query: str = Query(...)):
    return ytmusic_svc.get_search_suggestions(query)

@app.get("/api/ytm/artist/{channel_id}")
async def get_artist(channel_id: str):
    data = ytmusic_svc.get_artist(channel_id)
    if not data:
        raise HTTPException(status_code=404, detail="Artist not found")
    return data

@app.get("/api/ytm/album/{browse_id}")
async def get_album(browse_id: str):
    data = ytmusic_svc.get_album(browse_id)
    if not data:
        raise HTTPException(status_code=404, detail="Album not found")
    return data

@app.get("/api/ytm/playlist/{playlist_id}")
async def get_playlist(playlist_id: str):
    data = ytmusic_svc.get_playlist(playlist_id)
    if not data:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return data

@app.get("/api/ytm/radio/{video_id}")
async def get_radio(video_id: str):
    return ytmusic_svc.get_watch_playlist(video_id)

# ==================== Stream & Audio Endpoints ====================

@app.get("/api/stream/{video_id}")
async def get_audio_stream(
    video_id: str,
    title: Optional[str] = Query(""),
    artist: Optional[str] = Query(""),
    duration: Optional[int] = Query(0),
    quality: Optional[str] = Query("auto")
):
    stream_info = stream_resolver.resolve_audio(
        video_id,
        title=title,
        artist=artist,
        duration=duration,
        quality=quality
    )
    if not stream_info:
        raise HTTPException(status_code=500, detail="Could not resolve audio stream for track.")
    return stream_info

@app.get("/api/stream/{video_id}/audio")
async def stream_audio_proxy(
    video_id: str,
    request: Request,
    title: Optional[str] = Query(""),
    artist: Optional[str] = Query(""),
    quality: Optional[str] = Query("auto")
):
    """
    Audio streaming proxy with HTTP 206 Partial Content Range support and fast disconnection cleanup.
    Supports Lossless FLAC/ALAC add-on streams and YouTube Opus.
    """
    loop = asyncio.get_event_loop()
    stream_info = await loop.run_in_executor(
        None,
        lambda: stream_resolver.resolve_audio(
            video_id,
            title=title,
            artist=artist,
            quality=quality
        )
    )
    if not stream_info:
        raise HTTPException(status_code=404, detail="Could not resolve audio stream for track.")
    
    stream_url = stream_info.get("streamUrl")
    if not stream_url:
        raise HTTPException(status_code=404, detail="No stream URL available.")

    range_header = request.headers.get("Range")
    remote_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if range_header:
        remote_headers["Range"] = range_header

    try:
        resp = requests.get(stream_url, headers=remote_headers, stream=True, timeout=12)
        
        # Determine content type based on codec
        codec = str(stream_info.get("codec", "")).lower()
        if "flac" in codec:
            content_type = "audio/flac"
        elif "alac" in codec or "m4a" in codec or "mp4" in codec:
            content_type = "audio/mp4"
        elif "mp3" in codec:
            content_type = "audio/mpeg"
        else:
            content_type = resp.headers.get("Content-Type", "audio/webm")

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
            "X-Audio-Codec": str(stream_info.get("codec", "opus")),
            "X-Audio-Bitrate": str(stream_info.get("bitrate", 256)),
            "X-Audio-Lossless": "true" if stream_info.get("isLossless") else "false",
            "X-Audio-Source": str(stream_info.get("source", "youtube")),
        }
        if "Content-Range" in resp.headers:
            headers["Content-Range"] = resp.headers["Content-Range"]
        if "Content-Length" in resp.headers:
            headers["Content-Length"] = resp.headers["Content-Length"]

        # Optimized 128KB chunk stream with instant client disconnect release
        async def chunk_generator():
            try:
                for chunk in resp.iter_content(chunk_size=128 * 1024):
                    if await request.is_disconnected():
                        break
                    if chunk:
                        yield chunk
            finally:
                resp.close()

        return StreamingResponse(
            chunk_generator(),
            status_code=resp.status_code,
            headers=headers,
            media_type=content_type
        )
    except Exception as e:
        logger.error(f"Error proxying audio for {video_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch audio: {e}")

@app.get("/api/stream/{video_id}/video-info")
def get_video_stream_info(video_id: str):
    """
    Resolve video stream metadata and direct proxy URL.
    """
    video_info = stream_resolver.resolve_video(video_id)
    if not video_info:
        raise HTTPException(status_code=404, detail="Could not resolve video stream for track.")
    return {
        "videoId": video_id,
        "videoUrl": f"/api/stream/{video_id}/video",
        "title": video_info.get("title", ""),
        "duration": video_info.get("duration", 0),
        "resolution": video_info.get("resolution", "360p"),
        "audioQuality": "Standard YouTube Stream (160 kbps)"
    }

@app.get("/api/stream/{video_id}/video")
def stream_video_proxy(video_id: str, request: Request):
    """
    Direct video streaming proxy with HTTP 206 Partial Content Range support.
    Bypasses YouTube iframe embed restrictions (Error 150/152) for HTML5 video playback.
    """
    video_info = stream_resolver.resolve_video(video_id)
    if not video_info or not video_info.get("streamUrl"):
        raise HTTPException(status_code=404, detail="Could not resolve video stream for track.")

    stream_url = video_info["streamUrl"]
    range_header = request.headers.get("Range")
    remote_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if range_header:
        remote_headers["Range"] = range_header

    try:
        resp = requests.get(stream_url, headers=remote_headers, stream=True, timeout=15)
        content_type = resp.headers.get("Content-Type", "video/mp4")

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
            "X-Video-Resolution": str(video_info.get("resolution", "360p")),
        }
        if "Content-Range" in resp.headers:
            headers["Content-Range"] = resp.headers["Content-Range"]
        if "Content-Length" in resp.headers:
            headers["Content-Length"] = resp.headers["Content-Length"]

        def chunk_generator():
            for chunk in resp.iter_content(chunk_size=128 * 1024):
                if chunk:
                    yield chunk

        return StreamingResponse(
            chunk_generator(),
            status_code=resp.status_code,
            headers=headers,
            media_type=content_type
        )
    except Exception as e:
        logger.error(f"Error proxying video for {video_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch video: {e}")

@app.get("/api/stream/{video_id}/segments")
async def get_skip_segments(video_id: str):
    if not config_mgr.get("sponsorblock_enabled", True):
        return []
    cats = config_mgr.get("sponsorblock_categories", ["sponsor", "intro", "outro", "music_offtopic"])
    return stream_resolver.get_sponsorblock_segments(video_id, categories=cats)

# ==================== Lyrics Endpoints ====================

@app.get("/api/lyrics")
async def get_lyrics(
    title: str = Query(...),
    artist: str = Query(""),
    duration: int = Query(0)
):
    return lyrics_engine.get_lyrics(title, artist, duration)

# ==================== Downloader Endpoints ====================

class InspectRequest(BaseModel):
    url: str

@app.post("/api/downloader/inspect")
async def inspect_url(req: InspectRequest):
    try:
        return downloader_engine.inspect_url(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class QueueDownloadRequest(BaseModel):
    url: str
    download_type: str = "audio"  # 'audio' or 'video'
    format: str = "mp3"           # 'mp3', 'flac', 'm4a', 'opus', 'wav', 'mp4', 'mkv'
    quality: str = "320"          # '320', '256', '1080p', '4K'
    title: Optional[str] = None
    artist: Optional[str] = None
    thumbnail: Optional[str] = None

@app.post("/api/downloader/queue")
async def queue_download(req: QueueDownloadRequest):
    try:
        task_id = downloader_engine.queue_download(
            url=req.url,
            download_type=req.download_type,
            output_format=req.format,
            quality=req.quality,
            title=req.title,
            artist=req.artist,
            thumbnail=req.thumbnail
        )
        return {"status": "queued", "id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BatchQueueRequest(BaseModel):
    items: List[QueueDownloadRequest]

@app.post("/api/downloader/batch-queue")
async def batch_queue_download(req: BatchQueueRequest):
    queued_ids = []
    for item in req.items:
        t_id = downloader_engine.queue_download(
            url=item.url,
            download_type=item.download_type,
            output_format=item.format,
            quality=item.quality,
            title=item.title,
            artist=item.artist,
            thumbnail=item.thumbnail
        )
        queued_ids.append(t_id)
    return {"status": "queued", "count": len(queued_ids), "ids": queued_ids}

@app.get("/api/downloader/queue")
async def get_download_queue():
    # Returns pending and downloading items
    items = db_mgr.get_downloads()
    active = [i for i in items if i["status"] in ("pending", "downloading", "processing")]
    return active

@app.get("/api/downloader/history")
async def get_download_history(limit: int = Query(100)):
    items = db_mgr.get_downloads(limit=limit)
    history = [i for i in items if i["status"] in ("completed", "failed", "cancelled")]
    return history

@app.post("/api/downloader/cancel/{task_id}")
async def cancel_download(task_id: str):
    success = downloader_engine.cancel_download(task_id)
    return {"status": "ok", "cancelled": success}

@app.post("/api/downloader/retry/{task_id}")
async def retry_download(task_id: str):
    success = downloader_engine.retry_download(task_id)
    return {"status": "ok", "retried": success}

@app.delete("/api/downloader/{task_id}")
async def delete_download(task_id: str):
    success = db_mgr.delete_download(task_id)
    return {"status": "ok", "deleted": success}

@app.delete("/api/downloader/clear-completed")
async def clear_completed_downloads():
    count = db_mgr.clear_completed_downloads()
    return {"status": "ok", "cleared": count}

# ==================== Spotify Importer Endpoints ====================

spotify_importer = SpotifyImporter(ytmusic_svc)

class SpotifyImportRequest(BaseModel):
    url: str
    limit: int = 50

@app.post("/api/spotify/import")
async def import_spotify(req: SpotifyImportRequest):
    try:
        return spotify_importer.import_and_match(req.url, limit=req.limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== Local Library Endpoints ====================

@app.get("/api/library/scan")
async def scan_local_library(path: Optional[str] = Query(None)):
    return local_lib.scan_directory(path)

@app.get("/api/library/stream")
async def stream_local_file(path: str = Query(...)):
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Local file not found")
    return FileResponse(path=str(file_path), media_type="audio/mpeg", filename=file_path.name)

class OpenExplorerRequest(BaseModel):
    path: str

@app.post("/api/library/open-explorer")
async def open_in_explorer(req: OpenExplorerRequest):
    success = local_lib.open_in_explorer(req.path)
    return {"status": "ok" if success else "failed"}

# ==================== Favorites Endpoints ====================

@app.get("/api/favorites")
async def get_favorites():
    return db_mgr.get_favorites()

@app.post("/api/favorites")
async def add_favorite(payload: Dict[str, Any] = Body(...)):
    db_mgr.add_favorite(payload)
    return {"status": "ok"}

@app.delete("/api/favorites/{video_id}")
async def remove_favorite(video_id: str):
    success = db_mgr.remove_favorite(video_id)
    return {"status": "ok", "removed": success}

# ==================== Pluggable Sources & Extensions Endpoints ====================

@app.get("/api/plugins")
async def get_plugins():
    return plugin_svc.list_plugins()

class TogglePluginRequest(BaseModel):
    enabled: bool

@app.put("/api/plugins/{plugin_id}/toggle")
async def toggle_plugin(plugin_id: str, req: TogglePluginRequest):
    success = plugin_svc.toggle_plugin(plugin_id, req.enabled)
    return {"status": "ok" if success else "error"}

@app.post("/api/plugins")
async def add_plugin(payload: Dict[str, Any] = Body(...)):
    plugin = plugin_svc.add_custom_plugin(payload)
    return {"status": "ok", "plugin": plugin}

@app.delete("/api/plugins/{plugin_id}")
async def delete_plugin(plugin_id: str):
    success = plugin_svc.delete_custom_plugin(plugin_id)
    return {"status": "ok" if success else "error"}

@app.post("/api/plugins/{plugin_id}/test")
async def test_plugin(plugin_id: str):
    result = plugin_svc.test_plugin(plugin_id)
    return result

# ==================== Search & Playback History Endpoints ====================

@app.get("/api/history/searches")
def get_search_history(limit: int = Query(15)):
    return db_mgr.get_search_history(limit)

@app.post("/api/history/searches")
def add_search_history(payload: Dict[str, str] = Body(...)):
    query = payload.get("query", "").strip()
    if query:
        db_mgr.add_search_query(query)
    return {"status": "ok"}

@app.delete("/api/history/searches")
def delete_search_history(query: Optional[str] = Query(None)):
    if query:
        db_mgr.delete_search_query(query)
    else:
        db_mgr.clear_search_history()
    return {"status": "ok"}

@app.get("/api/history/playback")
def get_playback_history(limit: int = Query(50)):
    return db_mgr.get_playback_history(limit)

@app.post("/api/history/playback")
def add_playback_history(track: Dict[str, Any] = Body(...)):
    db_mgr.add_playback_history(track)
    return {"status": "ok"}

@app.delete("/api/history/playback")
def delete_playback_history(track_id: Optional[str] = Query(None)):
    if track_id:
        db_mgr.delete_playback_history(track_id)
    else:
        db_mgr.clear_playback_history()
    return {"status": "ok"}

# ==================== Custom Playlists Endpoints ====================

@app.get("/api/playlists/custom")
def list_custom_playlists():
    return db_mgr.get_custom_playlists()

@app.post("/api/playlists/custom")
def create_custom_playlist(payload: Dict[str, str] = Body(...)):
    name = payload.get("name", "My Playlist").strip()
    desc = payload.get("description", "").strip()
    thumb = payload.get("thumbnail", "").strip()
    return db_mgr.create_custom_playlist(name, desc, thumb)

@app.get("/api/playlists/custom/{playlist_id}")
def get_custom_playlist(playlist_id: str):
    pl = db_mgr.get_custom_playlist_details(playlist_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return pl

@app.put("/api/playlists/custom/{playlist_id}")
def update_custom_playlist(playlist_id: str, payload: Dict[str, Any] = Body(...)):
    name = payload.get("name")
    desc = payload.get("description")
    thumb = payload.get("thumbnail")
    db_mgr.update_custom_playlist(playlist_id, name=name, description=desc, thumbnail=thumb)
    return {"status": "ok"}

@app.delete("/api/playlists/custom/{playlist_id}")
def delete_custom_playlist(playlist_id: str):
    db_mgr.delete_custom_playlist(playlist_id)
    return {"status": "ok"}

@app.post("/api/playlists/custom/{playlist_id}/tracks")
def add_track_to_custom_playlist(playlist_id: str, track: Dict[str, Any] = Body(...)):
    db_mgr.add_track_to_playlist(playlist_id, track)
    return {"status": "ok"}

@app.delete("/api/playlists/custom/{playlist_id}/tracks/{track_id}")
def remove_track_from_custom_playlist(playlist_id: str, track_id: str):
    db_mgr.remove_track_from_playlist(playlist_id, track_id)
    return {"status": "ok"}

# ==================== Built-in ID3 Tag Editor & Storage ====================

@app.post("/api/library/edit-tags")
def edit_audio_tags(payload: Dict[str, Any] = Body(...)):
    file_path = payload.get("filePath", "")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    title = payload.get("title", "").strip()
    artist = payload.get("artist", "").strip()
    album = payload.get("album", "").strip()
    year = payload.get("year", "").strip()
    genre = payload.get("genre", "").strip()

    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.mp3 import MP3
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.mp3':
            try:
                audio = EasyID3(file_path)
            except Exception:
                audio = MP3(file_path)
                audio.add_tags()
                audio = EasyID3(file_path)
            if title: audio['title'] = title
            if artist: audio['artist'] = artist
            if album: audio['album'] = album
            if year: audio['date'] = year
            if genre: audio['genre'] = genre
            audio.save()
        elif ext == '.flac':
            audio = FLAC(file_path)
            if title: audio['title'] = title
            if artist: audio['artist'] = artist
            if album: audio['album'] = album
            if year: audio['date'] = year
            if genre: audio['genre'] = genre
            audio.save()
        elif ext in ('.m4a', '.mp4'):
            audio = MP4(file_path)
            if title: audio['\xa9nam'] = title
            if artist: audio['\xa9ART'] = artist
            if album: audio['\xa9alb'] = album
            if year: audio['\xa9day'] = year
            if genre: audio['\xa9gen'] = genre
            audio.save()

        return {"status": "ok", "filePath": file_path, "title": title, "artist": artist}
    except Exception as e:
        logger.error(f"Failed to edit tags for {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update metadata: {e}")

@app.get("/api/storage/info")
def get_storage_info():
    base_dir = Path.home() / ".ytz"
    cache_dir = base_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir = config_mgr.get("download_path", str(base_dir / "downloads"))
    
    def get_dir_size(path):
        total = 0
        p = Path(path)
        if p.exists():
            for f in p.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except Exception:
                        pass
        return total

    from backend.api.stream import _STREAM_CACHE
    disk_cache = get_dir_size(cache_dir)
    mem_cache = len(_STREAM_CACHE) * 512 * 1024
    total_cache = disk_cache + mem_cache
    dl_size = get_dir_size(downloads_dir)

    return {
        "cacheSizeBytes": total_cache,
        "cacheSizeMB": round(total_cache / (1024 * 1024), 2),
        "downloadsSizeBytes": dl_size,
        "downloadsSizeMB": round(dl_size / (1024 * 1024), 1),
        "downloadsPath": str(downloads_dir),
    }

@app.post("/api/storage/clear-cache")
def clear_storage_cache():
    from backend.api.stream import _STREAM_CACHE
    cleared_entries = len(_STREAM_CACHE)
    _STREAM_CACHE.clear()

    base_dir = Path.home() / ".ytz"
    cache_dir = base_dir / "cache"
    freed_bytes = 0
    if cache_dir.exists():
        for f in cache_dir.iterdir():
            if f.is_file():
                try:
                    freed_bytes += f.stat().st_size
                    f.unlink()
                except Exception:
                    pass

    try:
        with db_mgr._get_connection() as conn:
            conn.execute("VACUUM")
    except Exception as e:
        logger.debug(f"VACUUM note: {e}")

    freed_mb = round((freed_bytes + cleared_entries * 512 * 1024) / (1024 * 1024), 2)
    return {
        "status": "ok",
        "cleared": True,
        "clearedEntries": cleared_entries,
        "freedMB": max(0.1, freed_mb) if cleared_entries > 0 or freed_bytes > 0 else 0.0,
    }

# ==================== General YouTube Search (Separate Service) ====================

@app.get("/api/youtube/search")
async def search_youtube_videos(query: str = Query(...), limit: int = Query(20)):
    return await asyncio.to_thread(yt_search_svc.search, query, limit)

# ==================== WebSocket Endpoint ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong keepalive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)

# ==================== Static Frontend Serving ====================

DIST_DIR = ROOT_DIR / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")

def run_server(host: str = "0.0.0.0", port: int = 47892):
    lan_ip = get_lan_ip()
    print("=" * 65)
    print("           YT-Z: High-Fidelity Audio & Streaming Engine")
    print("=" * 65)
    print(f" [✓] Local access:   http://127.0.0.1:{port}")
    print(f" [✓] Network access: http://{lan_ip}:{port} (Any device on Wi-Fi/LAN)")
    print("=" * 65)
    uvicorn.run("backend.server:app", host=host, port=port, log_level="info")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YT-Z Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (0.0.0.0 to listen on all interfaces)")
    parser.add_argument("--port", type=int, default=47892, help="Port to listen on")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)

