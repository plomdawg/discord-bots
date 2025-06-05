"""Shopkeeper Quiz"""

import asyncio
import random
import time
from typing import TYPE_CHECKING, List

import discord
from discord.ext import commands

from cogs.dota import utils

if TYPE_CHECKING:
    from bots.dotabot import DotaBot

# Pictures used for the embedded messages.
SHOPKEEPER_IMAGE = "https://i.imgur.com/Xyf1VjQ.png"
UNKNOWN_IMAGE = "https://static.wikia.nocookie.net/dota2_gamepedia/images/5/5d/Unknown_Unit_icon.png/revision/latest/scale-to-width-down/128?cb=20170416184928"


def prepare(text):
    """Remove quotes and dashes from the text."""
    return text.replace("'", "").replace("-", " ").upper()


def scramble(word) -> str:
    """Randomly scrambles a word"""
    char_list = list(prepare(word))
    random.shuffle(char_list)
    scrambled = "".join(char_list)
    # Try again if the word isn't scrambled.
    if word in scrambled and len(word) > 1:
        return scramble(word)
    return scrambled.upper()


def easy_scramble(word) -> str:
    """Scrambles a word, with spaces in place"""
    words = prepare(word).split(" ")
    return " ".join(scramble(word) for word in words)


class Word:
    def __init__(self, text, category, image, url, emoji=None, hint=None) -> None:
        self.text = text
        self.category = category
        self.image = image
        self.url = url
        self.emoji = emoji
        self.hint = hint

    def check(self, word) -> bool:
        """Returns True if text matches the word, ignoring case and punctuation."""
        return prepare(word) == prepare(self.text)

    def get_hint(self):
        """Returns the hint for the word with the word censored."""
        if self.hint:
            return self.hint.replace(self.text, "*" * len(self.text))
        return None


