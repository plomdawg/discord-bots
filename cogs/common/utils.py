import functools
from typing import TYPE_CHECKING, Any, Callable, Union

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import DiscordBot


def ignore_self(func: Callable) -> Callable:
    """Decorator to ignore events from the bot itself.
    Works with both on_message and on_reaction_add events."""

    @functools.wraps(func)
    async def wrapper(
        self,
        event: Union[discord.Message, discord.Reaction],
        user: Union[discord.User, None] = None,
        *args: Any,
        **kwargs: Any,
    ):
        # For message events
        if isinstance(event, discord.Message):
            if event.author == self.bot.user:
                return
            return await func(self, event, *args, **kwargs)

        # For reaction events
        if isinstance(event, discord.Reaction):
            if user == self.bot.user:
                return
            return await func(self, event, user, *args, **kwargs)

        return await func(self, event, user, *args, **kwargs)

    return wrapper


class Utils(commands.Cog):
    def __init__(self, bot: "DiscordBot"):
        # Store the bot instance so we can access it inside the cog.
        self.bot = bot

    def get_voice_channel(self, user, guild_id):
        """
        Get the voice channel for a user in a guild.
        """
        if user.voice:
            return user.voice.channel

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return None

        # Find the user's voice channel.
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.id == user.id:
                    return channel

        # Failed to find a voice channel.
        return None

    async def author_has_voice(self, message: discord.Message, reason: str):
        """Returns True if the user is connected to a voice channel.
        Sends the message if the user is not connected."""
        if not (message.author.voice and message.author.voice.channel):
            thumbnail = "http://i.imgur.com/go67eLE.gif"
            error = (
                f"{message.author.mention} you must be in a voice channel to {reason}."
            )
            await self.bot.messaging.send_error(
                message.channel, text=error, thumbnail=thumbnail
            )
            return False
        return True

    def server_info(self):
        """
        List all servers the bot is in.
        """
        self.bot.log(f"Listing {len(self.bot.guilds)} servers")
        total_members = 0
        for guild in self.bot.guilds:
            self.bot.log(
                f" -  {guild.owner}: {guild.name} ({guild.id}) {guild.member_count} members"
            )
            total_members += guild.member_count or 0
        self.bot.log(f"Total members: {total_members}")


async def setup(bot):
    await bot.add_cog(Utils(bot))
