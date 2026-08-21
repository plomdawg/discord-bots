"""Shopkeeper Quiz.

`/quiz` posts a scrambled Dota name and players unscramble it in plain chat.
Correct answers pay out gold, tracked per user.

The game loop lives in ``cogs/common/quizgame.py``; this module only supplies the
words, the hint ladder, and the commands.
"""

from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.common.quizgame import (
    BaseQuizCog,
    Question,
    Quiz,
    QuizTheme,
    easy_scramble,
    scramble,
)
from cogs.common.utils import MY_DUDES_GUILD
from cogs.dota import utils

if TYPE_CHECKING:
    from bots.dotabot import DotaBot

# Pictures used for the embedded messages.
SHOPKEEPER_IMAGE = "https://i.imgur.com/Xyf1VjQ.png"
SHOPKEEPER_SAD_IMAGE = "https://i.imgur.com/YNEgwBb.png"
UNKNOWN_IMAGE = "https://static.wikia.nocookie.net/dota2_gamepedia/images/5/5d/Unknown_Unit_icon.png/revision/latest/scale-to-width-down/128?cb=20170416184928"

INNATE_ICON = "panorama/images/hud/facets/innate_icon_large_png.png"

THEME = QuizTheme(
    title="Shopkeeper's Quiz",
    results_title="Shopkeeper's Quiz Results",
    currency="gold",
    currency_key="gold",
    currency_emoji="🪙",
    play_again_command="/quiz",
    unknown_thumbnail=UNKNOWN_IMAGE,
    win_thumbnail=SHOPKEEPER_IMAGE,
    lose_thumbnail=SHOPKEEPER_SAD_IMAGE,
)


class Word(Question):
    """Unscramble a Dota name.

    The hint ladder:
      1. the name, hard-scrambled
      2. + the category
      3. the name scrambled with spaces left in place
      4. + the lore, with the answer censored out (only if there is any lore)
    """

    def __init__(self, text, category, image, url, emoji=None, hint=None) -> None:
        super().__init__(
            answer=text, category=category, image=image, url=url, emoji=emoji
        )
        # Kept for readability at the call sites in load_words().
        self.text = text
        self.hint = hint

    @property
    def phase_count(self) -> int:
        # Heroes have no lore hint, so their rounds are three phases.
        return 4 if self.get_hint() else 3

    def get_hint(self) -> Optional[str]:
        """Returns the hint for the word with the word censored."""
        if self.hint:
            return self.hint.replace(self.text, "*" * len(self.text))
        return None

    def phase_body(self, phase: int) -> str:
        # Re-scramble each phase, the way this game has always worked.
        if phase >= 3:
            scrambled = easy_scramble(self.answer)
        else:
            scrambled = scramble(self.answer)
        body = f"**Unscramble:** {scrambled}"

        if phase >= 2:
            body += f"\n**Category:** {self.category} "

        if phase >= 4:
            body += f"\n**Hint:** {self.get_hint()} "

        return body

    def phase_footer(self, phase: int) -> Optional[str]:
        if phase >= 4:
            return "*Here's another hint!*"
        if phase == 3:
            return "*Spaces are in their places!*"
        if phase == 2:
            return "*Here's a hint!*"
        return None

    def phase_thumbnail(self, phase: int) -> Optional[str]:
        # Show an image of the category type once the category is revealed.
        if phase < 2:
            return None
        if self.category == "Innate Abilities":
            return utils.dotabase_url(INNATE_ICON)
        if self.category == "Items":
            return SHOPKEEPER_IMAGE
        return None


