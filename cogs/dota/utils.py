"""Utility functions for Dota 2 cogs."""

import pathlib
import re
from typing import Awaitable, Callable, List, Optional, Tuple

import discord
import requests
from dotabase import Ability, Hero, Item, Response, Voice, dotabase_session

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


def emoji_name(name: str) -> str:
    """Normalize a name into a valid Discord emoji name.

    Discord only accepts [A-Za-z0-9_] in emoji names, so "Anti-Mage" and
    "Nature's Prophet" must lose their punctuation. Both the uploader and the
    lookup in Emojis.get() must apply this SAME transform -- when they differed
    (get() stripped only spaces) those two heroes could never resolve an emoji.
    """
    return re.sub(r"[^A-Za-z0-9_]", "", name)


async def download_hero_icons(
    icon_dir: pathlib.Path,
    heroes: List[Hero],
    progress: Optional[Callable[[str, str, int, int], Awaitable[None]]] = None,
) -> List[pathlib.Path]:
    """Download hero icons from dotabase into icon_dir.

    dotabase already serves every hero icon (~2-3KB PNGs, far under Discord's
    256KB emoji cap), so no wiki scraping is needed. Files are named with
    emoji_name() so the uploader derives the right emoji name from the filename.

    Args:
        progress: Optional async callback `(hero_name, status, done, total)`,
            where status is "downloaded", "cached" or "failed: <reason>".

    Returns the paths that are on disk and ready to upload.
    """
    icon_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for hero in heroes:
        if not hero.icon:
            continue
        name = hero.localized_name
        path = icon_dir / f"{emoji_name(name)}.png"
        if path.exists():
            paths.append(path)
            if progress:
                await progress(name, "cached", len(paths), len(heroes))
            continue
        try:
            response = requests.get(dotabase_url(hero.icon), timeout=30)
            response.raise_for_status()
            path.write_bytes(response.content)
            paths.append(path)
            if progress:
                await progress(name, "downloaded", len(paths), len(heroes))
        except Exception as e:
            print(f"Error downloading icon for {name}: {e}")
            if progress:
                await progress(name, f"failed: {e}", len(paths), len(heroes))
    return paths


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
    icons: Optional[List[pathlib.Path]] = None,
    progress: Optional[Callable[[str, str, str, int, int], Awaitable[None]]] = None,
) -> Tuple[int, int]:
    """Upload icons to multiple servers in chunks.

    Args:
        bot: The Discord bot instance
        icon_dir: Directory containing the icons
        servers: List of server IDs to upload to
        chunk_size: Number of icons to upload per server
        icons: Explicit icons to upload. Defaults to every PNG in icon_dir.
            Prefer passing only the icons you actually need: the loop below
            advances current_icon_index past icons it *skips* as already
            existing, so a full directory can burn the free-slot budget before
            reaching the new ones.
        progress: Optional async callback invoked once per icon as
            `(name, emoji, status, done, total)`, where `emoji` is the rendered
            emoji string (empty unless status is "uploaded") and `status` is
            "uploaded", "exists" or "failed: <reason>". Lets callers stream a
            live list; keep the callback cheap and throttle any message edits.

    Returns:
        Tuple of (successful uploads, total icons)
    """
    if icons is None:
        # Convert generator to list for len() and reuse
        icons = list(icon_dir.glob("*.png"))
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
                name = emoji_name(icon.stem)

                # Check if emoji already exists
                if any(emoji.name == name for emoji in guild.emojis):
                    print(f"Emoji {name} already exists in {guild.name}")
                    if progress:
                        await progress(name, "", "exists", successful, len(icons))
                    continue

                try:
                    with open(icon, "rb") as f:
                        created = await guild.create_custom_emoji(
                            name=name, image=f.read()
                        )
                    successful += 1
                    if progress:
                        await progress(
                            name, str(created), "uploaded", successful, len(icons)
                        )
                except Exception as e:
                    print(f"Error uploading {name} to {guild.name}: {e}")
                    if progress:
                        await progress(
                            name, "", f"failed: {e}", successful, len(icons)
                        )

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
    print(f"ability.innate: {ability.innate}")

    name = "Special Reserve"
    ability = db.query(Ability).filter(Ability.localized_name == name).first()
    print(f"[{name}] {ability}")
    print(f"[{name}] ability.innate: {ability.innate}")
    print(f"[{name}] ability.hero: {ability.hero}")

    for hero in get_heroes():
        for ability in hero.abilities:
            if "_" in ability.localized_name:
                print(ability.localized_name)

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
