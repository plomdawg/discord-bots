"""YouTube music source."""

import asyncio
import functools
import html
import logging
import re
import urllib.parse
from typing import Any, List, Optional

import isodate
import pyyoutube
import yt_dlp

from ..audio.types import AudioTrack

# Base ytdl configuration options
_BASE_YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

# Configuration for streaming URL extraction
STREAMING_YTDL_OPTIONS = {
    **_BASE_YTDL_OPTIONS,
    "extractaudio": True,
    "audioformat": "best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
}


class YouTubeSource:
    """A music source for YouTube."""

    def __init__(self, api_key: str):
        self.api = pyyoutube.Api(api_key=api_key)

    def _safe_get_items(self, result: Any) -> List[Any]:
        """Safely get items from a pyyoutube result object."""
        if not result:
            return []

        try:
            # Try accessing as property first
            items = result.items
            if callable(items):
                # If it's a method, call it
                items = items()
            return list(items) if items else []
        except (AttributeError, TypeError):
            return []

    async def extract_streaming_url(self, youtube_url: str) -> str:
        """Extract the actual streaming URL from a YouTube URL."""
        # Run yt-dlp extraction in executor to avoid blocking
        loop = asyncio.get_event_loop()
        extract_func = functools.partial(
            yt_dlp.YoutubeDL(STREAMING_YTDL_OPTIONS).extract_info,
            youtube_url,
            download=False,
        )
        info = await loop.run_in_executor(None, extract_func)

        if info and "url" in info:
            return info["url"]
        elif info and "formats" in info and info["formats"]:
            # Try to get the best audio format manually
            formats = info["formats"]
            audio_formats = [f for f in formats if f.get("acodec") != "none"]
            if audio_formats:
                best_format = audio_formats[0]  # yt-dlp orders them by quality
                return best_format["url"]
            else:
                raise ValueError("No audio formats found")
        else:
            raise ValueError("Failed to extract streaming URL from YouTube")

    async def get_track(self, query: str) -> Optional[AudioTrack]:
        """Get a track from a query string."""
        if "youtube.com" in query or "youtu.be" in query:
            return await self.url_to_track(query)
        return await self.query_to_track(query)

    async def query_to_track(self, query: str) -> Optional[AudioTrack]:
        """Converts a query to a track"""
        # Search youtube
        try:
            results = self.api.search_by_keywords(
                q=query, search_type=["video"], count=1, limit=1
            )
            items = self._safe_get_items(results)
            if not items:
                return None

            first_item = items[0]
            if not hasattr(first_item, "id") or not hasattr(first_item.id, "videoId"):
                return None
            video_id = first_item.id.videoId
            if not video_id:
                return None
            return await self.id_to_track(video_id, query)
        except Exception as e:
            logging.error(f"Failed to search youtube for '{query}': {e}")
            return None

    async def id_to_track(self, video_id: str, query: str) -> Optional[AudioTrack]:
        """Get a track from a video ID."""
        try:
            videos = self.api.get_video_by_id(video_id=video_id)
            items = self._safe_get_items(videos)
            if not items:
                return None

            video = items[0]
            if (
                not video
                or not hasattr(video, "snippet")
                or not hasattr(video, "contentDetails")
                or not video.snippet
                or not video.contentDetails
                or not hasattr(video.snippet, "thumbnails")
                or not video.snippet.thumbnails
                or not hasattr(video.snippet.thumbnails, "high")
                or not video.snippet.thumbnails.high
            ):
                return None

            # Safely get the title with type checking
            title_raw = getattr(video.snippet, "title", None)
            if not title_raw or not isinstance(title_raw, str):
                return None
            title = html.unescape(title_raw)

            duration = int(
                isodate.parse_duration(video.contentDetails.duration).total_seconds()
            )
            thumbnail = video.snippet.thumbnails.high.url
            youtube_url = f"https://youtu.be/{video_id}"

            # Extract streaming URL
            streaming_url = await self.extract_streaming_url(youtube_url)

            track_data = {
                "id": video_id,
                "name": video_id,
                "title": title,
                "duration": duration,
                "query": query,
                "thumbnail": thumbnail,
                "youtube_url": youtube_url,
                "source_url": streaming_url,  # Use the extracted streaming URL
            }
            track = AudioTrack(**track_data)
            return track
        except Exception as e:
            logging.error(f"Failed to get video details for '{video_id}': {e}")
            return None

    async def url_to_track(self, url: str) -> Optional[AudioTrack]:
        """Converts a video URL to a track"""
        try:
            parsed = urllib.parse.urlparse(url)
            if "v" in urllib.parse.parse_qs(parsed.query):
                video_id = urllib.parse.parse_qs(parsed.query)["v"][0]
            else:
                video_id = parsed.path.lstrip("/")
            return await self.id_to_track(video_id, url)
        except Exception as e:
            logging.error(f"Failed to parse youtube url '{url}': {e}")
            return None

    async def get_playlist(self, url: str) -> List[AudioTrack]:
        """Get tracks from a playlist URL."""
        try:
            playlist_id_match = re.search(r"list=([^&]+)", url)
            if not playlist_id_match:
                return []
            playlist_id = playlist_id_match.group(1)
            playlist = self.api.get_playlist_items(playlist_id=playlist_id, count=None)
            items = self._safe_get_items(playlist)
            if not items:
                return []

            tracks = []
            for item in items:
                if (
                    item
                    and hasattr(item, "snippet")
                    and item.snippet
                    and hasattr(item.snippet, "resourceId")
                    and item.snippet.resourceId
                    and hasattr(item.snippet.resourceId, "videoId")
                    and item.snippet.resourceId.videoId
                ):
                    track = await self.id_to_track(item.snippet.resourceId.videoId, "")
                    if track:
                        tracks.append(track)
            return tracks
        except Exception as e:
            logging.error(f"Failed to get youtube playlist '{url}': {e}")
            return []
