# Discord Bots

A collection of Discord bots with shared functionality, built using discord.py. This project is designed to maintain multiple specialized bots while sharing common code and functionality.

## Features

### Dotabot
- Voiceline playback
- Shopkeeper's Quiz
- Dota Wiki scraper

### Musicbot
- Music playback and playlist management
- Queue management
- Audio controls (volume, skip, pause)
- Spotify and YouTube support

### Voicebot
- AI Text-to-speech capabilities with multiple voice options:
  - Piper voices
  - Fish TTS voices
  - ElevenLabs voices
- AI Image Generation using Gemini:
  - Generate images from text prompts
  - User avatar remixing with custom prompts
- Message-based TTS with voice selection

## Project Structure

```
discord-bots/
├── bot.py           # Base DiscordBot class
├── bots/            # Individual bot implementations
│   ├── dotabot.py   # DotA 2 bot
│   ├── musicbot.py  # Music playing bot
│   ├── testbot.py   # Test bot
│   └── voicebot.py  # AI TTS bot
└── cogs/            # Bot functionality modules
    ├── common/      # Shared functionality
    └── dota/        # Dota-specific commands
```

## Setup

1. Clone the repository
2. Export keys as environment variables (see [docker-compose.yml](docker-compose.yml) for full list of keys)
   ```bash
   export DISCORD_BOT_CLIENT_ID="123456789012345678"
   export DISCORD_BOT_SECRET_TOKEN="Abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz"
   ```
3. Run the bots using docker:
   ```bash
   docker compose up
   ```

## Development Setup

Use python3.11

1. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up pre-commit hooks for code quality:
   ```bash
   pre-commit install
   ```

The pre-commit hooks will automatically:
- Sort Python imports using isort
- Validate YAML formatting
- Run on every commit
