"""
This file is the main entry point for the Test bot.
"""

import asyncio

import discord
from discord import app_commands

from bot import DiscordBot

MY_DUDES = discord.Object(id=408172061723459584)
TEST_CHANNEL = discord.Object(id=408481491597787136)


class TestBot(DiscordBot):
    def __init__(self, name: str):
        super().__init__(name)

    async def setup_hook(self):
        self.log("Copying global commands to guild")

        # Add the hello command
        @self.tree.command(name="hello", description="Says hello!", guild=MY_DUDES)
        async def hello(interaction: discord.Interaction):
            """Says hello!"""
            text = f"Hi, {interaction.user.mention}"
            await self.messaging.send_embed(interaction, text=text)

        # Sync the commands to the guild.
        self.log("Syncing commands to my dudes guild")
        await self.tree.sync(guild=MY_DUDES)
        self.log("Done syncing commands to my dudes guild")

    async def on_ready(self):
        await super().on_ready()

        self.log("Registering test command")

        # Change discord status to "Watching __ servers"
        await self.change_presence(
            activity=discord.Activity(
                name=f"{len(self.guilds)} servers",
                type=discord.ActivityType.watching,
            )
        )

        # Test the messaging cog.
        await self.test_messaging()

    async def test_messaging(self):
        """Test the messaging cog by sending and deleting a message."""
        channel = self.get_channel(TEST_CHANNEL.id)
        message = await self.messaging.send_embed(channel, title="Hello, world!")
        await self.messaging.add_reactions(message, ["👍", "👎"])
        await self.messaging.delete_message(message)

        self.log("Successfully sent and deleted a message!")


async def main():
    bot = await TestBot.create("Test Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
