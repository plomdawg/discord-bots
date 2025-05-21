"""
This cog provides Dota 2 wiki-related functionality.
"""

from discord.ext import commands

from bots.dotabot import DotaBot


class DotaWiki(commands.Cog):
    def __init__(self, bot: DotaBot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(DotaWiki(bot))
