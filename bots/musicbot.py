"""
This file is the main entry point for the Music bot.
"""

import asyncio

import discord

from bot import DiscordBot


class MusicBot(DiscordBot):
    def __init__(self, name: str):
        super().__init__(name)

    async def start(self):
        await super().start()

    async def on_ready(self):
        await super().on_ready()

        # Change discord status to "Playing music in __ servers"
        await self.change_presence(
            activity=discord.Activity(
                name=f"music in {len(self.guilds)} servers",
                type=discord.ActivityType.streaming,
            )
        )


async def main():
    bot = await MusicBot.create("Music Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
