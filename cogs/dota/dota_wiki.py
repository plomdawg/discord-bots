"""
This cog provides Dota 2 wiki-related functionality.
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bots.dotabot import DotaBot


class DotaWiki(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(DotaWiki(bot))
