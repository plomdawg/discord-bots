"""
This cog provides Gemini AI API functionality.
"""

import pathlib
from io import BytesIO
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands
from google import genai
from google.genai import types
from PIL import Image
import requests

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

    def generate_image(self, contents: list, path: pathlib.Path):
        """Generate an image using Gemini API to a path."""
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=contents,
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
        await self.handle_image_generation(interaction, prompt=prompt)

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
        await self.handle_image_generation(interaction, prompt=prompt)

    async def handle_image_generation(
        self,
        interaction: discord.Interaction,
        prompt: str,
        image=None,
        display_text: Optional[str] = None,
    ):
        """Handle the image generation process."""
        # Add the image to the contents if it is provided.
        contents = [prompt, image] if image else [prompt]

        # Reply to the interaction.
        text = (
            display_text or f"Generating image using Gemini AI: \n{code_block(prompt)}"
        )
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
            self.generate_image(contents=contents, path=image_path)
            self.log(f"Image saved successfully to {image_path}")
        except Exception as e:
            self.log(f"{e.__class__.__name__}: {e.__str__()}")
            self.log(f"Error generating image: {e}")
            return await self.bot.messaging.send_error(
                interaction.channel, text=f"Failed to generate image: {e}"
            )

        # Send the image
        await self.bot.messaging.send_image(interaction.channel, image_path)

    # Add the /chad command
    @discord.app_commands.command(
        name="chad", description="Generate a chad image using Gemini API."
    )
    @discord.app_commands.describe(user="The user to generate a chad image of.")
    async def chad(self, interaction: discord.Interaction, user: discord.Member):
        """Generate a chad image using Gemini API."""
        image_bytes = requests.get(user.display_avatar.url).content
        image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        # Create a prompt that incorporates the avatar and asks for a chad style image
        # prompt = f"Create a modern meme gigachad-style image of this avatar personified. IMPORTANT: Maintain the exact same gender as shown in the avatar - if the avatar appears feminine, keep it feminine; if masculine, keep it masculine. Do not alter or change the gender presentation in any way. Just make them look like a giga chad with huge muscles and a confident, heroic pose."
        # prompt = f"Generate a photograph of a gigachad-style image of this avatar personified. Body-builder body, with the avatar personified as the head. Use details from the avatar to make the body match the avatar. IMPORTANT: Maintain the exact same gender as shown in the avatar - if the avatar appears feminine, keep it feminine; if masculine, keep it masculine. Do not alter or change the gender presentation of the face in any way."
        prompt = f"Generate a image in the same artstyle of this avatar as a gigachad. Personify the avatar with a more muscular body. Use details from the avatar to make the body match the avatar. The outfit and accessories should be similar to the avatar, but designed to show off the muscles. IMPORTANT: Maintain the exact same gender as shown in the avatar - if the avatar appears feminine, keep it feminine; if masculine, keep it masculine. Do not alter or change the gender presentation of the face in any way."

        await self.handle_image_generation(
            interaction=interaction,
            prompt=prompt,
            image=image,
            display_text=f"Generating chad image of {user.display_name}...",
        )

    # Add the /remix command
    @discord.app_commands.command(
        name="remix", description="Generate a remix image using Gemini API."
    )
    @discord.app_commands.describe(user="The user to generate a remix image of.")
    @discord.app_commands.describe(prompt="The prompt to generate a remix image of.")
    async def remix(
        self, interaction: discord.Interaction, user: discord.Member, prompt: str
    ):
        """Generate a remix of a discord user's avatar using Gemini API."""
        image_bytes = requests.get(user.display_avatar.url).content
        image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        await self.handle_image_generation(
            interaction=interaction,
            prompt=prompt,
            image=image,
        )


async def setup(bot):
    await bot.add_cog(Gemini(bot))