class Quiz:
    def __init__(
        self, bot: "DotaBot", words: List[Word], channel: discord.TextChannel
    ) -> None:
        self.bot = bot
        self.in_progress = False
        self.round_time = 23  # seconds
        self.max_gold = 3  # total possible gold for an answer.
        self.current_word = None
        self.channel = channel  # discord text channel.
        self.guesses = {}  # current guesses for a round.

        # Create a copy of the word list so we can pop() from it.
        self.words = words.copy()

    def next_word(self):
        """Gets the next word from the word list."""
        index = random.randrange(len(self.words))
        word = self.words.pop(index)
        self.current_word = word
        return word

    def add_score(self, user):
        """Calculates and adds to a user's score."""
        # 1 gold per number of guessers.
        score = len(self.guesses.keys())
        # 1 gold per answer.
        score = 1
        try:
            self.scores[user] += score
            self.correct_answers[user] += 1
        except KeyError:
            self.scores[user] = score
            self.correct_answers[user] = 1

        # Update the user's gold in the database.
        gold = self.bot.database.get_user_setting(user.id, "gold", 0)
        self.bot.database.set_user_setting(user.id, "gold", gold + score)
        return score

    async def start_phase(self, message, check, category=False, easy=False, hint=False):
        """Start a phase by editing the message given. Returns the answer if solved."""
        # Manually create an embedded message.
        embed = discord.Embed()
        embed.set_thumbnail(url=UNKNOWN_IMAGE)
        embed.title = f"Shopkeeper's Quiz (round {self.round_number})"

        # Add the scrambled word.
        if easy:
            scrambled = easy_scramble(self.current_word.text)
        else:
            scrambled = scramble(self.current_word.text)
        description = f"**Unscramble:** {scrambled}"

        # Add the category.
        if category:
            description += f"\n**Category:** {self.current_word.category} "
            embed.set_footer(text="*Here's a hint!*")
            # Show an image of the category type.
            if self.current_word.category == "Innate Abilities":
                embed.set_thumbnail(
                    url=utils.dotabase_url(
                        "panorama/images/hud/facets/innate_icon_large_png.png"
                    )
                )
            elif self.current_word.category == "Facet Abilities":
                embed.set_thumbnail(
                    url=utils.dotabase_url(
                        "/panorama/images/spellicons/attribute_bonus_png.png"
                    )
                )
            elif self.current_word.category == "Items":
                embed.set_thumbnail(url=SHOPKEEPER_IMAGE)

        # Add the hint.
        if hint:
            description += f"\n**Hint:** {self.current_word.get_hint()} "
            embed.set_footer(text="*Here's another hint!*")

        # Change the footer if it's easy scrambled.
        if easy:
            embed.set_footer(text="*Spaces are in their places!*")

        # Edit the message for this round.
        embed.description = description
        await message.edit(embed=embed)

        # Wait for the answer.
        try:
            answer = await self.bot.wait_for(
                "message", check=check, timeout=self.round_time
            )
        except asyncio.TimeoutError:
            answer = None

        # Return the answer, or None.
        return answer, embed

    async def start_round(self):
        """Start a round."""
        # Start the round timer (used to calculate score).
        start_time = time.perf_counter()

        # Send a message.
        text = f"Starting round **{self.round_number}**, sit tight!"
        message = await self.bot.messaging.send_embed(self.channel, text=text)

        # Grab the next word.
        self.next_word()

        # Keep track of guesses.
        self.guesses = {}

        # This is called for each response, returns True if the guess is correct
        def check(msg):
            # Make sure the message is from this server.
            if msg.channel.guild != self.channel.guild:
                return False

            # Keep track of guesses per user.
            try:
                self.guesses[msg.author].append(msg.content)
            except KeyError:
                self.guesses[msg.author] = [msg.content]

            return self.current_word.check(msg.content)

        # Begin phase 1: hard scramble.
        answer, embed = await self.start_phase(message, check)

        # Begin phase 2: hard scramble with a category.
        if answer is None:
            answer, embed = await self.start_phase(message, check, category=True)

        # Begin phase 3: easy scramble with the category.
        if answer is None:
            answer, embed = await self.start_phase(
                message, check, category=True, easy=True
            )

        # Begin phase 4 if we have a hint: easy scramble with a hint.
        if answer is None and self.current_word.get_hint() is not None:
            answer, embed = await self.start_phase(
                message, check, category=True, easy=True, hint=True
            )

        #
        # Round is now over.
        #

        # Add the answer to the quiz message.
        embed.description += f"\n**Answer**: {self.current_word.emoji or ''} [{self.current_word.text}]({self.current_word.url})"

        # Add the image to the quiz message.
        if self.current_word.image is not None:
            embed.set_thumbnail(url=self.current_word.image)

        # Somebody answered!
        if answer:
            # Add a thumbs up to the correct answer.
            await answer.add_reaction("👍")

            # Increment user's score.
            elapsed_time = time.perf_counter() - start_time
            score = self.add_score(user=answer.author)

            # Add the user who guessed right to the footer of the quiz message.
            embed.set_footer(
                text=f"✅ {answer.author.display_name} 🪙 {score} gold ⌚ {elapsed_time:.2f} seconds"
            )

        # Game over if nobody answered.
        if answer is None:
            # Send a thumbs down on the quiz message.
            await message.add_reaction("👎")

            # Set the footer.
            embed.set_footer(text="Nobody answered in time! Game over.")

            # End the quiz.
            self.in_progress = False

        # Edit the message.
        await message.edit(embed=embed)

    async def start(self):
        """Start the quiz."""
        # Quiz is now in progress.
        self.in_progress = True

        # Reset scores and correct answers for this quiz.
        self.scores = {}
        self.correct_answers = {}

        # Keep starting rounds until the quiz is over.
        self.round_number = 1
        while self.in_progress:
            await self.start_round()
            self.round_number += 1

        # End the quiz.
        await self.end()

    async def end(self):
        """Handles a game over."""
        # Find the top score.
        try:
            top_score = max(self.scores.values())
        except ValueError:
            top_score = 0
            return

        # Find the winners and losers. There may be more than one winner if tied.
        winners = []
        losers = []
        for user, score in self.scores.items():
            if score == top_score:
                winners.append(user)
            else:
                losers.append(user)

        # If there are no winners, everybody lost!
        if len(winners) == 0:
            text = "Everybody lost!"

        # Single winner.
        elif len(winners) == 1:
            text = "Winner: **{}** earned **{}** gold with {} answers!\n".format(
                winners[0].display_name, top_score, self.correct_answers[winners[0]]
            )

        # Multiple winners!
        else:
            text = f"It's a tie! The following players earned **{top_score}** gold:\n"
            for winner in winners:
                text += " -- {}\n".format(winner)

        # Add the scores for everyone else.
        if len(losers) > 0:
            text += "Losers:\n"
            for user in losers:
                text += " -- {} got {} correct (**{}** gold)\n".format(
                    user.display_name, self.correct_answers[user], self.scores[user]
                )

        # Send the game over message.
        message = await self.bot.messaging.send_embed(
            channel=self.channel,
            title="Shopkeeper's Quiz Results",
            text=text,
            thumbnail=SHOPKEEPER_IMAGE,
            footer=f"To play again, press NEW or type /quiz",
        )
        await message.add_reaction("🆕")


