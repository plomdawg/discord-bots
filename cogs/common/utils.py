from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import DiscordBot


class Utils(commands.Cog):
    def __init__(self, bot: "DiscordBot"):
        # Store the bot instance so we can access it inside the cog.
        self.bot = bot

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
