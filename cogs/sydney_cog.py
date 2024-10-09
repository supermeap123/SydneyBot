# cogs/sydney_cog.py
import discord
from discord.ext import commands, tasks
import time
import asyncio
import random
import re
import datetime
from config import logger
from helpers import (
    contains_trigger_word,
    is_bot_mentioned,
    random_chance,
    replace_usernames_with_mentions,
    replace_ping_with_mention,
    replace_name_exclamation_with_mention,
    is_valid_prefix,
    get_system_prompt,
    get_reaction_system_prompt,
    is_refusal
)
from database import (
    load_user_preference,
    save_user_preference,
    backup_database,
    load_probabilities,
    save_probabilities
)
from openpipe_api import get_valid_response, get_reaction_response

class SydneyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conversation_histories = {}
        self.MAX_HISTORY_LENGTH = 50
        self.start_time = time.time()
        self.recent_messages = {}  # To track recent messages and their authors
        self.temperature = 0.1777  # Default temperature
        self.trigger_words = [
            "sydney", "syd", "s!talk", "sydneybot#3817"
        ]
        self.expensive_trigger_words = ["xxx"]
        self.probabilities = {}  # Store reply and reaction probabilities per guild/channel
        self.update_presence.start()

    def cog_unload(self):
        self.update_presence.cancel()

    @tasks.loop(minutes=5)
    async def update_presence(self):
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name=f"{len(self.bot.guilds)} servers"),
            discord.Activity(type=discord.ActivityType.listening, name=f"{len(set(self.bot.get_all_members()))} users"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{sum(len(channels) for channels in self.conversation_histories.values())} active chats"),
            discord.Activity(type=discord.ActivityType.playing, name="with AI conversations"),
            discord.Activity(type=discord.ActivityType.watching, name=f"Uptime: {str(datetime.timedelta(seconds=int(time.time() - self.start_time)))}"),
            discord.Activity(type=discord.ActivityType.listening, name="s!sydney_help"),
        ]
        status = random.choice(statuses)
        try:
            await self.bot.change_presence(activity=status)
        except Exception as e:
            logger.error(f"Error updating presence: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        # Process commands first
        await self.bot.process_commands(message)

        # Check if the message is a command and return if it is
        if message.content.startswith(self.bot.command_prefix):
            return

        logger.debug(f"Received message: {message.content}")

        is_dm = isinstance(message.channel, discord.DMChannel)
        guild_id = "DM" if is_dm else str(message.guild.id)
        channel_id = message.channel.id

        # Load probabilities for the guild and channel
        reply_probability, reaction_probability = load_probabilities(guild_id, channel_id)

        # Initialize conversation history for guild and channel if not present
        if guild_id not in self.conversation_histories:
            self.conversation_histories[guild_id] = {}

        if channel_id not in self.conversation_histories[guild_id]:
            self.conversation_histories[guild_id][channel_id] = []

        role = "assistant" if message.author == self.bot.user else "user"
        content = message.clean_content

        if role == "user":
            content = f"{message.author.display_name}: {content}"

        # Update user preferences based on instructions
        if role == "user":
            # Check for instruction to start messages with a prefix
            match = re.search(r'start your messages with(?: that)? by saying (.+?) before everything', content, re.IGNORECASE)
            if match:
                prefix = match.group(1).strip()
                if is_valid_prefix(prefix):
                    save_user_preference(message.author.id, prefix)
                    await message.channel.send(f"Okay, I'll start my messages with '{prefix}' from now on.")
                else:
                    await message.channel.send("Sorry, that prefix is invalid or too long.")

        self.conversation_histories[guild_id][channel_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

        if len(self.conversation_histories[guild_id][channel_id]) > self.MAX_HISTORY_LENGTH:
            self.conversation_histories[guild_id][channel_id] = self.conversation_histories[guild_id][channel_id][-self.MAX_HISTORY_LENGTH:]

        # Track recent messages asynchronously
        if channel_id not in self.recent_messages:
            self.recent_messages[channel_id] = []
        self.recent_messages[channel_id].append((message.author.id, time.time()))

        # Clean up old messages
        self.recent_messages[channel_id] = [
            (author_id, timestamp) for author_id, timestamp in self.recent_messages[channel_id]
            if time.time() - timestamp < 5
        ]

        # Check if another bot has replied recently
        if any(author_id != message.author.id and author_id != self.bot.user.id for author_id, _ in self.recent_messages[channel_id]):
            return

        should_respond = False
        use_expensive_model = False

        if is_bot_mentioned(message, self.bot.user):
            should_respond = True
        elif contains_trigger_word(message.content, self.trigger_words):
            should_respond = True
        elif contains_trigger_word(message.content, self.expensive_trigger_words):
            should_respond = True
            use_expensive_model = True
        elif is_dm:
            should_respond = True
        elif random_chance(reply_probability):
            should_respond = True

        if should_respond:
            # Build the system prompt without summary
            system_prompt = get_system_prompt(message.author.display_name, guild_id, channel_id)
            messages = [{"role": "system", "content": system_prompt}]
            # Include the last 50 messages as context
            messages.extend(self.conversation_histories[guild_id][channel_id])

            tags = {
                "user_id": str(message.author.id),
                "channel_id": str(channel_id),
                "server_id": str(guild_id) if guild_id != "DM" else "DM",
                "interaction_type": "trigger_chat",
                "prompt_id": "sydney_v1.0"
            }

            try:
                async with message.channel.typing():
                    response = await get_valid_response(messages, tags, initial_temperature=self.temperature, use_expensive_model=use_expensive_model)

                    # Extract custom name if present
                    custom_name_match = re.match(r"^(.+?):\s*(.*)$", response)
                    custom_name = custom_name_match.group(1) if custom_name_match else None
                    response_content = custom_name_match.group(2) if custom_name_match else response

                    # Get user preferences
                    message_prefix = load_user_preference(message.author.id)

                    # Prepend message prefix if any
                    if message_prefix:
                        response_content = f"{message_prefix} {response_content}"

                    # Replace placeholders and usernames with mentions
                    if not is_dm:
                        response_content = replace_usernames_with_mentions(response_content, message.guild)
                        response_content = replace_ping_with_mention(response_content, message.author)
                        response_content = replace_name_exclamation_with_mention(response_content, message.author)

                    # Truncate response if it exceeds Discord's limit
                    if len(response_content) > 2000:
                        response_content = response_content[:1997] + '...'

                    # Use Discord's reply feature
                    await message.reply(response_content, mention_author=False)

                    # Update conversation history with assistant's response
                    self.conversation_histories[guild_id][channel_id].append({
                        "role": "assistant",
                        "content": response_content,
                        "timestamp": time.time()
                    })

                    if len(self.conversation_histories[guild_id][channel_id]) > self.MAX_HISTORY_LENGTH:
                        self.conversation_histories[guild_id][channel_id] = self.conversation_histories[guild_id][channel_id][-self.MAX_HISTORY_LENGTH:]

                    # Backup the database after changes
                    backup_database()

            except Exception as e:
                await message.reply("Sorry, I encountered an error while processing your request.")
                logger.error(f"Error processing message from {message.author}: {e}")

        # Reaction handling
        if role == "user":
            if random_chance(reaction_probability):
                try:
                    # Show typing indicator
                    async with message.channel.typing():
                        # Prepare the system prompt and user message
                        system_prompt = get_reaction_system_prompt()
                        user_message = message.clean_content

                        # Build the messages for the API call
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ]

                        # Make the API call to get the reaction
                        reaction = await get_reaction_response(messages)

                    # Add the reaction to the message
                    if reaction:
                        await message.add_reaction(reaction.strip())
                    else:
                        logger.debug("No suitable reaction found.")
                except discord.HTTPException as e:
                    logger.error(f"Failed to add reaction: {e}")
                except Exception as e:
                    logger.error(f"Error adding reaction to message from {message.author}: {e}")

    # Commands and other event listeners go here
    # For brevity, I've only included the on_message event

    @commands.command(name='sydney_help', aliases=['sydney_commands', 'sydneyhelp'])
    async def sydney_help(self, ctx):
        """Displays the help message with a list of available commands."""
        embed = discord.Embed(
            title="SydneyBot Help",
            description="Here are the commands you can use with SydneyBot:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="General Commands",
            value=(
                "**s!sydney_help**\n"
                "Displays this help message.\n\n"
                "**s!set_reaction_probability <value>**\n"
                "Sets the reaction probability (0-1). Determines how often Sydney reacts to messages with emojis.\n\n"
                "**s!set_reply_probability <value>**\n"
                "Sets the reply probability (0-1). Determines how often Sydney randomly replies to messages.\n"
            ),
            inline=False
        )
        embed.add_field(
            name="Interaction with Sydney",
            value=(
                "Sydney will respond to messages that mention her or contain trigger words.\n"
                "She may also randomly reply or react to messages based on the set probabilities.\n"
                "To get Sydney's attention, you can mention her, use one of her trigger words, **or reply to one of her messages**.\n"
            ),
            inline=False
        )
        embed.add_field(
            name="Examples",
            value=(
                "- **Mentioning Sydney:** `@SydneyBot How are you today?`\n"
                "- **Using a trigger word:** `Sydney, tell me a joke!`\n"
                "- **Replying to Sydney:** *(reply to one of her messages)* `That's interesting! Tell me more.`\n"
                "- **Setting reaction probability:** `s!set_reaction_probability 0.5`\n"
                "- **Setting reply probability:** `s!set_reply_probability 0.2`\n"
            ),
            inline=False
        )
        embed.set_footer(text="Feel free to reach out if you have any questions!")
        await ctx.send(embed=embed)

    @sydney_help.error
    async def sydney_help_error(self, ctx, error):
        logger.exception(f"Error in sydney_help command: {error}")
        await ctx.send("An error occurred while displaying the help message.")

    # Add other commands like set_temperature, set_reply_probability, set_reaction_probability, etc.

    # Error handlers
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Sorry, I didn't recognize that command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing required argument. Please check the command usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument type. Please check the command usage.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Command is on cooldown. Try again after {round(error.retry_after, 2)} seconds.")
        else:
            await ctx.send("An error occurred while processing the command.")
            logger.error(f"Error processing command from {ctx.author}: {error}", exc_info=True)