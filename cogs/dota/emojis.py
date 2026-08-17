"""Emojis"""

import pathlib
from typing import TYPE_CHECKING, List

import discord
from discord import app_commands
from discord.ext import commands

from cogs.dota.utils import (
    download_hero_icons,
    emoji_name,
    get_heroes,
    upload_icons_to_servers,
)

if TYPE_CHECKING:
    from bots.dotabot import DotaBot

# DotA Heroes servers
SERVERS = [650182236490170369, 650182259248463907, 650180306782912533]
ICON_DIR = pathlib.Path("cogs/dota/icons")
ICON_DIR.mkdir(parents=True, exist_ok=True)

# Keep well under messaging.MAX_MSG_LENGTH (2048) -- edit_embed splits longer
# text into extra messages, which would break a single live-updating embed.
LIST_LIMIT = 1400


def format_list(entries: List[str], limit: int = LIST_LIMIT, sep: str = ", ") -> str:
    """Render entries as a joined list, truncating with a "+N more".

    Truncates on entry boundaries -- slicing the raw string could cut an emoji
    mention in half, which Discord renders as literal broken text.
    """
    if not entries:
        return "_none_"
    parts, length = [], 0
    for i, entry in enumerate(entries):
        if length + len(entry) + len(sep) > limit:
            parts.append(f"… +{len(entries) - i} more")
            break
        parts.append(entry)
        length += len(entry) + len(sep)
    return sep.join(parts)


# Checks
def user_is_plomdawg(interaction: discord.Interaction) -> bool:
    """Returns True if the author is plomdawg"""
    return interaction.user.id == 163040232701296641


class Emojis(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot
        self.emojis = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Loads all emojis from the 3 servers above"""
        self.load_emojis()

    def get(self, name) -> str:
        """Get an emoji.

        Uses the same normalization as the uploader -- this used to strip only
        spaces, so heroes with punctuation (Anti-Mage, Nature's Prophet) could
        never match their uploaded emoji.
        """
        return self.emojis.get(emoji_name(name), "")

    def missing_heroes(self) -> list:
        """Heroes that currently have no emoji loaded from the 3 servers."""
        return [h for h in get_heroes() if not self.emojis.get(emoji_name(h.localized_name))]

    def load_emojis(self):
        """Loads all emojis from the 3 servers above"""
        for guild_id in SERVERS:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            for emoji in guild.emojis:
                self.emojis[emoji.name] = str(emoji)
        self.bot.log(f"Loaded {len(self.emojis.keys())} emojis.")

    @app_commands.check(user_is_plomdawg)
    @app_commands.command(name="setup", description="Set up the emojis")
    async def setup_emojis(self, interaction: discord.Interaction):
        """Uploads all the hero icons onto 3 different servers (50 max each)"""
        message = await self.bot.messaging.send_embed(
            interaction,
            title="Setting up Emojis",
            text="Checking which heroes are missing emoji...",
        )

        # Refresh from the servers first so "missing" reflects reality.
        self.load_emojis()
        missing = self.missing_heroes()

        if not missing:
            heroes = get_heroes()
            slots = 50 * len(SERVERS) - len(self.emojis)
            # Glyphs only -- with names attached only ~35 of 127 fit in the
            # 2048-char budget, and the icon already identifies the hero.
            roster = [self.get(h.localized_name) for h in heroes]
            await self.bot.messaging.edit_embed(
                message,
                title="Emojis Setup Complete",
                text=(
                    f"All **{len(heroes)}** heroes already have an emoji. Nothing to do.\n"
                    f"Free emoji slots left: **{slots}** "
                    f"(50 per server x {len(SERVERS)}).\n\n"
                    + format_list(roster, sep=" ")
                ),
                color=discord.Color.green(),
            )
            return

        # Fetch icons for only the missing heroes. Uploading the whole directory
        # would spend the free-slot budget on icons that already exist.
        downloaded: List[str] = []

        async def on_download(name, status, done, total):
            if status == "cached":
                downloaded.append(f"{name} (cached)")
            elif status.startswith("failed"):
                downloaded.append(f"⚠️ {name}")
            else:
                downloaded.append(name)
            if status.startswith("failed") or done == total or done % 10 == 0:
                await self.bot.messaging.edit_embed(
                    message,
                    title="Setting up Emojis",
                    text=(
                        f"Downloading hero icons from dotabase... **{done}/{total}**\n\n"
                        + format_list(downloaded)
                    ),
                )

        icons = await download_hero_icons(ICON_DIR, missing, progress=on_download)

        # Stream the emoji as they land -- once created they render immediately.
        uploaded: List[str] = []
        failed: List[str] = []

        async def on_upload(name, emoji, status, done, total):
            if status == "uploaded":
                uploaded.append(f"{emoji} {name}")
            elif status == "exists":
                uploaded.append(f"{self.emojis.get(emoji_name(name), '')} {name}")
            else:
                failed.append(f"{name} — {status}")
            # Throttle edits: Discord rate-limits message edits per channel, so
            # only surface every 5th upload, the last one, and any failure.
            if status.startswith("failed") or done == total or done % 5 == 0:
                text = (
                    f"Uploading icons to {len(SERVERS)} servers... "
                    f"**{len(uploaded)}/{total}**\n\n" + format_list(uploaded)
                )
                if failed:
                    text += f"\n\n**Failed ({len(failed)}):** " + format_list(failed)
                await self.bot.messaging.edit_embed(
                    message, title="Setting up Emojis", text=text
                )

        successful, total = await upload_icons_to_servers(
            self.bot, ICON_DIR, SERVERS, icons=icons, progress=on_upload
        )

        # Reload emojis after upload
        self.load_emojis()
        still_missing = self.missing_heroes()
        heroes = len(get_heroes())
        slots = 50 * len(SERVERS) - len(self.emojis)

        text = (
            f"Uploaded **{successful}/{total}** icons and reloaded emojis.\n"
            f"Heroes with an emoji: **{heroes - len(still_missing)}/{heroes}**\n"
            f"Free emoji slots left: **{slots}** (50 per server x {len(SERVERS)})."
        )
        if uploaded:
            text += "\n\n**Added:**\n" + format_list(uploaded)
        if failed:
            text += f"\n\n**Failed ({len(failed)}):**\n" + format_list(failed)
        if still_missing:
            text += f"\n\n**Still missing ({len(still_missing)}):** " + format_list(
                [h.localized_name for h in still_missing]
            )
        if slots <= 0:
            text += "\n\n⚠️ Servers are full — add another server to `SERVERS`."

        await self.bot.messaging.edit_embed(
            message,
            title="Emojis Setup Complete",
            text=text,
            color=discord.Color.green(),
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(Emojis(bot))
