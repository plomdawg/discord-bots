"""
This file is the main entry point for the Voice bot.
"""

import asyncio

from bot import DiscordBot


class VoiceBot(DiscordBot):
    def __init__(self, name: str):
        super().__init__(name)
        self.prefix = ";"

    async def start(self):
        await self.load_cog("voice.tts", "TTS")
        await super().start(token=self.secrets.get("VOICEBOT_DISCORD_SECRET_TOKEN"))

    async def on_ready(self):
        await super().on_ready()

        # Change presence to "Playing AI voices | ;help"
        await self.set_activity(f"Playing AI voices | {self.prefix}help")


async def main():
    bot = await VoiceBot.create("Voice Bot")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