class ShopkeeperQuiz(commands.Cog):
    def __init__(self, bot: "DotaBot"):
        self.bot = bot
        self.quizzes = {}  # key = guild, value = quiz

    def log(self, message: str):
        """Log a message to the bot."""
        self.bot.log(f"[ShopkeeperQuiz] {message}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Load the words when the bot is ready."""
        self.load_words()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignore own reactions
        if user == self.bot.user:
            return

        # Ignore messages not sent by the bot
        if reaction.message.author != self.bot.user:
            return

        # NEW quiz
        if reaction.emoji in "🆕":
            """Remove own reaction and start quiz"""
            try:
                await reaction.remove(self.bot.user)
            except discord.errors.NotFound:
                pass
            asyncio.ensure_future(
                self.shopkeeper_quiz(bot=self.bot, channel=reaction.message.channel)
            )
        else:
            # Unknown emoji, do nothing
            return

        # Remove the reaction once the job is done
        try:
            await reaction.remove(user)
        except discord.errors.NotFound:
            pass

    def load_words(self):
        self.words = []

        # Add the heroes and abilities.
        heroes = utils.get_heroes()
        hero_words = []
        abilities = []
        for hero in heroes:
            emoji = self.bot.icons.get(hero.localized_name)

            # Heroes do not have a hint.
            hero_words.append(
                Word(
                    text=hero.localized_name,
                    category="Heroes",
                    image=utils.dotabase_url(hero.portrait),
                    url=utils.dota_wiki_url(hero.localized_name),
                    emoji=emoji,
                )
            )
            abilities.extend(hero.abilities)
        self.log(f"Loaded {len(hero_words)} words from {len(heroes)} heroes.")

        # Add the abilities.
        ability_words = []
        for ability in abilities:
            category = "Abilities"
            if ability.facet_id:
                category = "Facet Abilities"
            if ability.innate:
                category = "Innate Abilities"

            # Skip abilities with underscores like silencer_irrepressible.
            if "_" in ability.localized_name:
                continue

            # Skip abilities with no text in their name.
            if ability.localized_name.strip() == "":
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
                    emoji=emoji,
                )
            )
        self.log(f"Loaded {len(ability_words)} words from {len(abilities)} abilities.")

        # Add the facets.
        facet_words = []
        facets = utils.get_facets()
        for facet in facets:
            emoji = self.bot.icons.get(facet.hero.localized_name)

            # Skip facets with no text in their name.
            if facet.localized_name.strip() == "":
                continue

            facet_words.append(
                Word(
                    text=facet.localized_name,
                    category="Facets",
                    hint=f"Hero: {facet.hero.localized_name}",
                    image=utils.dotabase_url(facet.icon),
                    url=utils.dota_wiki_url(facet.localized_name),
                    emoji=emoji,
                )
            )
        self.log(f"Loaded {len(facet_words)} words from {len(facets)} facets.")

        # Add the items.
        item_words = []
        items = utils.get_items()
        for item in items:
            # Skip items with no text in their name.
            if item.localized_name.strip() == "":
                continue

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
        self.words.extend(facet_words)
        self.words.extend(hero_words)
        self.words.extend(ability_words)
        self.words.extend(item_words)

        print(f"Loaded {len(self.words)} quiz words.")

    async def shopkeeper_quiz(self, bot, channel):
        # Try to find existing quiz.
        quiz = self.quizzes.get(channel.guild)

        # Don't start a new quiz if there's already a quiz happening.
        if quiz is not None and quiz.in_progress:
            await bot.messaging.send_embed(
                channel, text="A quiz is in progress!", color=0xFF0000
            )
            return

        # Initialize Quiz.
        self.quizzes[channel.guild] = Quiz(bot=bot, words=self.words, channel=channel)

        # Begin the quiz.
        asyncio.ensure_future(self.quizzes[channel.guild].start())

    @discord.app_commands.command(name="quiz", description="Play the Shopkeeper's quiz")
    async def quiz(self, interaction: discord.Interaction):
        await self.bot.messaging.send_embed(interaction, text="Starting the quiz!")
        await self.shopkeeper_quiz(channel=interaction.channel, bot=self.bot)

    @discord.app_commands.command(
        name="top", description="List users with the most gold."
    )
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

    @discord.app_commands.command(
        name="gold", description="Check your current gold balance."
    )
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
