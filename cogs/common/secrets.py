"""
This cog is used to load secrets.
"""

import os

from discord.ext import commands

from bot import DiscordBot


class Secrets(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

    def get(self, secret_name) -> str:
        """
        Get a secret from an environment variable.

        Args:
            secret_name (str): The name of the secret.

        Returns:
            str: The secret.
        """
        secret = os.getenv(secret_name)
        if not secret:
            raise ValueError(f"Secret {secret_name} not found in environment variables")
        return secret


async def setup(bot):
    await bot.add_cog(Secrets(bot))
