"""
This cog provides test functionality.
"""

from discord.ext import commands
import discord

from bots.testbot import TestBot


class Test(commands.Cog):
    def __init__(self, bot: TestBot):
        self.bot = bot

    # Add the /hello command
    @discord.app_commands.command()
    async def hello(self, interaction: discord.Interaction):
        """Says hello!"""
        text = f"Hi, {interaction.user.mention}"
        await self.bot.messaging.send_embed(interaction, text=text)

    async def test_messaging_cog(self, channel_id: int):
        """Test the messaging cog by sending and deleting a message."""
        channel = self.bot.get_channel(channel_id)
        message = await self.bot.messaging.send_embed(channel, title="Hello, world!")
        await self.bot.messaging.add_reactions(message, ["👍", "👎"])
        await self.bot.messaging.delete_message(message)
        self.bot.log("Successfully sent and deleted a message!")


async def setup(bot):
    await bot.add_cog(Test(bot))
