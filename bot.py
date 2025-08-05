"""
This file is the main entry point for a discord bot.
"""

import typing
from datetime import datetime

import colorama
import discord
from discord import app_commands
from discord.ext import commands

from cogs.audio.audio import Audio
from cogs.common.database import Database
from cogs.common.messaging import Messaging
from cogs.common.secrets import Secrets
from cogs.common.utils import Utils

# Initialize colorama for colored console output.
colorama.init()


class DiscordBot(commands.Bot):
    def __init__(self, name: str):
        """
        Initialize the bot.

        Args:
            name (str): The name of the bot.
        """
        intents = discord.Intents.all()
        super().__init__(command_prefix="/", case_insensitive=True, intents=intents)
        self.name = name
        # Add type hints for cogs
        self.audio: Audio
        self.database: Database
        self.messaging: Messaging
        self.secrets: Secrets
        self.utils: Utils

    @classmethod
    async def create(cls, name: str) -> "DiscordBot":
        """
        Create and initialize a new bot instance.

        Args:
            name (str): The name of the bot.

        Returns:
            DiscordBot: The initialized bot instance.
        """
        bot = cls(name)
        # Load the cogs used by all bots.
        cog = await bot.load_cog("common.secrets", "Secrets")
        bot.secrets = typing.cast(Secrets, cog)
        cog = await bot.load_cog("common.database", "Database")
        bot.database = typing.cast(Database, cog)
        cog = await bot.load_cog("common.messaging", "Messaging")
        bot.messaging = typing.cast(Messaging, cog)
        cog = await bot.load_cog("common.utils", "Utils")
        bot.utils = typing.cast(Utils, cog)
        cog = await bot.load_cog("audio.audio", "Audio")
        bot.audio = typing.cast(Audio, cog)
        # cog = await bot.load_cog("common.error_handler", "ErrorHandler")
        return bot

    async def setup_hook(self):
        """
        Setup the bot by syncing commands to all servers.
        """
        commands = self.tree.get_commands()
        if len(commands) == 0:
            self.log("No commands to sync")
            return
        self.log(f"Syncing {len(commands)} commands to all servers:")
        for command in commands:
            assert isinstance(command, app_commands.Command)
            self.log(f"   /{command.name} - {command.description}")

        await self.tree.sync()
        self.log("Done syncing commands to all servers")

    @property
    def invite_link(self) -> str:
        """
        Get the invite link for the bot.
        """
        permissions = 1110453312
        url = f"https://discordapp.com/oauth2/authorize"
        url += f"?client_id={self.user.id}"  # type: ignore
        url += f"&scope=bot&permissions={permissions}"
        return url

    def log(self, message: str):
        """
        Log a message to the console with colors.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{colorama.Fore.CYAN}[{timestamp}] {colorama.Fore.GREEN}[{self.name}]{colorama.Style.RESET_ALL} {message}"
        )

    def error(self, message: str):
        """
        Log an error message to the console with colors.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{colorama.Fore.CYAN}[{timestamp}] {colorama.Fore.RED}[{self.name}]{colorama.Style.RESET_ALL} Error: {message}"
        )

    async def start(self, token=None):
        """
        Start the bot with the given token.
        """
        # Use provided token or get from secrets
        self.log("Starting bot...")
        token = token or self.secrets.get("DISCORD_BOT_SECRET_TOKEN")  # type: ignore
        await super().start(token)

    async def load_cog(self, cog_path: str, cog_name: str) -> commands.Cog:
        """
        Load a cog.

        Args:
            cog_path (str): The path to the cog module.
            cog_name (str): The name of the cog class.

        Returns:
            commands.Cog: The loaded cog.
        """
        self.log(
            f"Loading cog: {colorama.Fore.YELLOW}{cog_name}{colorama.Style.RESET_ALL} from {colorama.Fore.YELLOW}{cog_path}{colorama.Style.RESET_ALL}"
        )
        await self.load_extension(f"cogs.{cog_path}")
        cog = self.get_cog(cog_name)
        if cog is None:
            raise ValueError(f"Cog {cog_name} not found")
        return cog

    async def on_ready(self):
        """
        Called when the bot is ready.
        """
        self.log(
            f"Logged in as {colorama.Fore.GREEN}{self.user}{colorama.Style.RESET_ALL}"
        )
        self.log("Invite the bot to your server using the following link:")
        self.log(f" --> {self.invite_link}")

        # Print all servers the bot is in
        self.utils.server_info()  # type: ignore

    async def on_error(self, event: str, *args, **kwargs):
        """
        Called when an error occurs.
        """
        import traceback

        self.error(f"Error in event '{event}': {traceback.format_exc()}")

    async def set_activity(self, activity: str):
        """Sets the bot's activity based on a string.
        Available activities: Playing, Listening to, Watching
        Example: set_activity("Watching in 42 servers")"""
        # Generate the discord.Activity based on the first word

        # Only a few of the activity types are supported.
        activities = {
            "Playing": discord.ActivityType.playing,
            "Listening to": discord.ActivityType.listening,
            "Watching": discord.ActivityType.watching,
        }

        # Default to "Playing"
        activity_type = discord.ActivityType.playing

        # CHeck if the activity starts with a supported activity type.
        for activity_name, _activity_type in activities.items():
            if activity.startswith(activity_name):
                activity = activity.strip(activity_name)
                activity_type = _activity_type
                break

        # Set the activity.
        await self.change_presence(
            activity=discord.Activity(name=activity, type=activity_type)
        )
