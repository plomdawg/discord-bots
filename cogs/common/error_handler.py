"""
Error handler cog for Discord bots.
Handles command errors and provides user-friendly error messages.
"""

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from bot import DiscordBot


class ErrorHandler(commands.Cog):
    """Cog for handling command errors."""

    def __init__(self, bot: "DiscordBot"):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param.name}")
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.")
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
            return

        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions to do that.")
            return

        # Log unexpected errors
        self.bot.log(f"Command error: {error}")
        await ctx.send("An unexpected error occurred. Please try again later.")


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
