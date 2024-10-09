# bot.py
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, logger
from database import init_database
from cogs.sydney_cog import SydneyCog

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True  # Required to read message content
intents.dm_messages = True

bot = commands.Bot(command_prefix='s!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    init_database()
    await bot.add_cog(SydneyCog(bot))

if __name__ == '__main__':
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}")