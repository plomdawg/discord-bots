"""
This file is the main entry point for the Voice bot.
"""

import asyncio

import discord

from bot import DiscordBot


class VoiceBot(DiscordBot):
    def __init__(self):
        super().__init__("Voice Bot")

    async def start(self):
        await super().start()

    async def on_ready(self):
        await super().on_ready()

        # Change discord status to "Playing TTS in __ servers"
        await self.change_presence(
            activity=discord.Activity(
                name=f"TTS in {len(self.guilds)} servers",
                type=discord.ActivityType.streaming,
            )
        )


async def main():
    bot = VoiceBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
