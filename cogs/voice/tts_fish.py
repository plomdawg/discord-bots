import pathlib
from typing import List
from urllib.parse import quote

from plomtts import TTSClient
from pydub import AudioSegment, effects

from cogs.voice.tts_types import TTSGenerator, Voice

PLOMTTS_ENDPOINT = "http://192.168.8.175:8420"


def _boost_file(path: pathlib.Path) -> None:
    """Normalize an mp3 to peak 0 dBFS in place (Fish Audio S2 output is quiet).

    The player plays TTS tracks at full volume (see TTS_VOLUME), so normalizing
    the file to the ceiling makes speech as loud as possible without clipping.
    """
    try:
        audio = AudioSegment.from_file(str(path))
        effects.normalize(audio).export(str(path), format="mp3")
    except Exception as e:  # pragma: no cover - best-effort loudness
        print(f"Warning: volume normalize failed: {e}")


def generate_dialogue_audio(turns: list, path: pathlib.Path) -> None:
    """Generate multi-speaker dialogue audio to a path.

    Args:
        turns: ordered list of (voice_id, text) tuples.
        path: output mp3 path.
    """
    client = TTSClient(PLOMTTS_ENDPOINT)
    print(f"Generating dialogue with {len(turns)} turns")
    audio_bytes = client.generate_dialogue(turns=turns)
    path.write_bytes(audio_bytes)
    _boost_file(path)
    print(f"Saved dialogue audio to {path}")


class FishSpeechGenerator(TTSGenerator):
    """Fish-Speech implementation of the TTS generator (via plomtts server)."""

    def __init__(self, name: str):
        """Initialize the FishSpeechGenerator."""
        self.name = name
        self.backing_audio_mp3 = pathlib.Path("models") / name / "backing.mp3"

    def save_audio(self, text: str, path: pathlib.Path):
        """Save the audio to a path."""
        client = TTSClient(PLOMTTS_ENDPOINT)

        print(f"Generating audio for {text!r} using voice {self.name!r}")
        audio_bytes = client.generate_speech(text=text, voice_id=self.name)

        path.write_bytes(audio_bytes)
        print(f"Saved audio to {path}")

        # Special case: some voices have a backing mp3 track to mix in.
        if self.backing_audio_mp3.exists():
            try:
                generated_audio = AudioSegment.from_file(str(path))
                backing_audio = AudioSegment.from_mp3(str(self.backing_audio_mp3))

                generated_length = len(generated_audio)
                if len(backing_audio) > generated_length:
                    backing_audio = backing_audio[:generated_length]
                elif len(backing_audio) < generated_length:
                    loops_needed = (generated_length // len(backing_audio)) + 1
                    backing_audio = backing_audio * loops_needed
                    backing_audio = backing_audio[:generated_length]

                backing_audio = backing_audio - 10  # Reduce by 10dB
                mixed_audio = generated_audio.overlay(backing_audio)
                mixed_audio.export(str(path), format="mp3")
                print(f"Mixed audio with backing track to {path}")
            except Exception as e:
                print(f"Warning: Failed to mix backing track: {e}")

        # Boost loudness for Discord playback.
        _boost_file(path)

    def calculate_cost(self, text: str) -> str:
        """Calculate the cost of generating this TTS message."""
        return "$0"  # local TTS generation


def get_fish_voices() -> List[Voice]:
    """Get the voices from the plomtts server."""
    client = TTSClient(PLOMTTS_ENDPOINT)
    voice_list = client.list_voices()
    return [
        Voice(
            name=v.name,
            generator=FishSpeechGenerator(v.name),
            category="Fish",
            avatar=(
                PLOMTTS_ENDPOINT + quote(v.avatar_url) if v.avatar_url else ""
            ),
        )
        for v in voice_list.voices
    ]
