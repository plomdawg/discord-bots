"""
This file is the main entry point for the Music bot.
"""

import asyncio

from bot import DiscordBot


class MusicBot(DiscordBot):
    def __init__(self, name: str):
        super().__init__(name)

    async def start(self):
        await self.load_cog("music.genius", "Genius")
        await super().start(self.secrets.get("MUSICBOT_DISCORD_SECRET_TOKEN"))

    async def on_ready(self):
        await self.set_activity(f"Playing in {len(self.guilds)} servers 🎧")
        await super().on_ready()


async def main():
    bot = await MusicBot.create("Music Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
