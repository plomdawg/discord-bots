import re


def format_duration(duration) -> str:
    """Converts a duration into a string like '4h20m'"""
    if duration is None:
        return "?"
    if duration < 60:  # Under a minute
        return "{}s".format(int(duration))
    if duration < 3600:  # Under an hour
        return "{}m{}s".format(int(duration / 60), int(duration % 60))
    # Over an hour
    return "{}h{}m{}s".format(
        int(duration / 3600), int(duration % 3600 / 60), int(duration % 60)
    )


def format_title(title) -> str:
    """Removes "official audio/video" etc from video titles"""
    keywords = [
        " \\(official audio\\)",
        " \\(official video\\)",
        " \\(official music audio\\)",
        " \\(official music video\\)",
        " \\[official audio\\]",
        " \\[official video\\]",
        " \\[official music audio\\]",
        " \\[official music video\\]",
    ]
    title_format = re.compile("|".join(keywords), re.IGNORECASE)
    _title = title.replace("&amp;", "&")
    _title = _title.replace("&quot;", '"')
    return title_format.sub("", _title).strip()


def volume_bar(volume: float) -> str:
    """Returns an ASCII volume bar for the given volume.

    volume_bar(0.25): █████░░░░░░░░░░░░░░░
    """
    length = 20
    filled = int(volume * length)
    unfilled = length - filled
    return "█" * filled + "░" * unfilled
