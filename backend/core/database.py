"""
SQLite Database manager for YT-Z.
Persists download history, active queue items, and user favorites.
Stored in ~/.ytz/ytz.db
"""
import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("YTZ.Database")

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            config_dir = Path.home() / ".ytz"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = config_dir / "ytz.db"
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Downloads table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                artist TEXT,
                thumbnail TEXT,
                duration INTEGER DEFAULT 0,
                download_type TEXT DEFAULT 'audio',
                format TEXT DEFAULT 'mp3',
                quality TEXT DEFAULT '320',
                status TEXT DEFAULT 'pending',
                progress REAL DEFAULT 0.0,
                speed TEXT DEFAULT '0 MB/s',
                eta TEXT DEFAULT '00:00',
                file_size INTEGER DEFAULT 0,
                file_path TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
            """)

            # Favorites table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                artist TEXT,
                album TEXT,
                thumbnail TEXT,
                duration INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Saved Playlists table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                thumbnail TEXT,
                tracks_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Lyrics Cache table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS lyrics_cache (
                key TEXT PRIMARY KEY,
                lyrics_json TEXT NOT NULL,
                provider TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Pluggable Sources & Extensions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS plugins (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                endpoint TEXT,
                api_key TEXT,
                enabled INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active',
                latency_ms INTEGER DEFAULT 0,
                icon TEXT,
                is_builtin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Search History table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL UNIQUE,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Playback / Listening History table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS playback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                video_id TEXT,
                title TEXT NOT NULL,
                artist TEXT,
                album TEXT,
                thumbnail TEXT,
                duration INTEGER DEFAULT 0,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Custom Playlists table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_playlists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                thumbnail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Custom Playlist Tracks table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id TEXT NOT NULL,
                track_id TEXT NOT NULL,
                video_id TEXT,
                title TEXT NOT NULL,
                artist TEXT,
                album TEXT,
                thumbnail TEXT,
                duration TEXT,
                duration_seconds INTEGER DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES custom_playlists(id) ON DELETE CASCADE
            );
            """)

            conn.commit()

    # ---- Download Operations ----

    def add_download(self, item: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO downloads (
                id, url, title, artist, thumbnail, duration, download_type,
                format, quality, status, progress, speed, eta, file_size,
                file_path, error_message, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["id"], item["url"], item.get("title", "Unknown"),
                item.get("artist", ""), item.get("thumbnail", ""),
                item.get("duration", 0), item.get("download_type", "audio"),
                item.get("format", "mp3"), item.get("quality", "320"),
                item.get("status", "pending"), item.get("progress", 0.0),
                item.get("speed", "0 MB/s"), item.get("eta", "00:00"),
                item.get("file_size", 0), item.get("file_path", None),
                item.get("error_message", None),
                item.get("created_at", datetime.now().isoformat()),
                item.get("completed_at", None)
            ))
            conn.commit()

    def update_download(self, download_id: str, updates: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for k, v in updates.items():
                fields.append(f"{k} = ?")
                values.append(v)
            if not fields:
                return
            values.append(download_id)
            query = f"UPDATE downloads SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, tuple(values))
            conn.commit()

    def get_download(self, download_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads WHERE id = ?", (download_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_downloads(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM downloads WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM downloads ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_download(self, download_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_completed_downloads(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads WHERE status IN ('completed', 'failed', 'cancelled')")
            conn.commit()
            return cursor.rowcount

    # ---- Favorites Operations ----

    def add_favorite(self, track: Dict[str, Any]) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            track_id = track.get("id") or track.get("video_id")
            cursor.execute("""
            INSERT OR REPLACE INTO favorites (id, video_id, title, artist, album, thumbnail, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id, track_id, track.get("title", ""), track.get("artist", ""),
                track.get("album", ""), track.get("thumbnail", ""), track.get("duration", 0)
            ))
            conn.commit()
            return True

    def remove_favorite(self, video_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM favorites WHERE video_id = ? OR id = ?", (video_id, video_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_favorites(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM favorites ORDER BY added_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def is_favorite(self, video_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM favorites WHERE video_id = ? OR id = ?", (video_id, video_id))
            return cursor.fetchone() is not None

    # ---- Lyrics Cache Operations ----

    def get_cached_lyrics(self, key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT lyrics_json, provider FROM lyrics_cache WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return {
                    "lyrics": json.loads(row["lyrics_json"]),
                    "provider": row["provider"]
                }
            return None

    def cache_lyrics(self, key: str, lyrics: Any, provider: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO lyrics_cache (key, lyrics_json, provider, cached_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(lyrics), provider))
            conn.commit()

    # ---- Plugins & Pluggable Sources Operations ----

    def get_all_plugins(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plugins ORDER BY is_builtin DESC, type ASC, name ASC")
            return [dict(r) for r in cursor.fetchall()]

    def upsert_plugin(self, plugin: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO plugins (
                id, name, type, description, endpoint, api_key,
                enabled, status, latency_ms, icon, is_builtin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plugin["id"], plugin["name"], plugin["type"],
                plugin.get("description", ""), plugin.get("endpoint", ""),
                plugin.get("api_key", ""), 1 if plugin.get("enabled", True) else 0,
                plugin.get("status", "active"), plugin.get("latency_ms", 0),
                plugin.get("icon", "Puzzle"), 1 if plugin.get("is_builtin", False) else 0
            ))
            conn.commit()

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE plugins SET enabled = ? WHERE id = ?", (1 if enabled else 0, plugin_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_plugin(self, plugin_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plugins WHERE id = ? AND is_builtin = 0", (plugin_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_plugin_status(self, plugin_id: str, status: str, latency_ms: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE plugins SET status = ?, latency_ms = ? WHERE id = ?", (status, latency_ms, plugin_id))
            conn.commit()

    # ---- Search History Operations ----

    def add_search_query(self, query: str) -> None:
        q = query.strip()
        if not q:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO search_history (query, searched_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(query) DO UPDATE SET searched_at = CURRENT_TIMESTAMP
            """, (q,))
            # Keep latest 50 queries
            cursor.execute("""
            DELETE FROM search_history WHERE id NOT IN (
                SELECT id FROM search_history ORDER BY searched_at DESC LIMIT 50
            )
            """)
            conn.commit()

    def get_search_history(self, limit: int = 15) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT query FROM search_history ORDER BY searched_at DESC LIMIT ?",
                (limit,)
            )
            return [row["query"] for row in cursor.fetchall()]

    def delete_search_query(self, query: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM search_history WHERE query = ?", (query,))
            conn.commit()

    def clear_search_history(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM search_history")
            conn.commit()

    # ---- Playback History Operations ----

    def add_playback_history(self, track: Dict[str, Any]) -> None:
        t_id = track.get("id") or track.get("videoId")
        if not t_id:
            return
        title = track.get("title") or "Unknown Track"
        artist = track.get("artist") or ""
        album = track.get("album") or ""
        thumbnail = track.get("thumbnail") or ""
        duration = track.get("durationSeconds") or track.get("duration") or 0
        if isinstance(duration, str):
            try:
                parts = [int(p) for p in duration.split(":")]
                duration = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
            except Exception:
                duration = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playback_history WHERE track_id = ?", (t_id,))
            cursor.execute("""
            INSERT INTO playback_history (track_id, video_id, title, artist, album, thumbnail, duration, played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (t_id, track.get("videoId", t_id), title, artist, album, thumbnail, duration))
            # Keep latest 100 history tracks
            cursor.execute("""
            DELETE FROM playback_history WHERE id NOT IN (
                SELECT id FROM playback_history ORDER BY played_at DESC LIMIT 100
            )
            """)
            conn.commit()

    def get_playback_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT track_id as id, video_id as videoId, title, artist, album, thumbnail, duration, played_at
            FROM playback_history ORDER BY played_at DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def delete_playback_history(self, track_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playback_history WHERE track_id = ?", (track_id,))
            conn.commit()

    def clear_playback_history(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM playback_history")
            conn.commit()

    # ---- Custom Playlist Operations ----

    def create_custom_playlist(self, name: str, description: str = "", thumbnail: str = "") -> Dict[str, Any]:
        p_id = f"pl_{int(time.time() * 1000)}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO custom_playlists (id, name, description, thumbnail)
            VALUES (?, ?, ?, ?)
            """, (p_id, name, description, thumbnail))
            conn.commit()
        return {"id": p_id, "name": name, "description": description, "thumbnail": thumbnail, "trackCount": 0}

    def get_custom_playlists(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT p.id, p.name, p.description, p.thumbnail, p.created_at,
                   COUNT(t.id) as trackCount
            FROM custom_playlists p
            LEFT JOIN custom_playlist_tracks t ON p.id = t.playlist_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_custom_playlist_details(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, thumbnail, created_at FROM custom_playlists WHERE id = ?", (playlist_id,))
            row = cursor.fetchone()
            if not row:
                return None
            pl = dict(row)
            cursor.execute("""
            SELECT track_id as id, video_id as videoId, title, artist, album, thumbnail, duration, duration_seconds as durationSeconds, added_at
            FROM custom_playlist_tracks
            WHERE playlist_id = ?
            ORDER BY id ASC
            """, (playlist_id,))
            pl["tracks"] = [dict(r) for r in cursor.fetchall()]
            pl["trackCount"] = len(pl["tracks"])
            return pl

    def delete_custom_playlist(self, playlist_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_playlist_tracks WHERE playlist_id = ?", (playlist_id,))
            cursor.execute("DELETE FROM custom_playlists WHERE id = ?", (playlist_id,))
            conn.commit()

    def add_track_to_playlist(self, playlist_id: str, track: Dict[str, Any]) -> None:
        t_id = track.get("id") or track.get("videoId")
        if not t_id:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO custom_playlist_tracks (playlist_id, track_id, video_id, title, artist, album, thumbnail, duration, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                playlist_id, t_id, track.get("videoId", t_id),
                track.get("title", "Track"), track.get("artist", ""),
                track.get("album", ""), track.get("thumbnail", ""),
                str(track.get("duration", "0:00")), int(track.get("durationSeconds", 0) or 0)
            ))
            # Update thumbnail of playlist to first track thumbnail if none
            cursor.execute("""
            UPDATE custom_playlists SET thumbnail = ?
            WHERE id = ? AND (thumbnail IS NULL OR thumbnail = '')
            """, (track.get("thumbnail", ""), playlist_id))
            conn.commit()

    def remove_track_from_playlist(self, playlist_id: str, track_id: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_playlist_tracks WHERE playlist_id = ? AND track_id = ?", (playlist_id, track_id))
            conn.commit()
