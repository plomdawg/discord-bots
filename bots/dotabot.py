"""
This file is the main entry point for the Dota 2 bot.
"""

import asyncio

from bot import DiscordBot
from cogs.dota.dota_wiki import DotaWiki

import typing


class DotaBot(DiscordBot):
    def __init__(self, name: str):
        super().__init__(name)

    async def start(self):
        # Load the cogs used by the Dota bot.
        cog = await self.load_cog("dota.dota_wiki", "DotaWiki")
        self.dota_wiki = typing.cast(DotaWiki, cog)

        await super().start(token=self.secrets.get("DOTABOT_DISCORD_SECRET_TOKEN"))

    async def on_ready(self):
        await self.set_activity(f"DotA 2 in {len(self.guilds)} servers! 🎮")
        await super().on_ready()


async def main():
    bot = await DotaBot.create("Dota Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
