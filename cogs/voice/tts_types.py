import pathlib
from typing import Protocol


class TTSGenerator(Protocol):
    """Protocol defining the interface for a TTS generator."""

    def calculate_cost(self, text: str) -> str:
        """Calculate the cost of generating this TTS message.

        Args:
            text: The text to calculate cost for

        Returns:
            str: Formatted cost string like "$0.001"
        """
        ...

    def save_audio(self, text: str, path: pathlib.Path) -> pathlib.Path:
        """Generate audio bytes from text using the specified voice.

        Args:
            text: The text to convert to speech
            path: The path to save the audio file

        Returns:
            pathlib.Path: The path to the saved audio file
        """
        ...


class Voice:
    """An AI voice."""

    def __init__(
        self,
        name: str,
        category: str,
        generator: TTSGenerator,
        avatar: str = "",
        description: str = "",
    ):
        self.name = name
        self.category = category
        self.generator = generator
        self.avatar = avatar
        self.description = description

    def calculate_cost(self, text: str) -> str:
        """Calculate the cost of generating this TTS message."""
        return self.generator.calculate_cost(text)

    def save_audio(self, text: str, path: pathlib.Path):
        """Generate audio file from text to the specified path."""
        return self.generator.save_audio(text, path)
