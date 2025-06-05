import discord
from discord import Embed
from discord.ext import commands

command_list = """
`/quiz` - *Play the Shopkeeper's quiz*
`/gold` - *Check your gold balance*
`/top` - *List the top gold balances*
`[exact quote]` - *Play a voiceline*
`dota [partial quote]` - *Play a voiceline*
`dota [partial quote] [n]` - *Play voiceline n out of many*
`hero [hero]` - *Play a hero's voiceline*
`list [command]` - *List results for a command*
`list [n] [command]` - *List starting at an index*
"""


example_list = """
`Ho ho.` - *Plays "Ho ho. (Lifestealer)"*
`Ha ha. 10` - *Plays "Ha ha. (Invoker) (10 out of 17)"*
`dota banana` - *Plays "That's the biggest banana slug I've ever seen."*
`random Techies` - *Play a random Techies voice line*
`list hero Techies` - *List all Techies voice lines*
`list dota haha` - *List all voicelines containing "haha"*
"""


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Learn how to use this bot")
    async def _help(self, interaction: discord.Interaction):
        """Sends help message"""
        embed = Embed()
        embed.add_field(name="Commands", value=command_list, inline=False)
        embed.add_field(name="Examples", value=example_list, inline=False)
        embed.color = 0xFF0000
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
