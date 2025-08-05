"""Unified music source handler for YouTube and Spotify."""

from typing import List, Optional

from ..audio.types import AudioTrack
from .spotify_source import SpotifySource
from .youtube_source import YouTubeSource


class MusicSource:
    """Unified music source that can handle both YouTube and Spotify sources."""

    def __init__(
        self,
        youtube_api_key: str,
        spotify_client_id: str,
        spotify_client_secret: str,
    ):
        self.youtube = YouTubeSource(youtube_api_key)
        self.spotify = SpotifySource(
            spotify_client_id, spotify_client_secret, self.youtube
        )

    async def get_track(self, query: str) -> Optional[AudioTrack]:
        """Get a track from a query string.

        Args:
            query: The search query or URL

        Returns:
            Optional AudioTrack
        """
        if "spotify.com" in query:
            track = await self.spotify.get_track(query)
            if track:
                # Convert Spotify track to AudioTrack - use the source_url from YouTube track
                return AudioTrack(
                    name=track.name,
                    source_url=track.source_url,
                    title=track.title,
                    duration=track.duration,
                    youtube_url=track.youtube_url,
                    thumbnail=track.thumbnail,
                )
        else:
            track = await self.youtube.get_track(query)
            if track:
                return track

        return None

    async def get_playlist(self, url: str) -> List[AudioTrack]:
        """Get tracks from a playlist URL.

        Args:
            url: The playlist URL

        Returns:
            List of AudioTracks
        """
        tracks = []
        if "spotify.com" in url:
            spotify_tracks = await self.spotify.get_playlist(url)
            for track in spotify_tracks:
                tracks.append(
                    AudioTrack(
                        name=track.name,
                        source_url=track.source_url,
                        title=track.title,
                        duration=track.duration,
                        youtube_url=track.youtube_url,
                        thumbnail=track.thumbnail,
                    )
                )
        elif "youtube.com" in url:
            youtube_tracks = await self.youtube.get_playlist(url)
            for track in youtube_tracks:
                tracks.append(
                    AudioTrack(
                        name=track.name,
                        source_url=track.source_url,
                        title=track.title,
                        duration=track.duration,
                        youtube_url=track.youtube_url,
                        thumbnail=track.thumbnail,
                    )
                )

        return tracks
