"""Data models and common functionality."""

import json
import pathlib
from dataclasses import dataclass
from typing import Any, Optional, cast

from pony import orm

# Configure the pony database
db = orm.Database()


@dataclass
class TrackInfo:
    """Common track information shared between sources."""

    title: str
    duration: int
    query: str
    user: Optional[str] = None
    thumbnail: Optional[str] = None


class Track(db.Entity):
    """A track that can be played by the music player."""

    id = orm.PrimaryKey(str)  # YouTube ID
    title = orm.Required(str)
    duration = orm.Required(int, default=0)
    plays = orm.Required(int, default=0)
    query = orm.Optional(str)  # Original search query
    spotify_id = orm.Optional(str)  # Spotify ID if available
    thumbnail = orm.Optional(str)  # Thumbnail URL
    spotify_url = orm.Optional(str)  # Spotify URL if available
    youtube_url = orm.Optional(str)  # YouTube URL
    user = orm.Optional(str)  # User who requested the track

    @property
    def downloaded(self) -> bool:
        """Returns True if the track is downloaded."""
        return self.path.is_file()

    @property
    def path(self) -> pathlib.Path:
        """Returns the path to the downloaded track."""
        return pathlib.Path("tracks") / f"{self.id}.mp3"

    @property
    def link(self) -> str:
        """Returns a markdown link to the track."""
        # Remove brackets from track title
        title = cast(str, self.title).translate(str.maketrans(dict.fromkeys("[]()")))
        url = self.youtube_url or self.spotify_url
        return f"[**{title}**]({url})"

    @classmethod
    def from_youtube(cls, youtube_id: str, info: TrackInfo) -> "Track":
        """Create a track from YouTube data."""
        with orm.db_session:
            return cls(
                id=youtube_id,
                title=info.title,
                duration=info.duration,
                query=info.query,
                thumbnail=info.thumbnail,
                youtube_url=f"https://youtu.be/{youtube_id}",
                user=info.user,
            )

    @classmethod
    def from_spotify(
        cls, spotify_id: str, info: TrackInfo, spotify_url: str
    ) -> "Track":
        """Create a track from Spotify data."""
        with orm.db_session:
            return cls(
                id="",  # Will be filled in when YouTube lookup happens
                title=info.title,
                duration=info.duration,
                query=info.query,
                spotify_id=spotify_id,
                spotify_url=spotify_url,
                user=info.user,
            )


class Guild(db.Entity):
    """Guild settings."""

    id = orm.PrimaryKey(str)
    volume = orm.Required(float, default=20.0)
    music_channel = orm.Optional(str)
    settings = orm.Optional(str, default="{}")  # JSON string of key-value pairs

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a guild setting."""
        with orm.db_session:
            settings_str = cast(str, self.settings)
            settings = json.loads(settings_str)
            return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a guild setting."""
        with orm.db_session:
            settings_str = cast(str, self.settings)
            settings = json.loads(settings_str)
            settings[key] = value
            self.settings = json.dumps(settings)


class User(db.Entity):
    """User settings and data."""

    id = orm.PrimaryKey(str)
    steam_id = orm.Optional(str, default="")
    settings = orm.Optional(str, default="{}")  # JSON string of key-value pairs

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a user setting."""
        with orm.db_session:
            settings_str = cast(str, self.settings)
            settings = json.loads(settings_str)
            return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a user setting."""
        with orm.db_session:
            settings_str = cast(str, self.settings)
            settings = json.loads(settings_str)
            settings[key] = value
            self.settings = json.dumps(settings)
