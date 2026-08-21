"""Generic quiz engine.

This is the game-agnostic half of the quiz: the round loop, the escalating hint
phases, timing, scoring, the answer reveal, and the end-of-game summary. It knows
nothing about Dota or Slay the Spire.

A game plugs in by providing:
  * a :class:`QuizTheme`     - titles, thumbnails, and which currency to pay out
  * a list of :class:`Question` subclass instances - each owns its own hint ladder

See ``cogs/dota/quiz.py`` (unscramble the name) and ``cogs/slay/quiz.py``
(name the card from its description) for the two implementations.
"""

import asyncio
import difflib
import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import discord
from discord.ext import commands

# Answers shorter than this are matched exactly - a single typo in a 4-letter
# name blows past any sane similarity ratio anyway, and loosening it there just
# lets neighbouring answers win.
MIN_FUZZY_LENGTH = 5

# How similar a guess must be to count. 0.85 tolerates a letter or two in a
# medium-length name without accepting a different answer.
FUZZY_THRESHOLD = 0.85


def prepare(text: str) -> str:
    """Normalize text for comparison: drop quotes, dashes to spaces, uppercase."""
    return text.replace("'", "").replace("-", " ").upper()


def scramble(word: str) -> str:
    """Randomly scrambles a word."""
    char_list = list(prepare(word))
    random.shuffle(char_list)
    scrambled = "".join(char_list)
    # Try again if the word isn't scrambled.
    if word in scrambled and len(word) > 1:
        return scramble(word)
    return scrambled.upper()


def easy_scramble(word: str) -> str:
    """Scrambles a word, with spaces in place."""
    words = prepare(word).split(" ")
    return " ".join(scramble(word) for word in words)


def similarity(guess: str, answer: str) -> float:
    """Return how similar two strings are, 0.0 to 1.0, after normalization."""
    return difflib.SequenceMatcher(None, prepare(guess), prepare(answer)).ratio()


def fuzzy_match(guess: str, answer: str, others: Optional[frozenset] = None) -> bool:
    """Return True if the guess is close enough to the answer.

    Short answers must match exactly. Longer ones tolerate a typo, with one
    guard: if the guess looks *more* like some other answer in the pool, it is
    rejected, so a near-miss can't score on the wrong card.
    """
    guess = guess.strip()
    if not guess:
        return False

    if prepare(guess) == prepare(answer):
        return True

    if len(prepare(answer)) < MIN_FUZZY_LENGTH:
        return False

    score = similarity(guess, answer)
    if score < FUZZY_THRESHOLD:
        return False

    # Don't accept a guess that is a better match for something else entirely.
    if others:
        for other in others:
            if prepare(other) == prepare(answer):
                continue
            if similarity(guess, other) > score:
                return False

    return True


def letter_skeleton(answer: str, revealed: int = 0) -> str:
    """Render an answer as blanks, revealing the first `revealed` letters per word.

    Wrapped in a code span by the caller's format string so Discord doesn't try
    to read the underscores as italics.
    """
    words = []
    for word in answer.split():
        letters = []
        for index, character in enumerate(word):
            if not character.isalnum():
                letters.append(character)  # keep punctuation visible
            elif index < revealed:
                letters.append(character.upper())
            else:
                letters.append("_")
        words.append(" ".join(letters))
    return "   ".join(words)


def describe_length(answer: str) -> str:
    """A short '(2 words, 13 letters)' style note to accompany a skeleton."""
    words = answer.split()
    letters = sum(1 for character in answer if character.isalnum())
    if len(words) == 1:
        return f"({letters} letters)"
    return f"({len(words)} words, {letters} letters)"


@dataclass
class QuizTheme:
    """Per-game presentation and payout settings."""

    title: str  # embed title, gets " (round N)" appended
    results_title: str  # embed title for the summary
    currency: str  # human name, e.g. "gold"
    currency_key: str  # database user-setting key, e.g. "gold"
    currency_emoji: str  # shown next to a payout, e.g. "🪙"
    play_again_command: str  # e.g. "/quiz"
    unknown_thumbnail: str  # shown while the round is unsolved
    win_thumbnail: str  # summary, somebody scored
    lose_thumbnail: str  # summary, nobody scored
    round_time: int = 23  # seconds per phase


