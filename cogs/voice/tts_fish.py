import pathlib
import shutil
from typing import List

from gradio_client import Client, handle_file
from pydub import AudioSegment

from cogs.voice.tts_types import TTSGenerator, Voice

API_ENDPOINT = "http://192.168.8.174:7860"


class FishSpeechGenerator(TTSGenerator):
    """Fish-Speech implementation of the TTS generator."""

    def __init__(self, model_dir: pathlib.Path):

        self.name = model_dir.name
        self.reference_audio_mp3 = model_dir / f"{self.name}.mp3"
        self.backing_audio_mp3 = model_dir / f"backing.mp3"
        self.reference_audio_wav = model_dir / f"{self.name}.wav"
        self.reference_transcript = model_dir / f"{self.name}.txt"

    def _ensure_wav_reference(self):
        """Convert MP3 to WAV if WAV doesn't exist or is older than MP3."""
        if not self.reference_audio_wav.exists() or (
            self.reference_audio_mp3.exists()
            and self.reference_audio_mp3.stat().st_mtime
            > self.reference_audio_wav.stat().st_mtime
        ):
            if self.reference_audio_mp3.exists():
                print(f"Converting {self.reference_audio_mp3} to WAV format...")
                audio = AudioSegment.from_mp3(str(self.reference_audio_mp3))
                audio.export(str(self.reference_audio_wav), format="wav")
                print(f"Converted to {self.reference_audio_wav}")
            else:
                raise FileNotFoundError(
                    f"Reference audio file not found: {self.reference_audio_mp3}"
                )

    def save_audio(self, text: str, path: pathlib.Path):
        # Ensure we have a WAV file for the Fish Speech API
        self._ensure_wav_reference()

        # Create a new Gradio client for each request
        client = Client(API_ENDPOINT)

        # Generate audio using Gradio client
        print(f"Generating audio for {text}")
        generated_audio_path, error_message = client.predict(
            text=text,
            reference_id="",
            reference_audio=handle_file(str(self.reference_audio_wav)),
            reference_text=self.reference_transcript.read_text(),
            max_new_tokens=0,
            chunk_length=200,
            top_p=0.7,
            repetition_penalty=1.2,
            temperature=0.7,
            seed=0,
            use_memory_cache="off",
            api_name="/partial",
        )

        # Check for errors
        if error_message:
            raise RuntimeError(f"Fish-Speech generation failed: {error_message}")

        # Check if the generated audio file exists
        if not generated_audio_path or not pathlib.Path(generated_audio_path).exists():
            raise RuntimeError(
                f"Generated audio file not found: {generated_audio_path}"
            )

        # Copy the generated audio to the target path
        shutil.copy(generated_audio_path, path)
        print(f"Saved audio to {path}")

        # Special case: Some voices will have a backing mp3 track.
        # We need to mix the backing track with the generated audio.
        if self.backing_audio_mp3.exists():
            try:
                # Load the generated audio (could be various formats)
                generated_audio = AudioSegment.from_file(str(path))

                # Load the backing track
                backing_audio = AudioSegment.from_mp3(str(self.backing_audio_mp3))

                # Match the length of backing audio to generated audio
                generated_length = len(generated_audio)
                if len(backing_audio) > generated_length:
                    # Trim backing audio to match generated audio length
                    backing_audio = backing_audio[:generated_length]
                elif len(backing_audio) < generated_length:
                    # Loop backing audio to match generated audio length
                    loops_needed = (generated_length // len(backing_audio)) + 1
                    backing_audio = backing_audio * loops_needed
                    backing_audio = backing_audio[:generated_length]

                # Mix the backing track with the generated audio
                # Reduce backing volume to avoid overpowering the speech
                backing_audio = backing_audio - 10  # Reduce by 10dB
                mixed_audio = generated_audio.overlay(backing_audio)

                # Save the mixed audio
                mixed_audio.export(str(path), format="mp3")
                print(f"Mixed audio with backing track to {path}")
            except Exception as e:
                print(f"Warning: Failed to mix backing track: {e}")
                print(f"Keeping original generated audio at {path}")

    def calculate_cost(self, text: str) -> str:
        """Calculate the cost of generating this TTS message."""
        return "$0"  # local TTS generation


def get_fish_voices() -> List[Voice]:
    model_dir = pathlib.Path("models")
    voices: List[Voice] = []
    for model_dir in model_dir.iterdir():
        if model_dir.is_dir():
            # Ensure there is either a .mp3 or .wav file in the model directory
            if not any(model_dir.glob("*.mp3")) and not any(model_dir.glob("*.wav")):
                print(
                    f"Skipping because it doesn't have a .mp3 or .wav file: {model_dir.name}"
                )
                continue

            # print(f"Adding voice {model_dir.name}")
            voice = Voice(
                name=model_dir.name,
                generator=FishSpeechGenerator(model_dir),
                category="Fish",
            )
            avatar_path = model_dir / "avatar.txt"
            if avatar_path.exists():
                voice.avatar = avatar_path.read_text()
                # print(f"Reading avatar from {avatar_path}: {voice.avatar}")

            voices.append(voice)

    return voices
