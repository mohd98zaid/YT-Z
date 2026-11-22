"""
Spotify Playlist & Album Importer for YT-Z.
Extracts tracks from Spotify URLs or pasted text and matches them
against YouTube Music to enable instant streaming or 1-click batch downloading.
"""
import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
import requests
from backend.api.ytmusic import YTMusicService
from backend.core.database import DatabaseManager

logger = logging.getLogger("YTZ.SpotifyImporter")

class SpotifyImporter:
    def __init__(self, ytmusic_service: YTMusicService, db: Optional[DatabaseManager] = None):
        self.yt = ytmusic_service
        self.db = db

    def extract_spotify_id(self, url_or_uri: str) -> Dict[str, str]:
        """Extract type ('playlist', 'album', 'track') and ID from Spotify link"""
        url = url_or_uri.strip()
        # Handle spotify:playlist:xxxx
        uri_match = re.match(r"spotify:(playlist|album|track):([a-zA-Z0-9]+)", url)
        if uri_match:
            return {"type": uri_match.group(1), "id": uri_match.group(2)}

        # Handle https://open.spotify.com/playlist/xxxx?si=...
        url_match = re.search(r"open\.spotify\.com\/(playlist|album|track)\/([a-zA-Z0-9]+)", url)
        if url_match:
            return {"type": url_match.group(1), "id": url_match.group(2)}

        return {}

    def fetch_spotify_tracks(self, url_or_id: str) -> Dict[str, Any]:
        """Fetch track listings from Spotify public embed page"""
        info = self.extract_spotify_id(url_or_id)
        if not info:
            raise ValueError("Invalid Spotify URL or URI format.")

        item_type = info["type"]
        item_id = info["id"]
        embed_url = f"https://open.spotify.com/embed/{item_type}/{item_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            resp = requests.get(embed_url, headers=headers, timeout=8)
            if resp.status_code != 200:
                raise ValueError(f"Spotify embed returned HTTP {resp.status_code}")

            # Extract __NEXT_DATA__ JSON from HTML
            pattern = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)
            match = pattern.search(resp.text)
            if not match:
                # Try fallback regex for entity data
                raise ValueError("Could not extract Spotify embed metadata.")

            data = json.loads(match.group(1))
            props = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {})
            entity = props.get("entity", {})

            title = entity.get("title") or "Spotify Playlist"
            subtitle = entity.get("subtitle") or ""
            cover_art = ""
            cover_art_list = entity.get("coverArt", {}).get("sources", [])
            if cover_art_list:
                cover_art = cover_art_list[-1].get("url", "")

            raw_tracks = entity.get("trackList", [])
            parsed_tracks = []
            for t in raw_tracks:
                t_title = t.get("title", "").strip()
                t_artist = t.get("subtitle", "").strip()
                t_duration = t.get("duration", 0) // 1000  # seconds
                if t_title:
                    parsed_tracks.append({
                        "title": t_title,
                        "artist": t_artist,
                        "duration": t_duration
                    })

            return {
                "title": title,
                "subtitle": subtitle,
                "coverArt": cover_art,
                "totalTracks": len(parsed_tracks),
                "tracks": parsed_tracks
            }

        except Exception as e:
            logger.error(f"Error fetching Spotify embed tracks: {e}")
            raise

    def match_track_on_ytmusic(self, title: str, artist: str) -> Optional[Dict[str, Any]]:
        """Search YouTube Music for the best matching track"""
        clean_title = title.replace("\xa0", " ").strip()
        clean_artist = artist.replace("\xa0", " ").split(",")[0].split("&")[0].strip()
        query = f"{clean_title} {clean_artist}".strip()
        results = self.yt.search(query, filter_type="songs")
        if results:
            return results[0]
        # Fallback without artist filter or general search
        results = self.yt.search(f"{clean_title} {artist}".strip())
        if results:
            return results[0]
        return None

    def import_and_match(
        self,
        spotify_url: str,
        limit: int = 150,
        save_to_library: bool = True
    ) -> Dict[str, Any]:
        """Import playlist from Spotify, match tracks concurrently, and auto-save to My Playlists"""
        spotify_data = self.fetch_spotify_tracks(spotify_url)
        tracks = spotify_data.get("tracks", [])[:limit]

        # Parallelize YouTube Music matching for speed (8 concurrent workers)
        def _match_single(idx: int, t: Dict[str, Any]) -> tuple:
            match = self.match_track_on_ytmusic(t["title"], t["artist"])
            if match:
                return idx, {
                    "spotifyTitle": t["title"],
                    "spotifyArtist": t["artist"],
                    "videoId": match["id"],
                    "id": match["id"],
                    "title": match["title"],
                    "artist": match["artist"],
                    "thumbnail": match["thumbnail"],
                    "duration": match.get("duration", "0:00"),
                    "durationSeconds": match.get("durationSeconds", t["duration"]),
                    "matched": True
                }
            else:
                return idx, {
                    "spotifyTitle": t["title"],
                    "spotifyArtist": t["artist"],
                    "videoId": "",
                    "id": "",
                    "title": t["title"],
                    "artist": t["artist"],
                    "thumbnail": "",
                    "duration": "0:00",
                    "durationSeconds": t["duration"],
                    "matched": False
                }

        matched_tracks_indexed = []
        with ThreadPoolExecutor(max_workers=min(8, max(2, len(tracks)))) as executor:
            futures = [executor.submit(_match_single, idx, t) for idx, t in enumerate(tracks)]
            for fut in futures:
                try:
                    matched_tracks_indexed.append(fut.result())
                except Exception as e:
                    logger.debug(f"Track match error: {e}")

        # Sort back to preserve original Spotify playlist sequence
        matched_tracks_indexed.sort(key=lambda x: x[0])
        matched_tracks = [x[1] for x in matched_tracks_indexed]

        # Auto-save playlist into custom_playlists if requested and database is available
        saved_playlist_id = None
        if save_to_library and self.db:
            try:
                playlist_title = spotify_data["title"]
                cover_art = spotify_data.get("coverArt", "")
                
                # Check if a custom playlist with this name already exists
                existing_pls = self.db.get_custom_playlists()
                target_pl = next(
                    (p for p in existing_pls if p.get("name", "").strip().lower() == playlist_title.strip().lower()),
                    None
                )

                if target_pl:
                    saved_playlist_id = target_pl["id"]
                    # Optionally update thumbnail if not set
                    if not target_pl.get("thumbnail") and cover_art:
                        self.db.update_custom_playlist(saved_playlist_id, thumbnail=cover_art)
                else:
                    new_pl = self.db.create_custom_playlist(
                        name=playlist_title,
                        description=f"Imported from Spotify ({spotify_data.get('subtitle', '')})".strip(),
                        thumbnail=cover_art
                    )
                    saved_playlist_id = new_pl["id"]

                # Add all matched tracks to custom playlist
                for m in matched_tracks:
                    if m.get("matched") and m.get("videoId"):
                        self.db.add_track_to_playlist(saved_playlist_id, m)

                logger.info(f"Auto-saved Spotify playlist '{playlist_title}' to My Playlists (ID: {saved_playlist_id}) with {len(matched_tracks)} tracks.")
            except Exception as save_err:
                logger.error(f"Failed to auto-save imported Spotify playlist: {save_err}")

        return {
            "title": spotify_data["title"],
            "subtitle": spotify_data["subtitle"],
            "coverArt": spotify_data["coverArt"],
            "totalTracks": len(tracks),
            "matchedCount": sum(1 for m in matched_tracks if m["matched"]),
            "tracks": matched_tracks,
            "playlistId": saved_playlist_id,
            "savedToLibrary": bool(saved_playlist_id)
        }
