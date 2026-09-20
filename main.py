"""
Entry point: runs the Cali Masters, AoS Events and Texas Masters bots in one process.

All three are slash-command only and need no privileged intents.
The sentiment bot (which needs Message Content) lives in sentiment_bot.py.

    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import random

import discord
import openai
from discord.ext import commands

from aosbot import config
from aosbot.cogs.bcp import BcpCog
from aosbot.cogs.masters import CALI, TEXAS, MastersCog, Region
from aosbot.cogs.misc import MiscCog
from aosbot.cogs.personas import PersonasCog
from aosbot.cogs.scions import ScionsCog
from aosbot.cogs.stats import StatsCog

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

openai.api_key = config.OPENAI_API_KEY

# Slash commands don't need message content; guilds is enough for bot.guilds and channel lookups.
INTENTS = discord.Intents(guilds=True)


class SlashBot(commands.Bot):
    """commands.Bot with no prefix commands; cogs are attached and synced in setup_hook."""

    def __init__(self, name: str, cog_factories):
        super().__init__(command_prefix=commands.when_mentioned, intents=INTENTS,
                         help_command=None, description=name)
        self.name = name
        self.cog_factories = cog_factories

    async def setup_hook(self):
        for make in self.cog_factories:
            await self.add_cog(make(self))
        if config.DEV_GUILD_ID:
            guild = discord.Object(id=config.DEV_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("%s: synced %d commands to dev guild", self.name, len(self.tree.get_commands(guild=guild)))
        synced = await self.tree.sync()
        log.info("%s: synced %d global commands", self.name, len(synced))

    async def on_ready(self):
        log.info("%s: ready as %s in %d guild(s)", self.name, self.user, len(self.guilds))


def make_masters_bot(region: Region) -> SlashBot:
    return SlashBot(f"{region.name} Masters", [lambda bot: MastersCog(bot, region)])


def make_aos_bot() -> SlashBot:
    return SlashBot("AoS Events", [StatsCog, BcpCog, ScionsCog, PersonasCog, MiscCog])


# ── Login staggering (Discord rate-limits /users/@me across three bots) ─────

_login_lock = asyncio.Lock()


async def run_bot(bot: commands.Bot, token: str, initial_delay: float = 0):
    if initial_delay:
        await asyncio.sleep(initial_delay)

    backoff = 5
    while True:
        async with _login_lock:
            try:
                log.info("%s: logging in…", bot.name)
                await bot.login(token)
                break
            except discord.HTTPException as e:
                if getattr(e, "status", None) == 429:
                    wait = min(180, backoff) + random.uniform(0, 2)
                    log.warning("%s: 429 during login, sleeping %.1fs", bot.name, wait)
                    await bot.close()
                    await asyncio.sleep(wait)
                    backoff *= 2
                    continue
                log.exception("%s: login failed", bot.name)
                await bot.close()
                return
            except Exception:
                log.exception("%s: unexpected error during login", bot.name)
                await bot.close()
                return
    try:
        await bot.connect(reconnect=True)
    finally:
        await bot.close()


async def main():
    tokens = {
        "DISCORD_TOKEN":           config.TOKEN_CALI,
        "DISCORD_TOKEN_AOSEVENTS": config.TOKEN_AOS,
        "TEXAS_DISCORD_BOT":       config.TOKEN_TEXAS,
    }
    missing = [k for k, v in tokens.items() if not v]
    if missing:
        print(f"Missing tokens: {', '.join(missing)}")
        return

    await asyncio.gather(
        run_bot(make_masters_bot(CALI),  config.TOKEN_CALI,  initial_delay=0),
        run_bot(make_aos_bot(),          config.TOKEN_AOS,   initial_delay=12),
        run_bot(make_masters_bot(TEXAS), config.TOKEN_TEXAS, initial_delay=24),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
