"""
This cog provides Dota 2 wiki-related functionality.
"""

from discord.ext import commands


class DotaWiki(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(DotaWiki(bot))
