"""
This file is the main entry point for the Test bot.
"""

import asyncio
import pathlib
import typing

import discord

from bot import DiscordBot
from cogs.gemini import Gemini
from cogs.test import Test

MY_DUDES = discord.Object(id=408172061723459584)
TEST_CHANNEL = discord.Object(id=408481491597787136)


class TestBot(DiscordBot):
    def __init__(self, name: str):
        super().__init__(name)

    async def start(self):
        # Load the test cog.
        await self.load_cog("test", "Test")
        self.test = typing.cast(Test, self.get_cog("Test"))
        await self.load_cog("gemini", "Gemini")
        self.gemini = typing.cast(Gemini, self.get_cog("Gemini"))
        await super().start()

    async def setup_hook(self):
        # Sync the commands to the guild.
        self.log("Syncing commands to my dudes guild")
        await self.tree.sync(guild=MY_DUDES)
        self.log("Done syncing commands to my dudes guild")
        await super().setup_hook()

    async def on_ready(self):
        await self.set_activity(f"Watching {len(self.guilds)} servers! 😀")
        await super().on_ready()

        # Test the gemini cog.
        self.gemini.generate_image(
            prompt="A beautiful sunset over a calm ocean",
            path=pathlib.Path("sunset.png"),
        )

        # Test the messaging cog.
        # await self.test.test_messaging_cog(channel_id=TEST_CHANNEL.id)


async def main():
    bot = await TestBot.create("Test Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
