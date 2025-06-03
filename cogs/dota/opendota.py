"""
This cog provides opendota-related functionality.
"""

from typing import TYPE_CHECKING

import discord
import opendota2py
from discord.ext import commands

if TYPE_CHECKING:
    from bots.dotabot import DotaBot


def get_player(opendota_id: str) -> opendota2py.Player:
    """Get a player by OpenDota ID."""
    return opendota2py.Player(opendota_id)


class OpenDota(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[OpenDota] {message}")

    @discord.app_commands.command(
        name="opendota_id",
        description="Set your OpenDota ID.",
    )
    @discord.app_commands.describe(
        opendota_id="Your OpenDota ID (e.g. 1234567890).",
    )
    async def opendota_id(self, interaction: discord.Interaction, opendota_id: str):
        """Set your OpenDota ID."""
        self.bot.database.set_user_setting(
            interaction.user.id, "opendota_id", opendota_id
        )
        await self.bot.messaging.send_embed(
            interaction,
            title="OpenDota ID",
            text=f"OpenDota ID set to {opendota_id}.",
            ephemeral=True,
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(OpenDota(bot))


# Test functions.
if __name__ == "__main__":
    cog = OpenDota(None)
    plomdawg = opendota2py.Player(82279028)
    clockwerk = opendota2py.Hero(51)
    matches = plomdawg.matches()
    print(f"Found {len(matches)} matches for {plomdawg.personaname}.")
    for match in matches:
        text = f"Match: https://www.opendota.com/matches/{match.match_id} ({match.skill}) Hero: {opendota2py.Hero(match.hero_id).localized_name}"
        if match.player_slot < 128 and match.radiant_win:
            text += " (Win) ✅"
        elif match.player_slot > 128 and not match.radiant_win:
            text += " (Win) ✅"
        else:
            text += " (Loss) ❌"
        print(text)
