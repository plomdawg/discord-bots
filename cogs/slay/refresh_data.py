"""Refresh the committed Slay the Spire 2 data snapshot.

Pulls the bulk export from spire-codex (a community project that extracts game data
from the Godot/C# build) and writes the pools the quiz uses into ``data/sts2/``.

Run it from the service directory with ``make refresh-sts2``, or directly:

    python -m cogs.slay.refresh_data

Only the standard library is used on purpose: nothing new lands in requirements.txt,
so a data refresh stays a container *restart* rather than an image rebuild.

Notes for whoever runs this after a game patch:
  * StS2 is in early access and patches roughly every two weeks, and those patches
    *change content* - cards get added, reworked, and removed. Re-run this, then read
    `git diff --stat data/sts2/` before committing so you know what moved.
  * The export endpoint serves the *stable* branch, which is what we want to quiz on.
  * The export endpoint rate-limits at 10 requests/minute (much tighter than the 300
    the per-resource endpoints allow). This script makes exactly one request.
  * There is no game-version endpoint - /api/versions returns []. So the snapshot
    records the export's Last-Modified header and the entry counts instead.
"""

import io
import json
import pathlib
import urllib.request
import zipfile

EXPORT_URL = "https://spire-codex.com/api/exports/eng"

# The five pools the quiz draws questions from.
WANTED = ("cards.json", "relics.json", "potions.json", "monsters.json", "events.json")

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "sts2"

USER_AGENT = "plomdawg-discord-bots/1.0 (+https://github.com/plomdawg/discord-bots)"


def refresh(data_dir: pathlib.Path = DATA_DIR) -> dict:
    """Download the export and write the wanted pools. Returns {filename: count}."""
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {EXPORT_URL} ...")
    request = urllib.request.Request(EXPORT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        last_modified = response.headers.get("Last-Modified", "unknown")

    archive = zipfile.ZipFile(io.BytesIO(body))

    missing = [name for name in WANTED if name not in archive.namelist()]
    if missing:
        raise RuntimeError(f"export is missing expected files: {missing}")

    counts = {}
    for name in WANTED:
        payload = json.loads(archive.read(name))
        # Re-dump so the committed snapshot has a stable, diffable format.
        (data_dir / name).write_text(
            json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        counts[name] = len(payload)
        print(f"  wrote {name:16} {len(payload):>4} entries")

    # Provenance, so a stale snapshot is obvious and diffs are readable.
    lines = [
        f"source: {EXPORT_URL}",
        f"last-modified: {last_modified}",
        "",
    ] + [f"{name}: {count}" for name, count in counts.items()]
    (data_dir / "VERSION").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {'VERSION':16} last-modified={last_modified}")
    return counts


if __name__ == "__main__":
    refresh()
