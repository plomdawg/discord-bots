"""
Entry point for Claude Bot — talk to Claude Code from Discord.

Mention the bot (`@claude plex is broken!`) and it runs the headless Claude Code
CLI in the homelab repo, just like typing into an interactive session there.
Only plomdawg is listened to; conversations live in threads (one resumable
Claude session per thread). See cogs/claude/agent.py.
"""

import asyncio
import typing

from bot import DiscordBot
from cogs.common.secrets import Secrets


class ClaudeBot(DiscordBot):
    @classmethod
    async def create(cls, name: str) -> "ClaudeBot":
        """Lean bootstrap: claudebot only needs the Secrets cog (no audio/db)."""
        bot = cls(name)
        cog = await bot.load_cog("common.secrets", "Secrets")
        bot.secrets = typing.cast(Secrets, cog)
        return bot

    async def start(self):
        await self.load_cog("claude.agent", "ClaudeAgent")
        await super().start(token=self.secrets.get("CLAUDEBOT_DISCORD_SECRET_TOKEN"))

    async def on_ready(self):
        await self.set_activity("Watching for @mentions 🤖")
        await super().on_ready()


async def main():
    bot = await ClaudeBot.create("Claude Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
