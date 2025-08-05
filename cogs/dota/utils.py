"""Utility functions for Dota 2 cogs."""

import pathlib
from typing import List, Optional, Tuple

import discord
from dotabase import Ability, Facet, Hero, Item, Response, Voice, dotabase_session

db = dotabase_session()
"""
for hero in db.query(dotabase.Hero):
    print(f"{hero.localized_name} - {url(hero.portrait)}")

for item in db.query(dotabase.Item):
    print(f"{item.localized_name} - {url(item.icon)}")
"""


def dota_wiki_url(hero_name) -> str:
    """Convert a path to a Dota 2 Wiki URL.

    Example:
        dota_wiki_url("Revenant's Brooch") --> https://dota2.fandom.com/wiki/Revenant%27s_Brooch
    """
    path = hero_name.replace(" ", "_").replace("'", "%27")
    return f"https://liquipedia.net/dota2/{path}"


def fandom_url(voice_actor: str) -> str:
    """Convert a voice actor name to a Fandom wiki URL.

    Example:
        fandom_url("Bill Millsap") --> https://dubbing.fandom.com/wiki/Bill_Millsap
    """
    path = voice_actor.replace(" ", "_")
    return f"https://dubbing.fandom.com/wiki/{path}"


def dotabase_url(path) -> str:
    """Convert a dotabase path to a URL."""
    return f"https://dotabase.dillerm.io/vpk{path}"


def get_heroes() -> List[Hero]:
    """Get all heroes from dotabase."""
    return db.query(Hero).all()


def get_hero_by_name(name: str) -> Optional[Hero]:
    """Get a hero by name."""
    return db.query(Hero).filter(Hero.localized_name == name).first()


def get_facets() -> List[Facet]:
    """Get all facets from dotabase. Exclude facets with no name."""
    return [
        facet for facet in db.query(Facet).all() if facet.localized_name is not None
    ]


def get_abilities() -> List[Ability]:
    """Get all abilities from dotabase."""
    return db.query(Ability).all()


def get_items() -> List[Item]:
    """Get items from dotabase with a few filters."""
    items = []
    for item in db.query(Item).all():
        assert isinstance(item, Item)
        # Skip items with underscores in their name.
        if "_" in item.localized_name:
            continue
        # Skip items that are not in the shop.
        if item.cost is None or item.cost == 0:
            # Neutral items have no cost but do have a tier.
            if item.neutral_tier is None:
                continue

        # Skip enhancement items.
        if item.is_neutral_enhancement:
            continue

        # Skip recipes.
        if "Recipe" in item.localized_name:
            continue

        # Skip upgrades (like Dagon 2-5).
        if item.base_level and item.base_level > 1:
            continue

        items.append(item)
    return items


