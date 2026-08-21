"""Slay the Spire 2 game data for the quiz.

Reads the committed snapshot in ``data/sts2/`` (see ``refresh_data.py`` for how it
gets there) and turns it into quiz-ready records: a prompt, the answer, a rich
category label, an image, and a wiki link.

The five pools are cards, relics, potions, events, and enemies. Enemies are the odd
one out - the export ships them with an empty ``description``, so their prompt is
synthesized from HP and move list.
"""

import json
import pathlib
import re
from typing import Dict, Iterator, List, Optional

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "sts2"

# Images live behind a CDN; the export stores site-relative paths.
IMAGE_BASE = "https://cdn.spire-codex.com"
IMAGE_PREFIX = "/static/images/"

# The wiki keeps Slay the Spire 2 in its own namespace.
WIKI_BASE = "https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2:"

# Card colors that correspond to a playable character.
CHARACTERS = ("ironclad", "silent", "regent", "necrobinder", "defect")


def wiki_url(name: str) -> str:
    """Return the wiki page URL for a name."""
    return WIKI_BASE + name.replace(" ", "_")


def image_url(raw: Optional[str]) -> Optional[str]:
    """Turn an export image path into a CDN URL."""
    if not raw:
        return None
    if raw.startswith(IMAGE_PREFIX):
        return IMAGE_BASE + "/" + raw[len(IMAGE_PREFIX) :]
    return IMAGE_BASE + raw


def strip_markup(text: Optional[str]) -> str:
    """Convert the export's inline markup into Discord-friendly text.

    ``[gold]`` marks game keywords, so those become bold. Other color and effect
    tags carry no meaning worth keeping, so their text is kept and the tags are
    dropped. ``[energy:2]`` and ``[star:1]`` are icon placeholders.
    """
    if not text:
        return ""
    text = re.sub(r"\[energy:(\d+)\]", r"\1 energy", text)
    text = re.sub(r"\[star:(\d+)\]", r"\1★", text)
    text = re.sub(r"\[gold\](.*?)\[/gold\]", r"**\1**", text, flags=re.DOTALL)
    # Anything left is a color or effect tag, or a var placeholder - drop it.
    text = re.sub(r"\[/?[A-Za-z][A-Za-z0-9_]*\]", "", text)
    # Collapse the blank lines that dropped tags can leave behind.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def censor(text: str, answer: str) -> str:
    """Blank the answer out of a prompt so it can't give itself away."""
    if not text or not answer:
        return text
    return re.sub(re.escape(answer), "█" * len(answer), text, flags=re.IGNORECASE)


def _load(filename: str) -> List[dict]:
    """Read one snapshot file."""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _title(value: Optional[str]) -> str:
    """'ironclad' -> 'Ironclad'."""
    return (value or "").replace("_", " ").title()


def _label(prefix: str, parts: List[Optional[str]]) -> str:
    """'Card' + ['Ironclad', 'Rare'] -> 'Card — Ironclad, Rare'.

    Blanks are dropped, and a part that just repeats the prefix or an earlier part
    is skipped - otherwise the export's overlapping rarity/pool values produce
    labels like 'Potion — Event, Event'.
    """
    seen: List[str] = []
    for part in parts:
        if not part:
            continue
        if part == prefix or part in seen:
            continue
        seen.append(part)
    return f"{prefix} — " + ", ".join(seen) if seen else prefix


def _card_cost(card: dict) -> Optional[str]:
    """Human-readable energy or star cost for a card."""
    if card.get("is_x_star_cost"):
        return "X★"
    if card.get("is_x_cost"):
        return "X energy"
    star = card.get("star_cost")
    if star is not None:
        return f"{star}★"
    cost = card.get("cost")
    if cost is None or cost < 0:
        return None
    return f"{cost} energy"


def _card_category(card: dict) -> str:
    """'Card — Ironclad, Rare, 2 energy'."""
    color = card.get("color")
    character = _title(color) if color in CHARACTERS or color == "colorless" else None
    return _label("Card", [character, card.get("rarity"), _card_cost(card)])


def _hp_label(monster: dict) -> Optional[str]:
    """'66' or '66-70'."""
    low, high = monster.get("min_hp"), monster.get("max_hp")
    if low is None:
        return None
    if high is not None and high != low:
        return f"{low}-{high}"
    return str(low)


def _monster_prompt(monster: dict) -> str:
    """Build a prompt for an enemy from its HP and moves."""
    lines = []
    hp = _hp_label(monster)
    if hp:
        lines.append(f"**HP:** {hp}")

    moves = []
    for move in monster.get("moves") or []:
        name = move.get("name")
        if not name:
            continue
        intent = move.get("intent")
        moves.append(f"{name} ({intent})" if intent else name)
    if moves:
        lines.append("**Moves:** " + " · ".join(moves))

    powers = []
    for power in monster.get("innate_powers") or []:
        if not isinstance(power, dict):
            powers.append(str(power))
            continue
        # Powers come through as {"power_id": "ARTIFACT", "amount": 3}.
        name = _title(power.get("power_id") or power.get("name") or "")
        if not name:
            continue
        amount = power.get("amount")
        powers.append(f"{name} {amount}" if amount is not None else name)
    if powers:
        lines.append("**Innate:** " + ", ".join(powers))

    return "\n".join(lines)


