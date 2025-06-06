import random
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import DiscordBot

MAX_MSG_LENGTH = 2048


def bold(text):
    """Returns a bolded version of the text."""
    return f"**{text}**"


def italic(text):
    """Returns an italicized version of the text."""
    return f"*{text}*"


def underline(text):
    """Returns an underlined version of the text."""
    return f"___{text}___"


def code(text):
    """Returns a code version of the text."""
    return f"`{text}`"


def code_block(text):
    """Returns a code block version of the text."""
    return f"```{text}```"


def quoted_text(text: str) -> str:
    """Get the quoted text from the message.

    Args:
        text: The text to quote

    Returns:
        str: The quoted text with > prefix on each line
    """
    lines = text.split("\n")
    quoted_lines = [f" > {line}" for line in lines]
    return "\n".join(quoted_lines)


class Messaging(commands.Cog):
    def __init__(self, bot: "DiscordBot"):
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

    async def remove_reaction(self, reaction):
        """Removes a reaction from a message, ignoring NotFound errors"""
        try:
            await reaction.remove()
        except discord.errors.NotFound:
            pass

    async def remove_reactions(self, message):
        """Removes all reactions from a message, ignoring NotFound errors"""
        if message is not None:
            try:
                await message.clear_reactions()
            except discord.errors.NotFound:
                pass

    async def delete_message(self, message: discord.Message):
        """Deletes a message, ignoring NotFound errors"""
        if message is not None:
            try:
                await message.delete()
            except discord.errors.NotFound:
                pass

    def _create_base_embed(
        self,
        color,
        title=None,
        thumbnail=None,
        subtitle=None,
        subtext=None,
        footer=None,
        footer_icon=None,
    ) -> discord.Embed:
        """Creates a base embed with common fields."""
        embed = discord.Embed(color=color)
        if title is not None:
            embed.title = title
        if thumbnail is not None:
            embed.set_thumbnail(url=thumbnail)
        if subtitle is not None or subtext is not None:
            embed.add_field(name=subtitle, value=subtext, inline=True)
        if footer is not None:
            if footer_icon is not None:
                embed.set_footer(text=footer, icon_url=footer_icon)
            else:
                embed.set_footer(text=footer)
        return embed

    async def _send_embed(
        self, channel, embed: discord.Embed, ephemeral: bool = False
    ) -> discord.Message:
        """Sends a single embed message to the channel."""
        if type(channel) == discord.interactions.Interaction:
            response = await channel.response.send_message(
                embed=embed, ephemeral=ephemeral
            )
            assert isinstance(response.resource, discord.Message)
            return response.resource
        return await channel.send(embed=embed)

    def _split_text_into_chunks(self, text: str) -> list[str]:
        """Splits text into chunks that fit within Discord's message length limit."""
        chunks = []
        lines = text.split("\n")
        current_chunk = ""

        while lines:
            line = lines.pop(0) + "\n"

            if len(current_chunk) + len(line) < MAX_MSG_LENGTH:
                current_chunk += line
            elif len(line) > MAX_MSG_LENGTH:
                cutoff = MAX_MSG_LENGTH - len(current_chunk)
                next_line = line[:cutoff]
                remainder = line[cutoff:-1]
                current_chunk += next_line
                chunks.append(current_chunk)
                current_chunk = ""
                lines.insert(0, remainder)
            else:
                chunks.append(current_chunk)
                current_chunk = line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

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
        ephemeral=False,
    ):
        """Sends a message to a channel, and returns the discord.Message of the sent message.

        If the text is over 2048 characters, subtitle and subtext fields are ignored and the
        message is split up into chunks. The first message will have the title and thumbnail,
        and only the last message will have the footer. Returns the last message sent.
        """
        color = color or random.randint(0, 0xFFFFFF)

        # If the text is short enough to fit into one message, create and send a single embed
        if text is None or len(text) <= MAX_MSG_LENGTH:
            embed = self._create_base_embed(
                color=color,
                title=title,
                thumbnail=thumbnail,
                subtitle=subtitle,
                subtext=subtext,
                footer=footer,
                footer_icon=footer_icon,
            )
            if text is not None:
                embed.description = text
            return await self._send_embed(channel, embed, ephemeral)

        # Handle long text by splitting into chunks
        chunks = self._split_text_into_chunks(text)
        last_response = None

        for i, chunk in enumerate(chunks):
            embed = discord.Embed(color=color, description=chunk)

            # First message gets title and thumbnail
            if i == 0:
                if title is not None:
                    embed.title = title
                if thumbnail is not None:
                    embed.set_thumbnail(url=thumbnail)
                if subtitle is not None or subtext is not None:
                    embed.add_field(name=subtitle, value=subtext, inline=True)

            # Last message gets footer
            if i == len(chunks) - 1 and footer is not None:
                if footer_icon is not None:
                    embed.set_footer(text=footer, icon_url=footer_icon)
                else:
                    embed.set_footer(text=footer)

            last_response = await self._send_embed(channel, embed, ephemeral)

        return last_response

    async def send_image(self, channel, image, text=None):
        """Sends an image to a channel, optionally with text.

        Args:
            channel: The channel to send the image to (can be a channel or interaction)
            image: The image to send (can be a file path or file-like object)
            text: Optional text to send with the image

        Returns:
            The discord.Message of the sent message
        """
        return await channel.send(content=text, file=discord.File(image))

    async def send_file(self, channel, file_path, text=None, filename=None):
        """Sends a file to a channel, optionally with text.

        Args:
            channel: The channel to send the file to (can be a channel or interaction)
            file_path: The file to send (can be a file path or file-like object)
            text: Optional text to send with the file
            filename: Optional custom filename for the file

        Returns:
            The discord.Message of the sent message
        """
        discord_file = (
            discord.File(file_path, filename=filename)
            if filename
            else discord.File(file_path)
        )
        return await channel.send(content=text, file=discord_file)

    async def edit_embed(
        self,
        message,
        color=None,
        title=None,
        text=None,
        thumbnail=None,
        subtitle=None,
        subtext=None,
        footer=None,
        footer_icon=None,
    ):
        """Edits an existing embed message with new properties.

        If the text is over 2048 characters, subtitle and subtext fields are ignored and the
        message is split up into chunks. The first message will have the title and thumbnail,
        and only the last message will have the footer. Returns the last message edited.
        """
        if not message:
            return

        try:
            # If text is short enough or None, just edit the single embed
            if text is None or len(text) <= MAX_MSG_LENGTH:
                embed = message.embeds[0] if message.embeds else discord.Embed()

                # Update basic properties
                for attr, value in {
                    "color": color,
                    "title": title,
                    "description": text,
                }.items():
                    if value is not None:
                        setattr(embed, attr, value)

                # Update thumbnail if provided
                if thumbnail:
                    embed.set_thumbnail(url=thumbnail)

                # Update subtitle field if either is provided
                if subtitle or subtext:
                    # Remove existing subtitle field
                    for i, field in enumerate(embed.fields):
                        if field.name == subtitle:
                            embed.remove_field(i)
                            break
                    embed.add_field(name=subtitle, value=subtext, inline=True)

                # Update footer if provided
                if footer:
                    embed.set_footer(
                        text=footer, icon_url=footer_icon if footer_icon else None
                    )

                await message.edit(embed=embed)
                return message

            # Handle long text by splitting into chunks
            chunks = self._split_text_into_chunks(text)
            last_message = message

            for i, chunk in enumerate(chunks):
                embed = discord.Embed(
                    color=color or random.randint(0, 0xFFFFFF), description=chunk
                )

                # First message gets title and thumbnail
                if i == 0:
                    if title is not None:
                        embed.title = title
                    if thumbnail is not None:
                        embed.set_thumbnail(url=thumbnail)
                    if subtitle is not None or subtext is not None:
                        embed.add_field(name=subtitle, value=subtext, inline=True)

                # Last message gets footer
                if i == len(chunks) - 1 and footer is not None:
                    if footer_icon is not None:
                        embed.set_footer(text=footer, icon_url=footer_icon)
                    else:
                        embed.set_footer(text=footer)

                # Edit existing message or send new one
                if i == 0:
                    await message.edit(embed=embed)
                    last_message = message
                else:
                    last_message = await message.channel.send(embed=embed)

            return last_message

        except discord.errors.NotFound:
            pass

    async def send_error(self, channel, text, thumbnail=None):
        """Sends an error message to a channel."""
        if len(text) > MAX_MSG_LENGTH:
            text = text[: MAX_MSG_LENGTH - 3] + "..."

        return await self.send_embed(
            channel,
            color=discord.Color.red(),
            title="Error",
            text=text,
            thumbnail=thumbnail,
        )


async def setup(bot):
    await bot.add_cog(Messaging(bot))
