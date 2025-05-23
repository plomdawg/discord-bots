"""
This cog provides Gemini AI API functionality.
"""

import pathlib
from io import BytesIO
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from google import genai
from google.genai import types
from PIL import Image

from cogs.common.messaging import code_block

IMAGE_DIRECTORY = pathlib.Path("images")
IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)


if TYPE_CHECKING:
    from bot import DiscordBot


class Gemini(commands.Cog):
    def __init__(self, bot: "DiscordBot"):
        self.bot = bot
        self.client = genai.Client(api_key=self.bot.secrets.get("GEMINI_API_KEY"))

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[Gemini] {message}")

    def generate_image(self, prompt: str, path: pathlib.Path):
        """Generate an image using Gemini API to a path."""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                ),
            )
            if not response.candidates:
                self.log("Error: No candidates in response")
                raise ValueError("No candidates in response")

            if not response.candidates[0].content:
                self.log("Error: No content in first candidate")
                raise ValueError("No content in first candidate")

            if not response.candidates[0].content.parts:
                self.log("Error: No parts in content")
                raise ValueError("No parts in content")

            for part in response.candidates[0].content.parts:
                if part.inline_data is not None and part.inline_data.data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image.save(path)
                    return

            self.log("Error: No image data found in response parts")
            raise ValueError("No image data found in response parts")

        except Exception as e:
            self.log(f"{e.__class__.__name__}: {e.__str__()}")
            self.log(f"Error generating image: {str(e)}")
            raise

    # Add the /image command
    @discord.app_commands.command(
        name="image", description="Generate an image using Gemini API."
    )
    @discord.app_commands.describe(prompt="The prompt to generate an image from.")
    async def image(self, interaction: discord.Interaction, prompt: str):
        """Generate an image using Gemini API."""
        await self.handle_image_generation(interaction, prompt)

    # Add the /low-poly command
    @discord.app_commands.command(
        name="lowpoly", description="Generate a low-poly image using Gemini API."
    )
    @discord.app_commands.describe(
        prompt="The prompt to generate a low-poly image from."
    )
    async def lowpoly(self, interaction: discord.Interaction, prompt: str):
        """Generate a low-poly image using Gemini API."""
        prompt = f"A simple low-poly digital illustration of {prompt} with a simple light colored background"
        await self.handle_image_generation(interaction, prompt)

    async def handle_image_generation(
        self, interaction: discord.Interaction, prompt: str
    ):
        """Handle the image generation process."""
        text = f"Generating image using Gemini AI: \n{code_block(prompt)}"
        await self.bot.messaging.send_embed(
            interaction,
            text=text,
            footer_icon=interaction.user.display_avatar.url,
        )

        # Generate the image path based on message id.
        image_path = IMAGE_DIRECTORY / f"{interaction.id}.png"

        try:
            self.log(f"Generating image for {interaction.user.display_name}:")
            self.log(f"  -> {prompt}")
            self.generate_image(prompt, image_path)
            self.log(f"Image saved successfully to {image_path}")
        except Exception as e:
            self.log(f"{e.__class__.__name__}: {e.__str__()}")
            self.log(f"Error generating image: {e}")
            return await self.bot.messaging.send_error(
                interaction.channel, text=f"Failed to generate image: {e}"
            )

        # Send the image
        await self.bot.messaging.send_image(interaction.channel, image_path)


async def setup(bot):
    await bot.add_cog(Gemini(bot))