def _monster_category(monster: dict) -> str:
    """'Enemy — Act 1 - Overgrowth, Boss'."""
    act = None
    for encounter in monster.get("encounters") or []:
        if encounter.get("act"):
            act = encounter["act"]
            break
    return _label("Enemy", [act, monster.get("type")])


def _event_category(event: dict) -> str:
    """'Event — Act 1 - Overgrowth'."""
    act = event.get("act")
    if act and act != "None":
        return _label("Event", [act])
    return _label("Event", [event.get("type")])


def _relic_category(relic: dict) -> str:
    """'Relic — Boss' / 'Relic — Uncommon, Ironclad'."""
    rarity = (relic.get("rarity") or "").replace("Relic", "").strip()
    pool = relic.get("pool")
    character = _title(pool) if pool and pool != "shared" else None
    return _label("Relic", [rarity, character])


def _potion_category(potion: dict) -> str:
    """'Potion — Rare'."""
    pool = potion.get("pool")
    character = _title(pool) if pool and pool != "shared" else None
    return _label("Potion", [potion.get("rarity"), character])


def _skip_ambiguous_card_names(cards: List[dict]) -> set:
    """Names shared by several characters' cards, e.g. Strike and Defend.

    They make terrible questions - 'Deal 6 damage' has five right answers and the
    category hint would have to lie about which character it is.
    """
    seen: Dict[str, set] = {}
    for card in cards:
        seen.setdefault(card.get("name", ""), set()).add(card.get("color"))
    return {name for name, colors in seen.items() if len(colors) > 1}


def iter_records() -> Iterator[dict]:
    """Yield quiz-ready records from every pool.

    Each record is {prompt, answer, category, image, url}. Entries with no usable
    prompt are skipped, and a name is only ever used once.
    """
    cards = _load("cards.json")
    ambiguous = _skip_ambiguous_card_names(cards)

    for card in cards:
        name = card.get("name")
        if not name or name in ambiguous:
            continue
        yield {
            "prompt": strip_markup(card.get("description")),
            "answer": name,
            "category": _card_category(card),
            "image": image_url(card.get("image_url")),
            "url": wiki_url(name),
        }

    for relic in _load("relics.json"):
        name = relic.get("name")
        if not name:
            continue
        # Relic flavor text is still a placeholder in early access, so only the
        # mechanical description is usable here.
        yield {
            "prompt": strip_markup(relic.get("description")),
            "answer": name,
            "category": _relic_category(relic),
            "image": image_url(relic.get("image_url")),
            "url": wiki_url(name),
        }

    for potion in _load("potions.json"):
        name = potion.get("name")
        if not name:
            continue
        yield {
            "prompt": strip_markup(potion.get("description")),
            "answer": name,
            "category": _potion_category(potion),
            "image": image_url(potion.get("image_url")),
            "url": wiki_url(name),
        }

    for event in _load("events.json"):
        name = event.get("name")
        if not name:
            continue
        yield {
            "prompt": strip_markup(event.get("description")),
            "answer": name,
            "category": _event_category(event),
            "image": None,
            "url": wiki_url(name),
        }

    for monster in _load("monsters.json"):
        name = monster.get("name")
        if not name:
            continue
        yield {
            "prompt": _monster_prompt(monster),
            "answer": name,
            "category": _monster_category(monster),
            "image": image_url(monster.get("image_url")),
            "url": wiki_url(name),
        }


# Discord embed descriptions cap at 4096, but a wall of text makes a bad prompt.
MAX_PROMPT_LENGTH = 700

# A prompt this short carries no information (e.g. an empty card description).
MIN_PROMPT_LENGTH = 8


def load_records() -> List[dict]:
    """Return usable, de-duplicated records with the answer censored out."""
    records = []
    used = set()
    for record in iter_records():
        answer = record["answer"]
        key = answer.upper()
        if key in used:
            continue

        prompt = censor(record["prompt"], answer)
        if len(prompt) < MIN_PROMPT_LENGTH:
            continue
        if len(prompt) > MAX_PROMPT_LENGTH:
            prompt = prompt[:MAX_PROMPT_LENGTH].rsplit(" ", 1)[0] + " …"

        used.add(key)
        record["prompt"] = prompt
        records.append(record)
    return records


if __name__ == "__main__":
    import collections

    all_records = load_records()
    print(f"{len(all_records)} records")
    kinds = collections.Counter(r["category"].split(" — ")[0] for r in all_records)
    for kind, count in kinds.most_common():
        print(f"  {kind:8} {count}")
    print()
    for record in all_records[:3]:
        print(f"--- {record['answer']}  [{record['category']}]")
        print(f"    {record['prompt'][:200]}")
        print(f"    {record['image']}")
        print(f"    {record['url']}")
