"""Spotify music source."""

import logging
from typing import List, Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from ..audio.types import AudioTrack


class SpotifySource:
    """A music source for Spotify."""

    def __init__(self, client_id: str, client_secret: str, youtube_source):
        self.client = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )
        )
        self.youtube_source = youtube_source

    async def get_track(self, query: str) -> Optional[AudioTrack]:
        """Get a track from a query string."""
        if "track" in query:
            track_id = self._get_id_from_url(query, "track")
            if track_id:
                return await self.track_id_to_track(track_id)
        return None

    async def get_playlist(self, url: str) -> List[AudioTrack]:
        """Get tracks from a playlist URL."""
        playlist_id = self._get_id_from_url(url, "playlist")
        if not playlist_id:
            return []

        try:
            playlist = self.client.playlist_items(playlist_id)
            if not playlist:
                return []
            tracks = []
            for item in playlist["items"]:
                track = await self.track_to_track(item["track"])
                if track:
                    tracks.append(track)
            return tracks
        except Exception as e:
            logging.error(f"Failed to get spotify playlist '{url}': {e}")
            return []

    async def track_id_to_track(self, track_id: str) -> Optional[AudioTrack]:
        """Get a track from a track ID."""
        try:
            track = self.client.track(track_id)
            return await self.track_to_track(track)
        except Exception as e:
            logging.error(f"Failed to get spotify track '{track_id}': {e}")
            return None

    async def track_to_track(self, track_data: Optional[dict]) -> Optional[AudioTrack]:
        """Convert a spotify track dictionary to an AudioTrack."""
        if not track_data:
            return None
        try:
            title = f"{track_data['artists'][0]['name']} - {track_data['name']}"
            duration = track_data.get("duration_ms", 0) / 1000
            spotify_id = track_data.get("id")
            spotify_url = track_data.get("external_urls", {}).get("spotify")
            thumbnail = track_data.get("album", {}).get("images", [{}])[0].get("url")

            track = {
                "title": title,
                "duration": duration,
                "spotify_id": spotify_id,
                "spotify_url": spotify_url,
                "thumbnail": thumbnail,
            }
            # Get the YouTube equivalent for playback
            youtube_track = await self.youtube_source.get_track(title)
            if youtube_track:
                track["youtube_url"] = youtube_track.youtube_url
                track["source_url"] = youtube_track.source_url
                track["name"] = youtube_track.name

            return AudioTrack(**track)
        except (KeyError, IndexError) as e:
            logging.error(f"Failed to convert spotify track: {e}")
            return None
        except Exception as e:
            logging.error(f"Failed to convert spotify track: {e}")
            return None

    def _get_id_from_url(self, url: str, key: str) -> Optional[str]:
        """Extracts an ID from a spotify url."""
        try:
            return url.split(f"{key}/")[1].split("?")[0]
        except IndexError:
            return None
