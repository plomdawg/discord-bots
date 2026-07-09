"""
This cog provides local AI image generation via the homelab Forge server.

Images are generated on the RTX 3090 by Stable Diffusion WebUI Forge
(services/forge in the homelab repo), reached over its A1111-compatible REST API.
This replaced the Gemini image API, whose free-tier model was deprecated and whose
replacement (gemini-2.5-flash-image) is paid-only.
"""

import base64
import glob
import math
import os
import pathlib
from typing import TYPE_CHECKING, Optional

import discord
import requests
from discord import app_commands
from discord.ext import commands
from PIL import Image

from cogs.common.messaging import code_block

IMAGE_DIRECTORY = pathlib.Path("images")
IMAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)

# Forge (Stable Diffusion WebUI Forge) on homelab — A1111-compatible REST API.
# Same host-IP convention as PLOMTTS_ENDPOINT in cogs/voice/tts_fish.py.
FORGE_ENDPOINT = "http://192.168.8.175:7860"
# Default checkpoint (see services/forge/data/models/Stable-diffusion/).
DEFAULT_MODEL = "Juggernaut-XL-v9"


if TYPE_CHECKING:
    from bot import DiscordBot


class Gemini(commands.Cog):
    def __init__(self, bot: "DiscordBot"):
        self.bot = bot

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[Gemini] {message}")

    def format_api_error(self, e: Exception) -> str:
        """Format a Forge/HTTP error into a readable one-liner."""
        if isinstance(e, requests.HTTPError) and e.response is not None:
            detail = ""
            try:
                body = e.response.json()
                detail = body.get("detail") or body.get("error") or ""
            except Exception:
                detail = (e.response.text or "").strip()
            detail = f": {detail}" if detail else ""
            return f"{e.response.status_code} {e.response.reason}{detail}"[:400]
        if isinstance(e, requests.ConnectionError):
            return "could not reach the Forge image server (is services/forge up?)"
        if isinstance(e, requests.Timeout):
            return "image generation timed out"
        return str(e)

    def generate_image(
        self,
        prompt: str,
        path: pathlib.Path,
        image: Optional[bytes] = None,
        model: Optional[str] = None,
    ):
        """Generate an image via Forge and write it to path.

        Text-to-image when ``image`` is None; image-to-image (guided by the given
        raw image bytes, e.g. a Discord avatar) when it is provided.
        """
        model = model or DEFAULT_MODEL
        payload = {
            "prompt": prompt,
            "steps": 25,
            "width": 1024,
            "height": 1024,
            "cfg_scale": 6.0,
            "sampler_name": "DPM++ 2M",
            "override_settings": {"sd_model_checkpoint": model},
            "override_settings_restore_afterwards": False,
        }

        if image is not None:
            # img2img: seed the generation with the reference image (avatar remixes).
            payload["init_images"] = [base64.b64encode(image).decode("ascii")]
            payload["denoising_strength"] = 0.6
            endpoint = "/sdapi/v1/img2img"
        else:
            endpoint = "/sdapi/v1/txt2img"

        self.log(f"Generating image via Forge ({model}) -> {path}")
        response = requests.post(FORGE_ENDPOINT + endpoint, json=payload, timeout=300)
        response.raise_for_status()

        images = response.json().get("images") or []
        if not images:
            raise ValueError("No image data in Forge response")

        with open(path, "wb") as f:
            f.write(base64.b64decode(images[0]))

    # Add the /image command
    @app_commands.command(
        name="image", description="Generate an image with local AI."
    )
    @app_commands.describe(prompt="The prompt to generate an image from.")
    async def image(self, interaction: discord.Interaction, prompt: str):
        """Generate an image with local AI."""
        await self.handle_image_generation(interaction, prompt=prompt)

    # Add the /low-poly command
    @app_commands.command(
        name="lowpoly", description="Generate a low-poly image with local AI."
    )
    @app_commands.describe(prompt="The prompt to generate a low-poly image from.")
    async def lowpoly(self, interaction: discord.Interaction, prompt: str):
        """Generate a low-poly image with local AI."""
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
        text = display_text or f"Generating image: \n{code_block(prompt)}"
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
                interaction.channel, text=f"Failed to generate image: {self.format_api_error(e)}"
            )

        # Send the image
        await self.bot.messaging.send_image(interaction.channel, image_path)

    # Add the /chad command
    @app_commands.command(
        name="chad", description="Generate a chad image with local AI."
    )
    @app_commands.describe(user="The user to generate a chad image of.")
    async def chad(self, interaction: discord.Interaction, user: discord.Member):
        """Generate a chad image with local AI."""
        self.log(
            f"Generating chad image of {user.display_name}: {user.display_avatar.url}"
        )
        image_bytes = requests.get(user.display_avatar.url).content

        # Create a prompt that incorporates the avatar and asks for a chad style image
        prompt = "Generate a image in the same artstyle of this avatar as a gigachad. Personify the avatar with a more muscular body. Use details from the avatar to make the body match the avatar. The outfit and accessories should be similar to the avatar, but designed to show off the muscles. IMPORTANT: Maintain the exact same gender as shown in the avatar - if the avatar appears feminine, keep it feminine; if masculine, keep it masculine. Do not alter or change the gender presentation of the face in any way."

        await self.handle_image_generation(
            interaction=interaction,
            prompt=prompt,
            image=image_bytes,
            display_text=f"Generating chad image of {user.display_name}...",
        )

    # Add the /troll command
    @app_commands.command(
        name="troll", description="Generate a troll image with local AI."
    )
    @app_commands.describe(user="The user to generate a troll image of.")
    async def troll(self, interaction: discord.Interaction, user: discord.Member):
        """Generate a troll image with local AI."""
        image_bytes = requests.get(user.display_avatar.url).content

        await self.handle_image_generation(
            interaction=interaction,
            prompt="This character as a stupid troll",
            image=image_bytes,
            display_text=f"Generating {user.display_name} as a troll...",
        )

    # Add the /remix command
    @app_commands.command(
        name="remix", description="Generate a remix image with local AI."
    )
    @app_commands.describe(user="The user to generate a remix image of.")
    @app_commands.describe(prompt="The prompt to generate a remix image of.")
    async def remix(
        self, interaction: discord.Interaction, user: discord.Member, prompt: str
    ):
        """Generate a remix of a discord user's avatar with local AI."""
        self.log(
            f"Generating remix image of {user.display_name}: {user.display_avatar.url} with prompt: {prompt}"
        )
        image_bytes = requests.get(user.display_avatar.url).content

        await self.handle_image_generation(
            interaction=interaction,
            prompt=prompt,
            image=image_bytes,
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