class ShopkeeperQuiz(BaseQuizCog):
    @property
    def theme(self) -> QuizTheme:
        return THEME

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[ShopkeeperQuiz] {message}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Load the words when the bot is ready."""
        self.load_words()

    def build_quiz(self, channel) -> Quiz:
        return Quiz(
            bot=self.bot,
            questions=self.questions,
            channel=channel,
            theme=self.theme,
            on_phase_message=self.add_tts_reaction,
        )

    async def add_tts_reaction(self, quiz: Quiz, message: discord.Message) -> None:
        """Offer TTS of the scrambled word, in the my dudes server only."""
        # channel.guild is None in DMs, where there is no voice channel to play into.
        guild = getattr(quiz.channel, "guild", None)
        if guild is None or guild.id != MY_DUDES_GUILD.id:
            return
        try:
            await message.add_reaction("🗣️")
        except discord.errors.NotFound:
            pass

    async def handle_tts(self, message: discord.Message, user: discord.Member):
        """Handle TTS for the current quiz word."""
        # Check if the user is in a voice channel.
        if (
            not user.voice
            or not user.voice.channel
            or not isinstance(user.voice.channel, discord.VoiceChannel)
        ):
            return

        # Get the scrambled word from the embed description.
        if not message.embeds or not message.embeds[0].description:
            return

        description = message.embeds[0].description
        try:
            scrambled = description.split("**Unscramble:** ")[1].split("\n")[0]
        except IndexError:
            return

        # Play the scrambled word using TTS.
        if self.bot.tts is not None:
            await self.bot.tts.play(user.voice.channel, "Axe", scrambled)

    async def handle_reaction_add(self, reaction, user):
        """Handle the TTS reaction, otherwise fall back to the shared handler."""
        if reaction.emoji == "🗣️":
            quiz = self.quizzes.get(reaction.message.channel.id)
            if quiz and quiz.in_progress:
                await self.handle_tts(reaction.message, user)
            try:
                await reaction.remove(user)
            except discord.errors.NotFound:
                pass
            return

        await super().handle_reaction_add(reaction, user)

    def load_words(self):
        self.questions = []

        # Add the heroes and abilities.
        heroes = utils.get_heroes()
        hero_words = []
        abilities = []
        for hero in heroes:
            # Heroes do not have a hint.
            hero_words.append(
                Word(
                    text=hero.localized_name,
                    category="Heroes",
                    image=utils.dotabase_url(hero.portrait),
                    url=utils.dota_wiki_url(hero.localized_name),
                    emoji=self.bot.icons.get(hero.localized_name),
                )
            )
            abilities.extend(hero.abilities)
        self.log(f"Loaded {len(hero_words)} words from {len(heroes)} heroes.")

        # Add the abilities.
        ability_words = []
        for ability in abilities:
            category = "Abilities"
            if ability.innate:
                category = "Innate Abilities"

            # Skip abilities with underscores like silencer_irrepressible.
            if "_" in ability.localized_name:
                continue

            # Use the lore as the hint if it exists, otherwise use the hero name.
            hint = ability.lore or ability.hero.localized_name

            ability_words.append(
                Word(
                    text=ability.localized_name,
                    category=category,
                    hint=hint,
                    image=utils.dotabase_url(ability.icon),
                    url=utils.dota_wiki_url(ability.localized_name),
                    emoji=self.bot.icons.get(ability.hero.localized_name),
                )
            )
        self.log(f"Loaded {len(ability_words)} words from {len(abilities)} abilities.")

        # Add the items.
        item_words = []
        items = utils.get_items()
        for item in items:
            # Use the lore as the hint.
            item_words.append(
                Word(
                    text=item.localized_name,
                    category="Items",
                    hint=item.lore,
                    image=utils.dotabase_url(item.icon),
                    url=utils.dota_wiki_url(item.localized_name),
                )
            )
        self.log(f"Loaded {len(item_words)} words from {len(items)} items.")

        # Add the words to the list.
        self.questions.extend(hero_words)
        self.questions.extend(ability_words)
        self.questions.extend(item_words)

        print(f"Loaded {len(self.questions)} quiz words.")

    @app_commands.command(name="quiz", description="Play the Shopkeeper's quiz")
    async def quiz(self, interaction: discord.Interaction):
        await self.bot.messaging.send_embed(interaction, text="Starting the quiz!")
        await self.start_quiz(interaction.channel)

    @app_commands.command(name="top", description="List users with the most gold.")
    async def top(self, interaction: discord.Interaction):
        """Sends a list of the users with the most gold"""
        # Get all users and their gold amounts
        users = []
        for user_id in self.bot.database.get_all_users():
            gold = self.bot.database.get_user_setting(user_id, "gold", 0)
            # if gold > 0:  # Only include users with gold
            user = await self.bot.fetch_user(int(user_id))
            users.append((user, gold))

        # Sort by gold amount
        users.sort(key=lambda x: x[1], reverse=True)

        # Take top 10
        users = users[:10]

        gold_emoji = self.bot.icons.emojis.get("Gold", "*gold*")
        text = ""
        for i, (user, gold) in enumerate(users):
            if i == 0:
                emoji = ":crown:"
            elif i == 1:
                emoji = ":second_place:"
            elif i == 2:
                emoji = ":third_place:"
            else:
                emoji = ""
            text += (
                f"{i+1}. **{user.display_name}**: {gold} {gold_emoji} {emoji}" + "\n"
            )

        await self.bot.messaging.send_embed(
            interaction,
            title="Top Users",
            text=text,
            thumbnail="https://api.opendota.com/apps/dota2/images/abilities/alchemist_goblins_greed_md.png",
        )

    @app_commands.command(name="gold", description="Check your current gold balance.")
    async def gold(self, interaction: discord.Interaction):
        """Sends the user's current gold balance"""
        gold = self.bot.database.get_user_setting(interaction.user.id, "gold", 0)
        gold_emoji = self.bot.icons.emojis.get("Gold", "*gold*")
        await self.bot.messaging.send_embed(
            interaction,
            text=f"{interaction.user.mention}, you have **{gold}** {gold_emoji}",
        )


async def setup(bot: "DotaBot"):
    await bot.add_cog(ShopkeeperQuiz(bot))
