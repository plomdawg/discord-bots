"""
This cog provides Gemini AI API functionality.
"""

import glob
import math
import os
import pathlib
from io import BytesIO
from typing import TYPE_CHECKING, Optional

import discord
import requests
from discord import app_commands
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

    def generate_image(
        self, prompt: str, path: pathlib.Path, image: Optional[types.Part] = None
    ):
        """Generate an image using Gemini API to a path."""
        try:
            self.log(f"Generating image to {path}")
            parts = [types.Part(text=prompt)]
            if image is not None:
                parts.append(image)

            response = self.client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=[types.Content(parts=parts)],
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

            if response.candidates[0].content.parts[0].text:
                self.log(f"Text: {response.candidates[0].content.parts[0].text}")

            for part in response.candidates[0].content.parts:
                if (
                    hasattr(part, "inline_data")
                    and part.inline_data
                    and part.inline_data.data
                ):
                    # The data should be base64 encoded
                    import base64

                    try:
                        # Try to decode base64 data
                        image_data = base64.b64decode(part.inline_data.data)
                        # Save the decoded data
                        with open(path, "wb") as f:
                            f.write(image_data)
                        return
                    except Exception as e:
                        self.log(f"Error decoding image data: {e}")
                        # If base64 decoding fails, try saving raw data
                        with open(path, "wb") as f:
                            f.write(part.inline_data.data)
                        return

            self.log("Error: No image data found in response parts")
            raise ValueError("No image data found in response parts")

        except Exception as e:
            self.log(f"{e.__class__.__name__}: {e.__str__()}")
            self.log(f"Error generating image: {str(e)}")

            # Check for quota exceeded error
            if "RESOURCE_EXHAUSTED" in str(e) and "429" in str(e):
                raise ValueError("The daily quota has been exceeded :(")
            raise

    # Add the /image command
    @app_commands.command(
        name="image", description="Generate an image using Gemini API."
    )
    @app_commands.describe(prompt="The prompt to generate an image from.")
    async def image(self, interaction: discord.Interaction, prompt: str):
        """Generate an image using Gemini API."""
        await self.handle_image_generation(interaction, prompt=prompt)

    # Add the /low-poly command
    @app_commands.command(
        name="lowpoly", description="Generate a low-poly image using Gemini API."
    )
    @app_commands.describe(prompt="The prompt to generate a low-poly image from.")
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
        # Reply to the interaction.
        text = (
            display_text or f"Generating image using Gemini AI: \n{code_block(prompt)}"
        )
        await self.bot.messaging.send_embed(
            interaction,
            text=text,
            footer_icon=(
                interaction.user.display_avatar.url if interaction.user else None
            ),
        )

        # Generate the image path based on message id.
        image_path = IMAGE_DIRECTORY / f"{interaction.id}.png"

        try:
            self.log(
                f"Generating image for {interaction.user.display_name if interaction.user else 'unknown user'}:",
            )
            self.log(f"  -> {prompt}")
            self.generate_image(image=image, prompt=prompt, path=image_path)
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
    @app_commands.command(
        name="chad", description="Generate a chad image using Gemini API."
    )
    @app_commands.describe(user="The user to generate a chad image of.")
    async def chad(self, interaction: discord.Interaction, user: discord.Member):
        """Generate a chad image using Gemini API."""
        self.log(
            f"Generating chad image of {user.display_name}: {user.display_avatar.url}"
        )
        image_bytes = requests.get(user.display_avatar.url).content
        image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        # Create a prompt that incorporates the avatar and asks for a chad style image
        prompt = "Generate a image in the same artstyle of this avatar as a gigachad. Personify the avatar with a more muscular body. Use details from the avatar to make the body match the avatar. The outfit and accessories should be similar to the avatar, but designed to show off the muscles. IMPORTANT: Maintain the exact same gender as shown in the avatar - if the avatar appears feminine, keep it feminine; if masculine, keep it masculine. Do not alter or change the gender presentation of the face in any way."

        await self.handle_image_generation(
            interaction=interaction,
            prompt=prompt,
            image=image,
            display_text=f"Generating chad image of {user.display_name}...",
        )

    # Add the /troll command
    @app_commands.command(
        name="troll", description="Generate a troll image using Gemini API."
    )
    @app_commands.describe(user="The user to generate a troll image of.")
    async def troll(self, interaction: discord.Interaction, user: discord.Member):
        """Generate a troll image using Gemini API."""
        image_bytes = requests.get(user.display_avatar.url).content
        image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        await self.handle_image_generation(
            interaction=interaction,
            prompt="This character as a stupid troll",
            image=image,
            display_text=f"Generating {user.display_name} as a troll...",
        )

    # Add the /remix command
    @app_commands.command(
        name="remix", description="Generate a remix image using Gemini API."
    )
    @app_commands.describe(user="The user to generate a remix image of.")
    @app_commands.describe(prompt="The prompt to generate a remix image of.")
    async def remix(
        self, interaction: discord.Interaction, user: discord.Member, prompt: str
    ):
        """Generate a remix of a discord user's avatar using Gemini API."""
        self.log(
            f"Generating remix image of {user.display_name}: {user.display_avatar.url} with prompt: {prompt}"
        )
        image_bytes = requests.get(user.display_avatar.url).content
        image = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        await self.handle_image_generation(
            interaction=interaction,
            prompt=prompt,
            image=image,
        )

    # Add the /last command
    @app_commands.command(
        name="last", description="Create a collage of the most recent generated images."
    )
    @app_commands.describe(
        number="Number of recent images to include in collage (default: 25)"
    )
    async def last(self, interaction: discord.Interaction, number: int = 25):
        """Create a collage of the most recent images from the images folder."""
        message = await self.bot.messaging.send_embed(
            interaction,
            text=f"Creating collage of {number} recent images...",
            color=discord.Color.blue(),
        )

        try:
            assert IMAGE_DIRECTORY.exists(), "No images directory found!"

            # Get all image files sorted by modification time (most recent first)
            image_files = []
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"]:
                image_files.extend(glob.glob(str(IMAGE_DIRECTORY / ext)))

            assert image_files, "No images found in the images directory!"

            # Sort by modification time (newest first) and take the requested number
            image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            recent_files = image_files[:number]

            assert recent_files, "No recent images found!"

            # Create collage using existing IMAGE_DIRECTORY
            collage_path = IMAGE_DIRECTORY / f"collage_{interaction.id}.png"
            self.create_collage(recent_files, collage_path)

            # Send the collage using existing messaging system
            await self.bot.messaging.send_image(interaction.channel, collage_path)

            # Clean up the temporary collage file
            try:
                os.remove(collage_path)
            except:
                pass

        except Exception as e:
            self.log(f"Error creating collage: {e}")
            await self.bot.messaging.edit_embed(
                message,
                text=f"Failed to create collage: {str(e)}",
                color=discord.Color.red(),
            )

    def create_collage(self, image_paths: list, output_path: pathlib.Path):
        """Create a collage from the given image paths."""
        # Calculate grid dimensions to fit all images
        num_images = len(image_paths)

        if num_images == 1:
            cols, rows = 1, 1
        else:
            # Calculate square-ish grid that fits all images
            cols = math.ceil(math.sqrt(num_images))
            rows = math.ceil(num_images / cols)

        # Calculate individual image size to fit in 2000x2000
        img_width = 2000 // cols
        img_height = 2000 // rows

        # Create the collage canvas
        collage = Image.new("RGB", (2000, 2000), (255, 255, 255))

        for i, img_path in enumerate(image_paths):
            try:
                # Open and resize image
                img = Image.open(img_path)
                img = img.convert("RGB")
                img = img.resize((img_width, img_height), Image.Resampling.LANCZOS)

                # Calculate position
                col = i % cols
                row = i // cols
                x = col * img_width
                y = row * img_height

                # Paste image onto collage
                collage.paste(img, (x, y))

            except Exception as e:
                self.log(f"Error processing image {img_path}: {e}")
                continue

        # Save the collage
        collage.save(output_path, "PNG")


async def setup(bot):
    await bot.add_cog(Gemini(bot))
