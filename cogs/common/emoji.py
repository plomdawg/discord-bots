import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
import enum


if TYPE_CHECKING:
    from bot import DiscordBot


class Emoji(commands.Cog):
    """Adds emojis that trigger actions to messages."""

    def __init__(self, bot: "DiscordBot"):
        # Store the bot instance so we can access it inside the cog.
        self.bot = bot
        # Store the emoji actions.
        self.actions = {}

    async def add_actions(self, message, actions):
        """Adds actions to a message, ignoring NotFound errors

        Args:
            message: The message to add actions to.
            actions: A dictionary of emoji to action.

        Example:
            actions = {
                "🔀": self.bot.audio.queue.shuffle,
            }
        """
        if message is not None:
            # Keep track of the message ID.
            self.actions[message.id] = actions

            # Add emoji responses.
            await self.bot.messaging.add_reactions(message, actions.keys())

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignore reactions from self.
        if user.id == self.bot.user.id:
            return

        # Get the message.
        message = reaction.message

        # Get the action for the message.
        action = self.actions.get(message.id, {}).get(reaction.emoji)

        # If the action is not found, do nothing.
        if action is None:
            return

        # Run the action.
        await action(message, user)

        # Remove the reaction.
        await self.bot.messaging.delete_reaction(message, reaction)


async def setup(bot):
    await bot.add_cog(Emoji(bot))