class Question:
    """One question. Subclasses own the prompt and the hint ladder.

    ``answer`` is what a player types. It is deliberately separate from the
    prompt: the Dota quiz scrambles the answer to build its prompt, while the
    Slay quiz shows a description and keeps the answer hidden.
    """

    def __init__(
        self,
        answer: str,
        category: str,
        image: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[str] = None,
    ) -> None:
        self.answer = answer
        self.category = category
        self.image = image
        self.url = url
        self.emoji = emoji

    @property
    def phase_count(self) -> int:
        """How many hint phases this question has."""
        raise NotImplementedError

    def phase_body(self, phase: int) -> str:
        """The embed description for a 1-indexed phase."""
        raise NotImplementedError

    def phase_footer(self, phase: int) -> Optional[str]:
        """Optional footer nudge for a 1-indexed phase."""
        return None

    def phase_thumbnail(self, phase: int) -> Optional[str]:
        """Optional thumbnail override for a 1-indexed phase."""
        return None

    def check(self, guess: str) -> bool:
        """Return True if the guess is correct. Exact by default."""
        return prepare(guess) == prepare(self.answer)


class Quiz:
    """A running game in one channel."""

    def __init__(
        self,
        bot: commands.Bot,
        questions: List[Question],
        channel: discord.TextChannel,
        theme: QuizTheme,
        on_phase_message: Optional[Callable] = None,
    ) -> None:
        self.bot = bot
        self.theme = theme
        self.in_progress = False
        self.channel = channel
        self.current_question: Optional[Question] = None
        self.guesses: Dict = {}
        self.scores: Dict = {}
        self.correct_answers: Dict = {}
        self.round_number = 1

        # Called after each phase edit, for per-game extras (e.g. a TTS reaction).
        self.on_phase_message = on_phase_message

        # Create a copy of the question list so we can pop() from it.
        self.questions = questions.copy()

    def next_question(self) -> Question:
        """Gets the next question, without repeating within this game."""
        index = random.randrange(len(self.questions))
        question = self.questions.pop(index)
        self.current_question = question
        return question

    def add_score(self, user) -> int:
        """Adds to a user's score and persists their balance."""
        # One point per correct answer.
        score = 1
        try:
            self.scores[user] += score
            self.correct_answers[user] += 1
        except KeyError:
            self.scores[user] = score
            self.correct_answers[user] = 1

        balance = self.bot.database.get_user_setting(
            user.id, self.theme.currency_key, 0
        )
        self.bot.database.set_user_setting(
            user.id, self.theme.currency_key, balance + score
        )
        return score

    async def start_phase(self, message, check, phase: int):
        """Run one hint phase by editing the message. Returns (answer, embed)."""
        question = self.current_question
        embed = discord.Embed()
        embed.title = f"{self.theme.title} (round {self.round_number})"

        if question is None:
            return None, embed

        embed.set_thumbnail(
            url=question.phase_thumbnail(phase) or self.theme.unknown_thumbnail
        )
        embed.description = question.phase_body(phase)
        footer = question.phase_footer(phase)
        if footer:
            embed.set_footer(text=footer)

        await message.edit(embed=embed)

        if self.on_phase_message is not None:
            await self.on_phase_message(self, message)

        # Wait for the answer.
        try:
            answer = await self.bot.wait_for(
                "message", check=check, timeout=self.theme.round_time
            )
        except asyncio.TimeoutError:
            answer = None

        return answer, embed

    async def start_round(self):
        """Start a round."""
        start_time = time.perf_counter()

        text = f"Starting round **{self.round_number}**, sit tight!"
        message = await self.bot.messaging.send_embed(self.channel, text=text)

        self.next_question()
        self.guesses = {}

        # This is called for each message, returns True if the guess is correct.
        def check(msg):
            # Only accept guesses from the channel this game is running in, so two
            # quizzes on the same bot can run side by side without cross-scoring.
            if msg.channel.id != self.channel.id:
                return False

            # Ignore the bot's own messages.
            if msg.author == self.bot.user:
                return False

            # Keep track of guesses per user.
            try:
                self.guesses[msg.author].append(msg.content)
            except KeyError:
                self.guesses[msg.author] = [msg.content]

            if self.current_question is None:
                return False
            return self.current_question.check(msg.content)

        # Escalate through the hint phases until somebody answers.
        answer = None
        embed = None
        question = self.current_question
        phase_count = question.phase_count if question is not None else 0
        for phase in range(1, phase_count + 1):
            answer, embed = await self.start_phase(message, check, phase)
            if answer is not None:
                break

        #
        # Round is now over.
        #
        if embed is None:
            return

        # Add the answer to the quiz message.
        if question is not None:
            if embed.description is None:
                embed.description = ""
            link = question.answer
            if question.url:
                link = f"[{question.answer}]({question.url})"
            embed.description += f"\n\n**Answer**: {question.emoji or ''} {link}"

            if question.image is not None:
                embed.set_thumbnail(url=question.image)

        # Somebody answered!
        if answer:
            await answer.add_reaction("👍")

            elapsed_time = time.perf_counter() - start_time
            score = self.add_score(user=answer.author)

            embed.set_footer(
                text=f"✅ {answer.author.display_name} "
                f"{self.theme.currency_emoji} {score} {self.theme.currency} "
                f"⌚ {elapsed_time:.2f} seconds"
            )

        # Game over if nobody answered.
        else:
            if message is not None:
                await message.add_reaction("👎")
            embed.set_footer(text="Nobody answered in time! Game over.")
            self.in_progress = False

        if message is not None:
            await message.edit(embed=embed)

    async def start(self):
        """Start the quiz."""
        self.in_progress = True
        self.scores = {}
        self.correct_answers = {}

        self.round_number = 1
        while self.in_progress and self.questions:
            await self.start_round()
            self.round_number += 1

        await self.end()

    async def end(self):
        """Handles a game over."""
        thumbnail = self.theme.win_thumbnail

        top_score = max(self.scores.values(), default=0)

        # There may be more than one winner if tied.
        winners = []
        losers = []
        for user, score in self.scores.items():
            if score == top_score:
                winners.append(user)
            else:
                losers.append(user)

        if len(winners) == 0:
            text = "Everybody lost!"
            thumbnail = self.theme.lose_thumbnail

        elif len(winners) == 1:
            text = "Winner: **{}** earned **{}** {} with {} answers!\n".format(
                winners[0].display_name,
                top_score,
                self.theme.currency,
                self.correct_answers[winners[0]],
            )

        else:
            text = (
                f"It's a tie! The following players earned "
                f"**{top_score}** {self.theme.currency}:\n"
            )
            for winner in winners:
                text += " -- {}\n".format(winner.display_name)

        if len(losers) > 0:
            text += "Losers:\n"
            for user in losers:
                text += " -- {} got {} correct (**{}** {})\n".format(
                    user.display_name,
                    self.correct_answers[user],
                    self.scores[user],
                    self.theme.currency,
                )

        message = await self.bot.messaging.send_embed(
            channel=self.channel,
            title=self.theme.results_title,
            text=text,
            thumbnail=thumbnail,
            footer=f"To play again, press NEW or type {self.theme.play_again_command}",
        )
        if message is not None:
            await message.add_reaction("🆕")


