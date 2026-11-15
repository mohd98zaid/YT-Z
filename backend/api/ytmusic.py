"""
YouTube Music API Service for YT-Z.
Integrates with InnerTube / ytmusicapi to provide full music discovery,
search, charts, mood categories, and radio recommendation.
"""
import logging
from typing import Dict, Any, List, Optional
from ytmusicapi import YTMusic

logger = logging.getLogger("YTZ.YTMusic")

class YTMusicService:
    def __init__(self):
        try:
            self.yt = YTMusic()
            logger.info("Initialized YTMusic anonymous client")
        except Exception as e:
            logger.error(f"Failed to initialize YTMusic client: {e}")
            self.yt = None

    def _normalize_thumbnail(self, thumbnails: Any) -> str:
        if not thumbnails:
            return ""
        if isinstance(thumbnails, list) and len(thumbnails) > 0:
            # Pick highest resolution thumbnail
            best = sorted(thumbnails, key=lambda x: x.get("width", 0), reverse=True)[0]
            url = best.get("url", "")
            # Upgrade resolution if YouTube thumbnail format
            if "=w" in url and "-h" in url:
                url = url.split("=")[0] + "=w500-h500-l90-rj"
            return url
        if isinstance(thumbnails, str):
            return thumbnails
        return ""

    def _normalize_track(self, item: Dict[str, Any]) -> Dict[str, Any]:
        video_id = item.get("videoId") or item.get("id") or ""
        title = item.get("title") or "Unknown Title"
        if isinstance(title, dict):
            title = title.get("text", "")

        # Extract artists
        artists_data = item.get("artists") or []
        artist_names = []
        artist_id = ""
        if isinstance(artists_data, list):
            for a in artists_data:
                if isinstance(a, dict):
                    name = a.get("name")
                    if name:
                        artist_names.append(name)
                    if not artist_id and a.get("id"):
                        artist_id = a.get("id")
                elif isinstance(a, str):
                    artist_names.append(a)
        artist_str = ", ".join(artist_names) if artist_names else (item.get("author") or "Unknown Artist")

        # Extract album
        album_data = item.get("album")
        album_name = ""
        album_id = ""
        if isinstance(album_data, dict):
            album_name = album_data.get("name", "")
            album_id = album_data.get("id", "")
        elif isinstance(album_data, str):
            album_name = album_data

        # Duration
        duration = item.get("duration") or item.get("length") or "0:00"
        duration_seconds = item.get("duration_seconds") or 0
        if not duration_seconds and isinstance(duration, str):
            parts = duration.split(":")
            try:
                if len(parts) == 2:
                    duration_seconds = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except ValueError:
                duration_seconds = 0

        thumbnail = self._normalize_thumbnail(item.get("thumbnails"))

        return {
            "id": video_id,
            "videoId": video_id,
            "title": title,
            "artist": artist_str,
            "artistId": artist_id,
            "album": album_name,
            "albumId": album_id,
            "duration": duration,
            "durationSeconds": duration_seconds,
            "thumbnail": thumbnail,
            "isExplicit": item.get("isExplicit", False),
        }

    def get_home(self) -> List[Dict[str, Any]]:
        """Fetch personalized / trending home feed sections"""
        if not self.yt:
            return []
        try:
            home_data = self.yt.get_home(limit=6)
            sections = []
            for section in home_data:
                title = section.get("title", "")
                contents = section.get("contents", [])
                items = []
                for item in contents:
                    video_id = item.get("videoId")
                    if video_id:
                        items.append(self._normalize_track(item))
                    else:
                        # Playlist or Album item in home
                        browse_id = item.get("browseId") or item.get("playlistId")
                        items.append({
                            "id": browse_id,
                            "browseId": browse_id,
                            "title": item.get("title", ""),
                            "subtitle": item.get("description") or (", ".join([a.get("name", "") for a in item.get("artists", []) if isinstance(a, dict)]) if item.get("artists") else ""),
                            "thumbnail": self._normalize_thumbnail(item.get("thumbnails")),
                            "type": "playlist" if "playlist" in str(browse_id).lower() or "vl" in str(browse_id).lower() else "album"
                        })
                if items:
                    sections.append({
                        "title": title,
                        "items": items
                    })
            return sections
        except Exception as e:
            logger.error(f"Error fetching home feed: {e}")
            return []

    def get_charts(self, country: str = "US") -> Dict[str, Any]:
        """Fetch Top Charts: Top Songs, Top Videos, Top Artists"""
        if not self.yt:
            return {"songs": [], "videos": [], "artists": []}
        try:
            charts = self.yt.get_charts(country=country)
            songs = [self._normalize_track(s) for s in charts.get("songs", {}).get("items", [])]
            videos = [self._normalize_track(v) for v in charts.get("videos", {}).get("items", [])]
            artists = []
            for a in charts.get("artists", {}).get("items", []):
                artists.append({
                    "id": a.get("browseId", ""),
                    "name": a.get("title", ""),
                    "thumbnail": self._normalize_thumbnail(a.get("thumbnails")),
                    "rank": a.get("rank", ""),
                    "subscribers": a.get("subscribers", "")
                })
            return {
                "songs": songs,
                "videos": videos,
                "artists": artists
            }
        except Exception as e:
            logger.error(f"Error fetching charts: {e}")
            return {"songs": [], "videos": [], "artists": []}

    def get_mood_categories(self) -> Dict[str, List[Dict[str, str]]]:
        """Fetch mood and genre categories (Moods, Genres, Moments)"""
        if not self.yt:
            return {}
        try:
            return self.yt.get_mood_categories()
        except Exception as e:
            logger.error(f"Error fetching mood categories: {e}")
            return {}

    def get_mood_playlists(self, params: str) -> List[Dict[str, Any]]:
        """Fetch playlists for a given mood/genre category parameter"""
        if not self.yt:
            return []
        try:
            playlists = self.yt.get_mood_playlists(params)
            results = []
            for p in playlists:
                results.append({
                    "id": p.get("playlistId"),
                    "title": p.get("title"),
                    "description": p.get("description"),
                    "thumbnail": self._normalize_thumbnail(p.get("thumbnails")),
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching mood playlists: {e}")
            return []

    def search(self, query: str, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search YouTube Music.
        filter_type: 'songs', 'videos', 'albums', 'artists', 'playlists', or None
        """
        if not self.yt or not query.strip():
            return []
        try:
            # ytmusicapi filters: songs, videos, albums, artists, playlists
            results = self.yt.search(query.strip(), filter=filter_type)
            items = []
            for item in results:
                cat = item.get("resultType") or filter_type or "song"
                if cat in ("song", "video"):
                    track = self._normalize_track(item)
                    track["resultType"] = cat
                    items.append(track)
                elif cat == "artist":
                    items.append({
                        "id": item.get("browseId"),
                        "resultType": "artist",
                        "title": item.get("artist") or item.get("title", ""),
                        "thumbnail": self._normalize_thumbnail(item.get("thumbnails")),
                        "subscribers": item.get("subscribers", "")
                    })
                elif cat in ("album", "playlist"):
                    items.append({
                        "id": item.get("browseId") or item.get("playlistId"),
                        "resultType": cat,
                        "title": item.get("title", ""),
                        "artist": ", ".join([a.get("name", "") for a in item.get("artists", [])]) if item.get("artists") else (item.get("author") or ""),
                        "year": item.get("year", ""),
                        "thumbnail": self._normalize_thumbnail(item.get("thumbnails")),
                        "itemCount": item.get("itemCount", "")
                    })
            return items
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}")
            return []

    def get_search_suggestions(self, query: str) -> List[str]:
        """Fetch search query auto-completions"""
        if not self.yt or not query.strip():
            return []
        try:
            return self.yt.get_search_suggestions(query.strip())
        except Exception as e:
            logger.error(f"Search suggestions error: {e}")
            return []

    def get_artist(self, channel_id: str) -> Dict[str, Any]:
        """Fetch artist profile, top tracks, albums, singles"""
        if not self.yt:
            return {}
        try:
            artist_data = self.yt.get_artist(channel_id)
            top_songs = [self._normalize_track(s) for s in artist_data.get("songs", {}).get("results", [])]
            albums = []
            for a in artist_data.get("albums", {}).get("results", []):
                albums.append({
                    "id": a.get("browseId"),
                    "title": a.get("title"),
                    "year": a.get("year"),
                    "thumbnail": self._normalize_thumbnail(a.get("thumbnails"))
                })
            singles = []
            for s in artist_data.get("singles", {}).get("results", []):
                singles.append({
                    "id": s.get("browseId"),
                    "title": s.get("title"),
                    "year": s.get("year"),
                    "thumbnail": self._normalize_thumbnail(s.get("thumbnails"))
                })
            return {
                "id": channel_id,
                "name": artist_data.get("name", ""),
                "description": artist_data.get("description", ""),
                "thumbnail": self._normalize_thumbnail(artist_data.get("thumbnails")),
                "subscribers": artist_data.get("subscribers", ""),
                "topSongs": top_songs,
                "albums": albums,
                "singles": singles
            }
        except Exception as e:
            logger.error(f"Error fetching artist {channel_id}: {e}")
            return {}

    def get_album(self, browse_id: str) -> Dict[str, Any]:
        """Fetch album details and track list"""
        if not self.yt:
            return {}
        try:
            album_data = self.yt.get_album(browse_id)
            tracks = [self._normalize_track(t) for t in album_data.get("tracks", [])]
            return {
                "id": browse_id,
                "title": album_data.get("title", ""),
                "artist": ", ".join([a.get("name", "") for a in album_data.get("artists", [])]) if album_data.get("artists") else "",
                "year": album_data.get("year", ""),
                "thumbnail": self._normalize_thumbnail(album_data.get("thumbnails")),
                "description": album_data.get("description", ""),
                "trackCount": album_data.get("trackCount", len(tracks)),
                "duration": album_data.get("duration", ""),
                "tracks": tracks
            }
        except Exception as e:
            logger.error(f"Error fetching album {browse_id}: {e}")
            return {}

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Fetch playlist details and track list"""
        if not self.yt:
            return {}
        try:
            pl_data = self.yt.get_playlist(playlist_id)
            tracks = [self._normalize_track(t) for t in pl_data.get("tracks", [])]
            return {
                "id": playlist_id,
                "title": pl_data.get("title", ""),
                "author": pl_data.get("author", {}).get("name", "") if isinstance(pl_data.get("author"), dict) else "",
                "description": pl_data.get("description", ""),
                "thumbnail": self._normalize_thumbnail(pl_data.get("thumbnails")),
                "trackCount": pl_data.get("trackCount", len(tracks)),
                "tracks": tracks
            }
        except Exception as e:
            logger.error(f"Error fetching playlist {playlist_id}: {e}")
            return {}

    def get_watch_playlist(self, video_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch auto-generated radio / Up Next queue for a song"""
        if not self.yt:
            return []
        try:
            watch_data = self.yt.get_watch_playlist(videoId=video_id, limit=limit)
            tracks = []
            for t in watch_data.get("tracks", []):
                norm = self._normalize_track(t)
                if norm["id"] != video_id:  # Exclude current song
                    tracks.append(norm)
            return tracks
        except Exception as e:
            logger.error(f"Error fetching watch playlist for {video_id}: {e}")
            return []
