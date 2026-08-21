"""Slay the Spire 2 quiz.

`/slay-quiz` posts a card, relic, potion, enemy, or event's description and players
name it in plain chat. Correct answers pay out embers, tracked per user.

The game loop lives in ``cogs/common/quizgame.py``; this module only supplies the
questions, the hint ladder, and the commands.
"""

from typing import TYPE_CHECKING, FrozenSet, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.common.quizgame import (
    BaseQuizCog,
    Question,
    QuizTheme,
    describe_length,
    fuzzy_match,
    letter_skeleton,
)
from cogs.slay import data

if TYPE_CHECKING:
    from bots.dotabot import DotaBot

STEAM_ART = "https://cdn.cloudflare.steamstatic.com/steam/apps/2868840"

THEME = QuizTheme(
    title="Slay the Spire II Quiz",
    results_title="Slay the Spire II Quiz Results",
    currency="ember",
    currency_key="sts2_ember",
    currency_emoji="🔥",
    play_again_command="/slay-quiz",
    unknown_thumbnail=f"{STEAM_ART}/library_600x900.jpg",
    win_thumbnail=f"{STEAM_ART}/logo.png",
    lose_thumbnail=f"{STEAM_ART}/header.jpg",
)


class SlayQuestion(Question):
    """Name the card/relic/potion/enemy/event from its description.

    The hint ladder walks from pure knowledge to a letter puzzle:
      1. the description alone
      2. + the category (character, rarity, cost, act...)
      3. + a blanked-out skeleton of the answer and its length
      4. + the first letter of each word
    """

    def __init__(
        self,
        prompt: str,
        answer: str,
        category: str,
        image: Optional[str],
        url: Optional[str],
        all_answers: FrozenSet[str],
    ) -> None:
        super().__init__(answer=answer, category=category, image=image, url=url)
        self.prompt = prompt
        self.all_answers = all_answers

    @property
    def phase_count(self) -> int:
        return 4

    def phase_body(self, phase: int) -> str:
        body = f"**Name it:**\n\n{self.prompt}"

        if phase >= 2:
            body += f"\n\n**Category:** {self.category}"

        if phase >= 3:
            revealed = 1 if phase >= 4 else 0
            skeleton = letter_skeleton(self.answer, revealed=revealed)
            body += f"\n**Answer:** `{skeleton}` {describe_length(self.answer)}"

        return body

    def phase_footer(self, phase: int) -> Optional[str]:
        return {
            2: "*Here's a hint!*",
            3: "*Here's the shape of it!*",
            4: "*First letters are free!*",
        }.get(phase)

    def check(self, guess: str) -> bool:
        # Close counts, but not if the guess looks more like a different answer.
        return fuzzy_match(guess, self.answer, self.all_answers)


class SlayQuiz(BaseQuizCog):
    @property
    def theme(self) -> QuizTheme:
        return THEME

    def log(self, message: str) -> None:
        self.bot.log(f"[SlayQuiz] {message}")

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready fires again on every reconnect; the snapshot can't change while
        # the process is up, so only read it once.
        if not self.questions:
            self.load_questions()

    def load_questions(self) -> None:
        """Build the question list from the committed data snapshot."""
        records = data.load_records()
        answers = frozenset(record["answer"] for record in records)

        self.questions = [
            SlayQuestion(
                prompt=record["prompt"],
                answer=record["answer"],
                category=record["category"],
                image=record["image"],
                url=record["url"],
                all_answers=answers,
            )
            for record in records
        ]

        counts: dict = {}
        for question in self.questions:
            kind = question.category.split(" — ")[0]
            counts[kind] = counts.get(kind, 0) + 1
        for kind, count in sorted(counts.items(), key=lambda item: -item[1]):
            self.log(f"Loaded {count} {kind.lower()} questions.")
        self.log(f"Loaded {len(self.questions)} Slay the Spire II questions.")

    @app_commands.command(
        name="slay-quiz", description="Play the Slay the Spire II quiz"
    )
    async def slay_quiz(self, interaction: discord.Interaction):
        await self.bot.messaging.send_embed(interaction, text="Starting the quiz!")
        await self.start_quiz(interaction.channel)

    @app_commands.command(
        name="slay-top", description="List users with the most embers"
    )
    async def slay_top(self, interaction: discord.Interaction):
        """Sends a list of the users with the most embers."""
        # Only look up users who have actually scored - each lookup is an API call.
        balances = []
        for user_id in self.bot.database.get_all_users():
            embers = self.bot.database.get_user_setting(user_id, THEME.currency_key, 0)
            if embers:
                balances.append((user_id, embers))

        balances.sort(key=lambda item: item[1], reverse=True)

        text = ""
        for rank, (user_id, embers) in enumerate(balances[:10]):
            medal = {0: ":crown:", 1: ":second_place:", 2: ":third_place:"}.get(
                rank, ""
            )
            user = await self.bot.fetch_user(int(user_id))
            text += (
                f"{rank + 1}. **{user.display_name}**: "
                f"{embers} {THEME.currency_emoji} {medal}\n"
            )

        if not text:
            text = f"Nobody has any embers yet! Play {THEME.play_again_command}."

        await self.bot.messaging.send_embed(
            interaction,
            title="Top Ascenders",
            text=text,
            thumbnail=THEME.win_thumbnail,
        )

    @app_commands.command(name="embers", description="Check your current ember balance")
    async def embers(self, interaction: discord.Interaction):
        """Sends the user's current ember balance."""
        embers = self.bot.database.get_user_setting(
            interaction.user.id, THEME.currency_key, 0
        )
        await self.bot.messaging.send_embed(
            interaction,
            text=(
                f"{interaction.user.mention}, you have "
                f"**{embers}** {THEME.currency_emoji}"
            ),
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(SlayQuiz(bot))