class BaseQuizCog(commands.Cog):
    """Shared cog plumbing: one game per channel, and the NEW reaction."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self.questions: List[Question] = []
        self.quizzes: Dict[int, Quiz] = {}  # key = channel id

    @property
    def theme(self) -> QuizTheme:
        raise NotImplementedError

    def build_quiz(self, channel) -> Quiz:
        """Override to pass per-game hooks into the Quiz."""
        return Quiz(
            bot=self.bot,
            questions=self.questions,
            channel=channel,
            theme=self.theme,
        )

    async def start_quiz(self, channel) -> None:
        """Start a quiz in a channel, unless one is already running there."""
        quiz = self.quizzes.get(channel.id)
        if quiz is not None and quiz.in_progress:
            await self.bot.messaging.send_embed(
                channel, text="A quiz is in progress!", color=0xFF0000
            )
            return

        if not self.questions:
            await self.bot.messaging.send_embed(
                channel, text="No questions are loaded!", color=0xFF0000
            )
            return

        self.quizzes[channel.id] = self.build_quiz(channel)
        asyncio.ensure_future(self.quizzes[channel.id].start())

    def owns_message(self, message) -> bool:
        """True if the given bot message belongs to this cog's quiz.

        Two quiz cogs can live on one bot, so each must only answer for its own
        messages - otherwise pressing NEW on a Dota summary would also start a
        Slay game.
        """
        for embed in message.embeds:
            if embed.title and (
                embed.title.startswith(self.theme.title)
                or embed.title.startswith(self.theme.results_title)
            ):
                return True
        return False

    async def handle_reaction_add(self, reaction, user):
        """Handle a reaction add event."""
        if reaction.emoji == "🆕":
            try:
                await reaction.remove(self.bot.user)
            except discord.errors.NotFound:
                pass
            asyncio.ensure_future(self.start_quiz(reaction.message.channel))
        else:
            return

        try:
            await reaction.remove(user)
        except discord.errors.NotFound:
            pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignore own reactions.
        if user == self.bot.user:
            return

        # Ignore messages not sent by the bot.
        if reaction.message.author != self.bot.user:
            return

        # Ignore other quizzes' messages.
        if not self.owns_message(reaction.message):
            return

        asyncio.ensure_future(self.handle_reaction_add(reaction, user))
