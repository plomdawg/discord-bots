"""Piper TTS implementation of the TTS generator."""

import pathlib
import wave
from typing import List

import requests
from piper import PiperVoice

from cogs.voice.tts_types import TTSGenerator, Voice

# Voice configurations
VOICES = [
    {
        "name": "Lessac",
        "alias": "Piper",
        "language": "en_US",
        "quality": "medium",
        "description": "A clear, professional American English voice",
        "category": "Piper TTS (local)",
        "avatar": "https://i.imgur.com/WSK1NDK.png",
    },
    {
        "name": "Bryce",
        "language": "en_US",
        "quality": "medium",
        "description": "A clear, professional American English voice",
        "category": "Piper TTS (local)",
        "avatar": "https://i.imgur.com/x1kEi7m.png",
    },
    {
        "name": "Norman",
        "language": "en_US",
        "quality": "medium",
        "description": "A clear, professional American English voice",
        "category": "Piper TTS (local)",
        "avatar": "https://i.imgur.com/Jb6bAIQ.png",
    },
]


class PiperGenerator(TTSGenerator):
    """Piper implementation of the TTS generator."""

    def __init__(self, voice_path: str, config_path: str):
        """Initialize the Piper TTS generator.

        Args:
            voice_path: Path to the voice model file (.onnx)
            config_path: Path to the voice config file (.json)
        """
        self.voice_path = voice_path
        self.config_path = config_path
        self._voice = None

    @property
    def voice(self) -> PiperVoice:
        """Lazy load the voice model when needed."""
        if self._voice is None:
            self._voice = PiperVoice.load(self.voice_path, self.config_path)
        return self._voice

    def save_audio(self, text: str, path: pathlib.Path) -> pathlib.Path:
        """Generate audio bytes from text using the specified voice.

        Args:
            text: The text to convert to speech
            path: The path to save the audio file

        Returns:
            pathlib.Path: The path to the saved audio file
        """
        # Generate audio using Piper
        wav_path = path.with_suffix(".wav")
        with wave.open(str(wav_path), "wb") as wav_file:
            self.voice.synthesize(text, wav_file)

        # Convert WAV to MP3 using pydub
        from pydub import AudioSegment

        audio = AudioSegment.from_wav(str(wav_path))
        audio.export(str(path), format="mp3")

        # Clean up the temporary WAV file
        wav_path.unlink()

        return path

    def calculate_cost(self, text: str) -> str:
        """Calculate the cost of generating this TTS message."""
        return "$0"  # local TTS generation


def download_file(url: str, path: pathlib.Path) -> bool:
    """Download a file to a path.

    Args:
        url: URL to download from
        path: Path to save the file to

    Returns:
        bool: True if download was successful
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(path, "wb") as f:
            for data in response.iter_content(8192):
                f.write(data)
        return True
    except Exception as e:
        if path.exists():
            path.unlink()
        return False


def get_piper_voices() -> List[Voice]:
    """Get the available Piper voices."""
    voices: List[Voice] = []

    # Get the models directory
    models_dir = pathlib.Path("models/piper")
    models_dir.mkdir(parents=True, exist_ok=True)

    # Download all voices if not present
    for voice_config in VOICES:
        name = voice_config.get("name", "").lower()
        language = voice_config.get("language", "")
        quality = voice_config.get("quality", "")
        voice_path = models_dir / f"{name}-{language}-{quality}.onnx"
        config_path = models_dir / f"{name}-{language}-{quality}.onnx.json"

        if not voice_path.exists() or not config_path.exists():
            # Download from Piper's model repository with correct version and download parameters
            # https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx
            #
            # https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.json
            base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/{language.split('_')[0]}/{language}/{name}/{quality}/{language}-{name}-{quality}"
            download_file(f"{base_url}.onnx?download=true", voice_path)
            download_file(f"{base_url}.onnx.json?download=true", config_path)

        voice_name = voice_config.get("alias", voice_config.get("name", ""))
        voices.append(
            Voice(
                name=voice_name,
                description=voice_config.get("description", ""),
                category=voice_config.get("category", ""),
                avatar=voice_config.get("avatar", ""),
                generator=PiperGenerator(str(voice_path), str(config_path)),
            )
        )

    return voices
