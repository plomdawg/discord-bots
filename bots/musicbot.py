"""
This file is the main entry point for the Music bot.
"""

import asyncio

from bot import DiscordBot


class MusicBot(DiscordBot):
    """Music bot."""

    def __init__(self, name: str):
        super().__init__(name)

    async def start(self):
        """Start the bot."""
        await self.load_cog("music.genius", "Genius")
        await self.load_cog("music.music", "Music")
        await super().start(self.secrets.get("MUSICBOT_DISCORD_SECRET_TOKEN"))

    async def on_ready(self):
        """Called when the bot is ready."""
        await self.set_activity(f"Playing in {len(self.guilds)} servers 🎧")
        await super().on_ready()


async def main():
    """Run the bot."""
    bot = await MusicBot.create("Music Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
