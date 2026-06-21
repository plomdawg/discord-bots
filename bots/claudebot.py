"""
Entry point for Claude Bot — talk to Claude Code from Discord.

Mention the bot (`@claude plex is broken!`) and it runs the headless Claude Code
CLI in the homelab repo, just like typing into an interactive session there.
Only plomdawg is listened to; conversations live in threads (one resumable
Claude session per thread). See cogs/claude/agent.py.
"""

import asyncio
import typing

import discord

from bot import DiscordBot
from cogs.common.secrets import Secrets


class ClaudeBot(DiscordBot):
    def __init__(self, name: str):
        # Least-privilege intents: claudebot only needs to read message content +
        # guild messages, not Members/Presence. So only the "Message Content"
        # privileged intent has to be enabled in the developer portal.
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(name, intents=intents)

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
        # Don't call super().on_ready(): it uses self.utils.server_info(), and this
        # lean bot doesn't load the Utils cog.
        await self.set_activity("Watching for @mentions 🤖")
        self.log(f"Logged in as {self.user}")
        self.log(f"Listening only to user id {self.secrets.get('PLOMDAWG_USER_ID')}")
        self.log(f"In {len(self.guilds)} guild(s): {[g.name for g in self.guilds]}")


async def main():
    bot = await ClaudeBot.create("Claude Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
