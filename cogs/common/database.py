"""Database management functionality."""

from typing import Any, List, Optional

from discord.ext import commands
from pony import orm

from .models import Guild, Track, TrackInfo, User, db


class Database(commands.Cog):
    """Manages database operations for the bot."""

    def __init__(self, bot):
        self.bot = bot
        self.db_session = orm.db_session

    @commands.Cog.listener()
    async def on_ready(self):
        """Bind the database to the bot's user name."""
        name = self.bot.user.name.replace(" ", "_")
        filename = f"database-{name}.sqlite"
        db.bind(provider="sqlite", filename=filename, create_db=True)
        db.generate_mapping(create_tables=True)

    def _get_or_create_guild(self, guild_id: str) -> Guild:
        """Get a guild or create it if it doesn't exist."""
        with self.db_session:
            guild = Guild.get(id=guild_id)
            if guild is None:
                guild = Guild(id=guild_id)
            return guild

    def _get_or_create_user(self, user_id: int) -> User:
        """Get a user or create it if it doesn't exist."""
        with self.db_session:
            user = User.get(id=str(user_id))
            if user is None:
                user = User(id=str(user_id))
            return user

    # Track operations
    def find_track(self, **kwargs) -> Optional[Track]:
        """Find a track by any combination of fields."""
        with self.db_session:
            return Track.get(**kwargs)

    def save_track(self, **kwargs) -> Track:
        """Save a track to the database."""
        with self.db_session:
            return Track(**kwargs)

    def save_youtube_track(self, youtube_id: str, info: TrackInfo) -> Track:
        """Save a track from YouTube data."""
        with self.db_session:
            return Track.from_youtube(youtube_id, info)

    def save_spotify_track(
        self, spotify_id: str, info: TrackInfo, spotify_url: str
    ) -> Track:
        """Save a track from Spotify data."""
        with self.db_session:
            return Track.from_spotify(spotify_id, info, spotify_url)

    def increment_plays(self, track_id: str) -> None:
        """Increment the play count for a track."""
        with self.db_session:
            track = Track.get(id=track_id)
            if track:
                track.plays += 1

    # Guild operations
    def get_guild(
        self, guild_id: str, create_if_missing: bool = False
    ) -> Optional[Guild]:
        """Get a guild by ID."""
        if create_if_missing:
            return self._get_or_create_guild(guild_id)
        with self.db_session:
            return Guild.get(id=guild_id)

    def get_guild_setting(self, guild_id: str, key: str, default: Any = None) -> Any:
        """Get a guild setting."""
        with self.db_session:
            guild = self._get_or_create_guild(guild_id)
            return guild.get_setting(key, default)

    def set_guild_setting(self, guild_id: str, key: str, value: Any) -> None:
        """Set a guild setting."""
        with self.db_session:
            guild = self._get_or_create_guild(guild_id)
            guild.set_setting(key, value)

    # User operations
    def get_user(self, user_id: int, create_if_missing: bool = False) -> Optional[User]:
        """Get a user by ID."""
        if create_if_missing:
            return self._get_or_create_user(user_id)
        with self.db_session:
            return User.get(id=user_id)

    def get_user_setting(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get a user setting."""
        with self.db_session:
            user = self._get_or_create_user(user_id)
            return user.get_setting(key, default)

    def set_user_setting(self, user_id: int, key: str, value: Any) -> None:
        """Set a user setting."""
        with self.db_session:
            user = self._get_or_create_user(user_id)
            user.set_setting(key, value)

    def get_all_users(self) -> List[int]:
        """Get a list of all user IDs in the database."""
        with self.db_session:
            return [user.id for user in User.select()]


async def setup(bot):
    """Add the database manager to the bot."""
    await bot.add_cog(Database(bot))
