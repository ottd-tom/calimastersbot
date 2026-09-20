"""
Standalone bot for the !sentiment command.

This is the ONE bot that still needs the Message Content intent (it reads
channel history). Register it as a separate Discord application, install it
only in the sentiment server (SENTIMENT_GUILD_ID in aos_sentiment.py), and
as long as that app stays under Discord's 10,000-user review threshold you can
simply toggle Message Content on in the Developer Portal.

    DISCORD_TOKEN_SENTIMENT=... AOS_EVENTS_DB_URL=... python sentiment_bot.py
"""

from __future__ import annotations

import asyncio
import logging

import discord
import openai
from discord.ext import commands

from aos_sentiment import register as register_sentiment
from aosbot import config
from aosbot.db import get_db_pool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sentiment_bot")

openai.api_key = config.OPENAI_API_KEY

intents = discord.Intents(guilds=True, guild_messages=True, message_content=True)

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None,
                   description="AoS faction sentiment bot")
register_sentiment(bot, get_db_pool, config.ALIAS_MAP, config.EMOJI_MAP)


@bot.event
async def on_ready():
    log.info("sentiment bot ready as %s in %d guild(s)", bot.user, len(bot.guilds))


async def main():
    if not config.TOKEN_SENTIMENT:
        print("Missing token: DISCORD_TOKEN_SENTIMENT")
        return
    async with bot:
        await bot.start(config.TOKEN_SENTIMENT)


if __name__ == "__main__":
    asyncio.run(main())