def chunks(lst: List, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_icons_to_servers(
    bot: discord.Client,
    icon_dir: pathlib.Path,
    servers: List[int],
    chunk_size: int = 50,
) -> Tuple[int, int]:
    """Upload icons to multiple servers in chunks.

    Args:
        bot: The Discord bot instance
        icon_dir: Directory containing the icons
        servers: List of server IDs to upload to
        chunk_size: Number of icons to upload per server

    Returns:
        Tuple of (successful uploads, total icons)
    """
    icons = list(
        icon_dir.glob("*.png")
    )  # Convert generator to list for len() and reuse
    successful = 0

    # First, check available slots in each server
    server_slots = {}
    for server_id in servers:
        guild = discord.utils.get(bot.guilds, id=server_id)
        if not guild:
            continue
        current_emojis = len(guild.emojis)
        available_slots = 50 - current_emojis
        if available_slots > 0:
            server_slots[server_id] = available_slots

    if not server_slots:
        print("No servers have available emoji slots")
        return 0, len(icons)

    # Distribute icons across servers based on available slots
    current_icon_index = 0
    while current_icon_index < len(icons) and server_slots:
        for server_id, available_slots in list(server_slots.items()):
            if current_icon_index >= len(icons):
                break

            guild = discord.utils.get(bot.guilds, id=server_id)
            if not guild:
                del server_slots[server_id]
                continue

            # Process up to available_slots icons for this server
            icons_to_process = min(available_slots, len(icons) - current_icon_index)
            for i in range(icons_to_process):
                icon = icons[current_icon_index + i]
                name = (
                    icon.name.replace(".png", "")
                    .replace("-", "")
                    .replace("_", "")
                    .replace("'", "")
                )

                # Check if emoji already exists
                if any(emoji.name == name for emoji in guild.emojis):
                    print(f"Emoji {name} already exists in {guild.name}")
                    continue

                try:
                    with open(icon, "rb") as f:
                        await guild.create_custom_emoji(name=name, image=f.read())
                    successful += 1
                except Exception as e:
                    print(f"Error uploading {name} to {guild.name}: {e}")

            current_icon_index += icons_to_process
            available_slots -= icons_to_process

            # Remove server if it's full
            if available_slots <= 0:
                del server_slots[server_id]
            else:
                server_slots[server_id] = available_slots

    return successful, len(icons)


def get_all_voice_responses() -> List[Response]:
    """Return all voice responses from dotabase."""
    return db.query(Response).all()


def find_voice_responses_by_text(text: str) -> List[Response]:
    """Return all voice responses containing the given text (case-insensitive)."""
    return db.query(Response).filter(Response.text.ilike(f"%{text}%")).all()


def find_voice_responses_by_hero(hero_name: str) -> List[Response]:
    """Return all voice responses for a given hero name (case-insensitive)."""
    hero = db.query(Hero).filter(Hero.localized_name.ilike(hero_name)).first()
    if not hero:
        return []
    return db.query(Response).filter(Response.hero_id == hero.id).all()


def find_voice_responses_exact(text: str) -> List[Response]:
    """Return all voice responses that exactly match the given text."""
    return db.query(Response).filter(Response.text == text).all()


def get_voice(voice_id: int) -> Voice:
    """Get a voice by ID."""
    return db.query(Voice).filter(Voice.id == voice_id).first()


if __name__ == "__main__":
    ability = db.query(Ability).filter(Ability.localized_name == "Arcane Bolt").first()
    print(f"ability.facet_id: {ability.facet_id}")
    print(f"ability.innate: {ability.innate}")

    name = "Special Reserve"
    ability = db.query(Ability).filter(Ability.localized_name == name).first()
    print(f"[{name}] {ability}")
    print(f"[{name}] ability.facet_id: {ability.facet_id}")
    print(f"[{name}] ability.innate: {ability.innate}")
    print(f"[{name}] ability.facet: {ability.facet}")
    print(f"[{name}] ability.hero: {ability.hero}")

    for hero in get_heroes():
        for ability in hero.abilities:
            if "_" in ability.localized_name:
                print(f"{ability.localized_name} - {ability.facet_id}")

    response = find_voice_responses_by_text("you people")[0]
    print(response)
    voice = get_voice(response.voice_id)
    print(voice)  # <dotabase.dotabase.Voice object at 0x7fa2fd294c10>
    print(voice.name)  # Announcer: Cave Johnson
    print(
        dotabase_url(voice.icon)
    )  # https://dotabase.dillerm.io/vpk/panorama/images/icon_announcer_psd.png
    print(
        dotabase_url(voice.image)
    )  # https://dotabase.dillerm.io/vpk/panorama/images/econ/announcer/cave_johnson_ti11_png.png
    print(
        dota_wiki_url(voice.url)
    )  # https://liquipedia.net/dota2/Cave_Johnson_Announcer_Pack
    print(voice.media_name)  # announcer_dlc_cavej
    print(voice.voice_actor)  # None
    print(voice.hero_id)  # None
    print(voice.criteria)  # None

    voice = find_voice_responses_by_text("biggest banana slug")[0].voice
    print(voice)
    print(voice.name)  # Monkey King
    print(
        dotabase_url(voice.icon)
    )  # https://dotabase.dillerm.io/vpk/panorama/images/heroes/icons/npc_dota_hero_monkey_king_png.png
    print(
        dotabase_url(voice.image)
    )  # https://dotabase.dillerm.io/vpk/panorama/images/heroes/selection/npc_dota_hero_monkey_king_png.png
    print(1111)
    print(
        dota_wiki_url(voice.url)
    )  # https://liquipedia.net/dota2/Monkey_King/Responses
    print(voice.media_name)  # monkey_king
    print(voice.voice_actor)  # Bill Millsap
    print(voice.hero_id)  # 114
    print(voice.criteria)  # None
    print(fandom_url(voice.voice_actor))  # https://dubbing.fandom.com/wiki/Bill_Millsap

    print(dotabase_url("/panorama/images/icon_announcer_psd.png"))
