"""Split a markdown answer into Discord-sized (<=2000 char) message chunks.

Tries to break on paragraph / line boundaries, and re-opens code fences across a
split so a fenced block never ends up half-open in one message and orphaned in the
next. Falls back to a hard character cut for any single line longer than the limit.
"""

DISCORD_LIMIT = 2000


def _hard_split(text: str, limit: int) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def chunk(text: str, limit: int = DISCORD_LIMIT) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    # Reserve room for a possible re-opened fence line ("```lang\n").
    budget = limit - 12
    chunks: list[str] = []
    current = ""
    open_fence: str | None = None  # the fence token+lang currently open, e.g. "```py"

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.rstrip("\n"))
        current = ""

    for line in text.split("\n"):
        # Track fenced code blocks so we can carry them across chunk boundaries.
        stripped = line.lstrip()
        is_fence = stripped.startswith("```")

        candidate = line if not current else current + "\n" + line
        prefix = (open_fence + "\n") if open_fence else ""

        if len(prefix) + len(candidate) > budget:
            if open_fence:
                current += "\n```"  # close the open fence in this chunk
            flush()
            current = (open_fence + "\n" + line) if open_fence else line
            # A single oversized line: hard-split it.
            if len(current) > budget:
                for piece in _hard_split(current, budget):
                    chunks.append(piece)
                current = ""
        else:
            current = candidate

        if is_fence:
            open_fence = None if open_fence else stripped.rstrip()

    flush()
    return chunks
