"""
YouTube Music API Service for YT-Z.
Integrates with InnerTube / ytmusicapi to provide full music discovery,
search, charts, mood categories, and radio recommendation.
"""
import random
import logging
from typing import Dict, Any, List, Optional
from ytmusicapi import YTMusic

logger = logging.getLogger("YTZ.YTMusic")

class YTMusicService:
    def __init__(self, location: str = "IN", language: str = "en"):
        self.default_country = location
        self._quick_picks_cache: List[Dict[str, Any]] = []
        try:
            self.yt = YTMusic(language=language, location=location)
            logger.info(f"Initialized YTMusic anonymous client (location={location}, language={language})")
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

        # Check author field if artist_names is empty
        author_val = item.get("author") or item.get("uploader")
        if not artist_names and author_val:
            if isinstance(author_val, str):
                artist_names.append(author_val)
            elif isinstance(author_val, dict):
                n = author_val.get("name")
                if n:
                    artist_names.append(n)
            elif isinstance(author_val, list):
                for a in author_val:
                    if isinstance(a, dict) and a.get("name"):
                        artist_names.append(a["name"])
                    elif isinstance(a, str):
                        artist_names.append(a)

        artist_str = ", ".join(artist_names) if artist_names else "YouTube Music"

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
        if not thumbnail and video_id and len(video_id) == 11 and not any(c in video_id for c in " /\\?&=#"):
            thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

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

    def get_quick_picks(self, refresh: bool = False, mood: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch varied, dynamically refreshed quick picks.
        If refresh=True or cache is empty, gathers candidates from YouTube Music's
        Quick picks section, Top Charts, and trending genres, and yields a fresh shuffled selection.
        """
        if refresh or not self._quick_picks_cache or (mood and mood.lower() != "all"):
            candidates = []
            seen_ids = set()

            # 1. If mood is requested, query mood / genre
            if mood and mood.lower() != "all":
                try:
                    search_results = self.search(f"{mood} hits songs", filter_type="songs")
                    for t in search_results:
                        vid = t.get("videoId") or t.get("id")
                        if vid and vid not in seen_ids:
                            seen_ids.add(vid)
                            candidates.append(t)
                except Exception as ex:
                    logger.debug(f"Mood quick picks search failed: {ex}")

            # 2. Get songs from home feed Quick picks
            try:
                home_data = self.yt.get_home(limit=8)
                for sec in home_data:
                    title = sec.get("title", "").lower()
                    if any(k in title for k in ("quick", "picks", "songs", "tracks")):
                        for item in sec.get("contents", []):
                            vid = item.get("videoId")
                            if vid and vid not in seen_ids:
                                seen_ids.add(vid)
                                candidates.append(self._normalize_track(item))
            except Exception as e:
                logger.debug(f"Error fetching home quick picks pool: {e}")

            # 3. Add Top Charts songs to broaden variety
            try:
                charts = self.get_charts(country=self.default_country)
                for s in charts.get("songs", []):
                    vid = s.get("videoId") or s.get("id")
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        candidates.append(s)
            except Exception as e:
                logger.debug(f"Error fetching charts pool: {e}")

            if candidates:
                self._quick_picks_cache = candidates

        pool = list(self._quick_picks_cache)
        if not pool:
            return []

        # Return a randomized sample
        count = min(limit, len(pool))
        return random.sample(pool, count)

    def get_home(self) -> List[Dict[str, Any]]:
        """Fetch personalized / trending home feed sections"""
        if not self.yt:
            return []
        try:
            home_data = self.yt.get_home(limit=8)
            sections = []
            for section in home_data:
                title = section.get("title", "")
                contents = section.get("contents", [])
                items = []

                if "quick" in title.lower():
                    fresh_picks = self.get_quick_picks(refresh=False, limit=10)
                    if fresh_picks:
                        items = fresh_picks

                if not items:
                    for item in contents:
                        video_id = item.get("videoId")
                        if video_id:
                            items.append(self._normalize_track(item))
                        else:
                            # Playlist or Album item in home
                            browse_id = item.get("browseId") or item.get("playlistId") or ""
                            is_playlist = (
                                browse_id.startswith("RDCL") or
                                browse_id.startswith("PL") or
                                browse_id.startswith("VL") or
                                browse_id.startswith("RD") or
                                "playlist" in str(browse_id).lower()
                            )
                            items.append({
                                "id": browse_id,
                                "browseId": browse_id,
                                "title": item.get("title", ""),
                                "subtitle": item.get("description") or (", ".join([a.get("name", "") for a in item.get("artists", []) if isinstance(a, dict)]) if item.get("artists") else ""),
                                "thumbnail": self._normalize_thumbnail(item.get("thumbnails")),
                                "type": "playlist" if is_playlist else "album"
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

    def get_charts(self, country: str = "IN") -> Dict[str, Any]:
        """Fetch Top Charts: Top Songs, Top Videos, Top Artists"""
        if not self.yt:
            return {"songs": [], "videos": [], "artists": []}
        try:
            charts = self.yt.get_charts(country=country)
            
            # 1. Parse Artists
            artists = []
            raw_artists = charts.get("artists")
            if isinstance(raw_artists, dict):
                raw_artists = raw_artists.get("items", [])
            if isinstance(raw_artists, list):
                for a in raw_artists:
                    if isinstance(a, dict):
                        artists.append({
                            "id": a.get("browseId", ""),
                            "name": a.get("title", ""),
                            "thumbnail": self._normalize_thumbnail(a.get("thumbnails")),
                            "rank": a.get("rank", ""),
                            "subscribers": a.get("subscribers", "")
                        })

            # 2. Parse Songs / Videos from charts playlists
            songs = []
            videos = []
            raw_videos = charts.get("videos")
            if isinstance(raw_videos, dict):
                raw_videos = raw_videos.get("items", [])

            # If videos is a list of playlists (e.g. Daily Top Music Videos)
            if isinstance(raw_videos, list) and len(raw_videos) > 0:
                first_pl = raw_videos[0]
                if isinstance(first_pl, dict) and first_pl.get("playlistId"):
                    try:
                        pl_data = self.get_playlist(first_pl["playlistId"])
                        all_tracks = pl_data.get("tracks", [])
                        songs = all_tracks[:30]
                        videos = all_tracks[30:60] if len(all_tracks) > 30 else all_tracks[:30]
                    except Exception as ex:
                        logger.debug(f"Failed to fetch charts playlist: {ex}")
                elif isinstance(first_pl, dict) and (first_pl.get("videoId") or first_pl.get("id")):
                    videos = [self._normalize_track(v) for v in raw_videos if isinstance(v, dict)]

            # If songs still empty, query top songs playlist or search
            if not songs:
                try:
                    fallback_pl = self.get_playlist("PL4fGSI1pDJn6t3TXLGiiJdD-sZbrG3tG0")
                    songs = fallback_pl.get("tracks", [])[:30]
                except Exception:
                    songs = self.search("Top Hits 2026", filter_type="songs")[:20]

            return {
                "songs": songs,
                "videos": videos if videos else songs[:15],
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
                    artist_title = item.get("artist") or item.get("title", "")
                    artist_id = item.get("browseId") or ""
                    if (not artist_title or not artist_id) and item.get("artists"):
                        raw_a = item["artists"]
                        if isinstance(raw_a, list) and len(raw_a) > 0:
                            first_a = raw_a[0]
                            if isinstance(first_a, dict):
                                if not artist_title:
                                    artist_title = first_a.get("name", "")
                                if not artist_id:
                                    artist_id = first_a.get("id", "")
                            elif isinstance(first_a, str) and not artist_title:
                                artist_title = first_a

                    items.append({
                        "id": artist_id,
                        "browseId": artist_id,
                        "resultType": "artist",
                        "title": artist_title or query.strip(),
                        "thumbnail": self._normalize_thumbnail(item.get("thumbnails")),
                        "subscribers": str(item.get("subscribers") or "")
                    })
                elif cat in ("album", "playlist"):
                    album_title = item.get("title", "")
                    if isinstance(album_title, dict):
                        album_title = album_title.get("text", "")

                    raw_artists = item.get("artists", [])
                    artist_names = []
                    if isinstance(raw_artists, list):
                        for a in raw_artists:
                            if isinstance(a, dict):
                                name = a.get("name")
                                if name:
                                    artist_names.append(name)
                            elif isinstance(a, str):
                                artist_names.append(a)

                    author_field = item.get("author")
                    if isinstance(author_field, dict):
                        author_field = author_field.get("name", "")
                    elif isinstance(author_field, list):
                        author_field = ", ".join([x.get("name", "") if isinstance(x, dict) else str(x) for x in author_field])

                    artist_str = ", ".join(artist_names) if artist_names else (str(author_field) if author_field else "YouTube Music")

                    items.append({
                        "id": item.get("browseId") or item.get("playlistId") or "",
                        "browseId": item.get("browseId") or item.get("playlistId") or "",
                        "resultType": cat,
                        "title": album_title or "Untitled Collection",
                        "artist": artist_str,
                        "year": str(item.get("year") or ""),
                        "thumbnail": self._normalize_thumbnail(item.get("thumbnails")),
                        "itemCount": str(item.get("itemCount") or "")
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
        """Fetch album details and track list with auto-fallback to playlist"""
        if not self.yt or not browse_id:
            return {}
        # If browse_id is actually a playlist (RDCL, PL, VL, RD)
        if any(browse_id.startswith(p) for p in ("RDCL", "PL", "VL", "RD")):
            return self.get_playlist(browse_id)
        try:
            album_data = self.yt.get_album(browse_id)
            tracks = [self._normalize_track(t) for t in album_data.get("tracks", []) if t.get("videoId") or t.get("id")]
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
            logger.debug(f"get_album failed for {browse_id}, trying get_playlist: {e}")
            pl_result = self.get_playlist(browse_id)
            if pl_result and pl_result.get("tracks"):
                return pl_result
            logger.error(f"Error fetching album {browse_id}: {e}")
            return {}

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Fetch playlist details and track list with auto-fallback to album"""
        if not self.yt or not playlist_id:
            return {}
        # If playlist_id is actually an album browse ID (MPREb_)
        if playlist_id.startswith("MPREb_"):
            return self.get_album(playlist_id)
        try:
            pl_data = self.yt.get_playlist(playlist_id)
            tracks = [self._normalize_track(t) for t in pl_data.get("tracks", []) if t.get("videoId") or t.get("id")]
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
            logger.debug(f"get_playlist failed for {playlist_id}, trying get_album: {e}")
            album_result = self.get_album(playlist_id)
            if album_result and album_result.get("tracks"):
                return album_result
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
