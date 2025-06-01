"""
This cog provides Dota 2 wiki-related functionality.
"""

import json
import pathlib
from typing import TYPE_CHECKING, Any, List, Tuple, TypeVar

import discord
import requests
from bs4 import BeautifulSoup, Tag
from discord.ext import commands

from cogs.common.utils import PLOMBOT_DEV_GUILD
from cogs.dota.emojis import ICON_DIR

if TYPE_CHECKING:
    from bots.dotabot import DotaBot

DOTA_WIKI_URL = "https://dota2.gamepedia.com"

RUNE_DATA = pathlib.Path("data/runes.json")

T = TypeVar("T")


from dataclasses import dataclass
from typing import List


@dataclass
class Rune:
    name: str
    icon: str  # URL of the icon image
    gif: str  # URL of the gif image
    model: str  # URL of the model image
    bottle: str  # URL of the bottle image
    description: str  # Description of the rune
    stats: List[str]  # List of stats


def save_data(data: List[Any], filepath: pathlib.Path) -> None:
    """Save a list of objects to a JSON file.

    Args:
        data: List of objects to save
        filepath: Path to save the JSON file to
    """
    # Create parent directories if they don't exist
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Convert objects to dictionaries
    data_dicts = [obj.__dict__ for obj in data]

    # Save to JSON file
    with open(filepath, "w") as f:
        json.dump(data_dicts, f, indent=2)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def scrape_rune_data():
    """Scrape rune data from the Dota 2 wiki."""
    runes = []  # type: List[Rune]
    url = f"{DOTA_WIKI_URL}/Runes#List"
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser")
    for rune in soup.find_all("table", class_="wikitable"):
        # Get name from the first th element
        name_elem = rune.find("th")  # type: Tag
        if not name_elem:
            continue
        name_link = name_elem.find("a")  # type: Tag
        if not name_link:
            continue
        name = name_link.text.strip()

        # Get description from the second th element
        desc_elem = name_elem.find_next("th")  # type: Tag
        if not desc_elem:
            continue
        desc_i = desc_elem.find("i")  # type: Tag
        if not desc_i:
            continue
        description = desc_i.text.strip()

        # Get icon URL
        icon_elem = rune.find(
            "img", {"data-image-key": lambda x: x and "minimap_icon" in x}
        )  # type: Tag
        icon = icon_elem.get("data-src") if icon_elem else ""

        # Get gif URL
        gif_elem = rune.find(
            "img", {"data-image-key": lambda x: x and "gif" in x}
        )  # type: Tag
        gif = gif_elem.get("data-src") if gif_elem else ""

        # Get model URL
        model_elem = rune.find(
            "img", {"data-image-key": lambda x: x and "model" in x}
        )  # type: Tag
        model = model_elem.get("data-src") if model_elem else ""

        # Get bottle URL
        bottle_elem = rune.find(
            "img", {"data-image-key": lambda x: x and "Bottle" in x}
        )  # type: Tag
        bottle = bottle_elem.get("data-src") if bottle_elem else ""

        # Get stats from the td elements
        stats = []
        for td in rune.find_all("td"):  # type: Tag
            # Only get stats from the first column of the table
            if td.get("style") and "width: 40%" in td.get("style"):
                for b in td.find_all("b"):
                    stat_text = b.next_sibling
                    if stat_text:
                        stat_text = stat_text.strip()
                        if stat_text:
                            stats.append(f"{b.text.strip()}: {stat_text}")

        rune_obj = Rune(
            name=name,
            icon=icon,
            gif=gif,
            model=model,
            bottle=bottle,
            description=description,
            stats=stats,
        )
        runes.append(rune_obj)

    # Save the scraped data
    save_data(runes, RUNE_DATA)
    return runes


class DotaWiki(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot

        # Load rune data if it doesn't exist.
        if not RUNE_DATA.exists():
            self.log(f"Rune data not found, downloading from Dota 2 wiki...")
            scrape_rune_data()

        self.runes = json.load(RUNE_DATA.open())
        self.log(f"Loaded {len(self.runes)} runes")

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[DotaWiki] {message}")

    async def _download_icon(self, url: str, name: str) -> bool:
        """Download a single icon from a URL."""
        try:
            req = requests.get(url)
            path = ICON_DIR / name
            with open(path, "wb") as f:
                f.write(req.content)
            return True
        except Exception as e:
            self.log(f"Error downloading icon {name}: {e}")
            return False

    async def _get_all_icons(self, url: str) -> List[Tag]:
        """Get all icons from a Dota 2 wiki page."""
        icons = []
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")
        icons = soup.find_all("img")
        return icons

    async def _scrape_rune_icons(self, url: str) -> Tuple[int, int]:
        """Scrape rune icons from a Dota 2 wiki page.

        Args:
            url: The URL to scrape from

        Returns:
            Tuple of (successful downloads, total icons found)
        """
        try:
            page = requests.get(url)
            soup = BeautifulSoup(page.text, "html.parser")
            icons = soup.find_all("img")

            # Filter for rune icons
            icons = [
                icon
                for icon in icons
                if isinstance(icon, Tag) and "minimap_icon" in (icon.get("src") or "")
            ]

            successful = 0
            for icon in icons:
                if not isinstance(icon, Tag):
                    continue

                alt = icon.get("alt")
                if not isinstance(alt, str):
                    continue

                name = alt.replace(" ", "_").replace("_minimap_icon", "")
                url = icon.get("data-src") or icon.get("src")
                if not url:
                    continue

                if await self._download_icon(url, name):
                    successful += 1

            return successful, len(icons)

        except Exception as e:
            self.log(f"Error scraping rune icons: {e}")
            return 0, 0

    @discord.app_commands.command(
        name="scrape_icons",
        description="Scrape hero and rune icons from the Dota 2 wiki.",
    )
    @discord.app_commands.guilds(PLOMBOT_DEV_GUILD)
    async def scrape_icons(self, interaction: discord.Interaction):
        """Scrape hero and rune icons from the Dota 2 wiki."""
        message = await self.bot.messaging.send_embed(
            interaction,
            title="Scraping Icons",
            text="Starting to scrape icons from the Dota 2 wiki...",
        )

        # Scrape rune icons
        rune_success, rune_total = await self._scrape_rune_icons(
            f"{DOTA_WIKI_URL}/Runes#List"
        )

        # Send results
        await self.bot.messaging.edit_embed(
            message,
            title="Icon Scraping Complete",
            text=(f"Successfully scraped {rune_success}/{rune_total} rune icons!\n"),
            color=discord.Color.green(),
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(DotaWiki(bot))
