import random

import discord
from discord.ext import commands
from discord.ext.commands import context

from bot import DiscordBot

MAX_MSG_LENGTH = 2048


class Messaging(commands.Cog):
    def __init__(self, bot: DiscordBot):
        # Store the bot instance so we can access it inside the cog.
        self.bot = bot

    async def add_reactions(self, message, emojis):
        """Adds emojis to a message, ignoring NotFound errors"""
        if message is not None:
            try:
                for emoji in emojis:
                    await message.add_reaction(emoji)
            except discord.errors.NotFound:
                pass

    async def delete_message(self, message):
        """Deletes a message, ignoring NotFound errors"""
        if message is not None:
            try:
                await message.delete()
            except discord.errors.NotFound:
                pass

    async def send_embed(
        self,
        channel,
        color=None,
        footer=None,
        footer_icon=None,
        subtitle=None,
        subtext=None,
        text=None,
        title=None,
        thumbnail=None,
    ):
        """Sends a message to a channel, and returns the discord.Message of the sent message.

        If the text is over 2048 characters, subtitle and subtext fields are ignored and the
        message is split up into chunks. The first message will have the title and thumbnail,
        and only the last message will have the footer. Returns the last message sent.
        """
        # Use a random color if none was given
        color = color or random.randint(0, 0xFFFFFF)

        self.bot.log(f"type(channel) = {type(channel)}")
        # If the text is short enough to fit into one message,
        # create and send a single embed.
        if text is None or len(text) <= MAX_MSG_LENGTH:
            embed = discord.Embed(color=color)
            if footer is not None:
                if footer_icon is None:
                    embed.set_footer(text=footer)
                else:
                    embed.set_footer(text=footer, icon_url=footer_icon)
            if subtitle is not None or subtext is not None:
                embed.add_field(name=subtitle, value=subtext, inline=True)
            if thumbnail is not None:
                embed.set_thumbnail(url=thumbnail)
            if title is not None:
                embed.title = title
            if text is not None:
                embed.description = text

            # If this is a ctx, use respond() so the command succeeds and doesn't
            # print "This interaction failed" to the user.
            self.bot.log(f"type(channel) = {type(channel)}")
            if type(channel) == discord.interactions.Interaction:
                response = await channel.response.send_message(embed=embed)
                return

            # Send the single message
            return await channel.send(embed=embed)

        # If the text is too long, it must be broken into chunks.
        message_index = 0
        lines = text.split("\n")
        while lines:
            # Construct the text of this message
            text = ""
            while True:
                if not lines:
                    break
                line = lines.pop(0) + "\n"

                # next line fits in this message, add it
                if len(text) + len(line) < MAX_MSG_LENGTH:
                    text += line

                # one line is longer than max length of message, split the line and put the rest back
                elif len(line) > MAX_MSG_LENGTH:
                    cutoff = MAX_MSG_LENGTH - len(text)
                    next_line = line[:cutoff]
                    remainder = line[cutoff:-1]
                    text += next_line
                    lines.insert(0, remainder)
                # message is full - send it
                else:
                    lines.insert(0, line)
                    break

            embed = discord.Embed(color=color)
            embed.description = text

            # First message in chain - add the title and thumbnail
            if message_index == 0:
                if title is not None:
                    embed.title = title
                if thumbnail is not None:
                    embed.set_thumbnail(url=thumbnail)
                if subtitle is not None or subtext is not None:
                    embed.add_field(name=subtitle, value=subtext, inline=True)
                response = await channel.send(embed=embed)

            # Last message in chain - add the footer.
            if not lines:
                if footer is not None:
                    if footer_icon is not None:
                        embed.set_footer(text=footer, icon_url=footer_icon)
                    else:
                        embed.set_footer(text=footer)

                # If this is an interaction, use response.send_message() so the command
                # succeeds and doesn't print "This interaction failed" to the user.
                self.bot.log(f"type(channel) = {type(channel)}")
                if type(channel) == discord.interactions.Interaction:
                    response = await channel.response.send_message(embed=embed)
                else:
                    response = await channel.send(embed=embed)

            message_index = message_index + 1

        # Return the last message sent so reactions can be easily added
        return response


async def setup(bot):
    await bot.add_cog(Messaging(bot))
