"""ElevenLabs implementation of the TTS generator."""

import pathlib
from typing import List

from elevenlabs.client import ElevenLabs

from cogs.voice.tts_types import TTSGenerator, Voice

AVATARS = {
    "Cooper": "https://i.imgur.com/3kXop0E.png",
    "Sexy": "https://i.imgur.com/xzeKYDH.png",
}


NAMES = {
    "Sexy Female Villain Voice": "Sexy",
}


class ElevenLabsGenerator(TTSGenerator):
    """ElevenLabs implementation of the TTS generator."""

    def __init__(self, client: ElevenLabs, voice_id: str):
        self.client = client
        self.voice_id = voice_id

    def save_audio(self, text: str, path: pathlib.Path) -> pathlib.Path:
        """Generate audio bytes from text using the specified voice.

        Args:
            text: The text to convert to speech
            path: The path to save the audio file

        Returns:
            pathlib.Path: The path to the saved audio file
        """
        audio_iterator = self.client.text_to_speech.convert(
            text=text,
            voice_id=self.voice_id,
            output_format="mp3_44100_128",
        )
        # Save the audio to the path.
        with open(path, "wb") as f:
            for chunk in audio_iterator:
                f.write(chunk)
        return path

    def calculate_cost(self, text: str) -> str:
        """Calculate the cost of generating this TTS message.

        Args:
            text: The text to calculate cost for

        Returns:
            str: Formatted cost string
        """
        # Starter tier gives 40,000 characters per month for $5
        cost_per_character = 5 / 40000
        cost = round(len(text) * cost_per_character, 8)
        return f"${cost}"


def get_elevenlabs_voices(api_key: str) -> List[Voice]:
    """Get the voices from ElevenLabs."""
    voices: List[Voice] = []
    client = ElevenLabs(api_key=api_key)
    response = client.voices.get_all()
    for voice in response.voices:
        if not voice.name:
            continue
        name = NAMES.get(voice.name, voice.name)
        category = f"ElevenLabs {voice.category}"
        voices.append(
            Voice(
                name=name,
                description=voice.description or "",
                category=category,
                avatar=AVATARS.get(name, ""),
                generator=ElevenLabsGenerator(client, voice.voice_id),
            )
        )
    return voices
