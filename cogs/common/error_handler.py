"""
Error handler cog for Discord bots.
Handles command errors and provides user-friendly error messages.
"""

import traceback
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import DiscordBot


class ErrorHandler(commands.Cog):
    """Cog for handling command errors."""

    def __init__(self, bot: "DiscordBot"):
        self.bot = bot
        # Set up application command error handler
        self.bot.tree.on_error = self.on_app_command_error

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param.name}")
            self.bot.error(f"Missing required argument in command: {error}")
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.")
            self.bot.error(f"Bad argument in command: {error}")
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
            self.bot.error(f"Missing permissions: {error}")
            return

        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions to do that.")
            self.bot.error(f"Bot missing permissions: {error}")
            return

        # Log unexpected errors with full traceback
        self.bot.error(f"Unexpected command error: {error}")
        self.bot.error(f"Full traceback: {traceback.format_exc()}")
        await ctx.send("An unexpected error occurred. Please try again later.")

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ):
        """Handle application command (slash command) errors."""
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
            return

        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            self.bot.error(f"Missing permissions in app command: {error}")
            return

        if isinstance(error, discord.app_commands.BotMissingPermissions):
            await interaction.response.send_message(
                "I don't have the required permissions to do that.",
                ephemeral=True
            )
            self.bot.error(f"Bot missing permissions in app command: {error}")
            return

        # Log unexpected errors with full traceback
        self.bot.error(f"Unexpected app command error: {error}")
        self.bot.error(f"Full traceback: {traceback.format_exc()}")
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )
        except Exception as e:
            self.bot.error(f"Failed to send error message: {e}")


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
