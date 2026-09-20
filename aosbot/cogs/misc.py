"""
Odds and ends on the AoS Events bot.

/help  /servers  /thommoisinadequate  /brianisinadequate
"""

from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from ..api import fetch_json
from ..config import CALI_URL
from ..persona_data import GHB_MISSIONS
from ..reply import send, send_lines

HELP_LINES = [
    "**AoS Events Bot Commands**",
    "/winrates [faction] [time]      - Faction win rates (all, or one faction)",
    "/rollwr <faction> [28|70]       - Rolling win-rate chart",
    "/popularity [category] [time]   - Faction / manifestation / drop popularity",
    "/artefacts <faction> [time]",
    "/traits <faction> [time]",
    "/formations <faction> [time]",
    "/units <faction> [time]",
    "/hof <faction>                  - Hall of Fame (5+ win) players",
    "/itcrank <name>",
    "/itcstandings [faction]",
    "/playerwr <first> <last>",
    "/standings <event>",
    "/standingsfull <event>",
    "/pairings <event> [round] [names]",
    "/sciontracker [days]  /scionlist  /scionid <name>",
    "",
    "Right-click a message → Apps → Rewrite as… (Noog, Jar Jar, Yoda, Noe, Orlando)",
    "",
    "Source: https://aos-events.com",
]


class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="List the AoS Events bot commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.send_message("```\n" + "\n".join(HELP_LINES) + "\n```", ephemeral=True)

    @app_commands.command(name="servers", description="List the servers this bot is in")
    async def servers(self, interaction: discord.Interaction):
        guilds = self.bot.guilds
        if not guilds:
            return await send(interaction, "I'm not in any servers!")
        lines = [f"Servers I'm in ({len(guilds)}):"]
        lines += [f"{i}. {g.name} (ID: {g.id})" for i, g in enumerate(guilds, 1)]
        await send_lines(interaction, lines)

    @app_commands.command(name="thommoisinadequate", description="Pick random GHB missions")
    @app_commands.describe(rounds="How many missions to pick")
    async def thommoisinadequate(self, interaction: discord.Interaction,
                                 rounds: app_commands.Range[int, 1, len(GHB_MISSIONS)] = 5):
        picks = random.sample(GHB_MISSIONS, k=min(rounds, len(GHB_MISSIONS)))
        await send(interaction, "\n".join(f"{i}. {m}" for i, m in enumerate(picks, 1)))

    @app_commands.command(name="brianisinadequate", description="Show the current Cali Masters top 16")
    async def brianisinadequate(self, interaction: discord.Interaction):
        await interaction.response.defer()
        top = (await fetch_json(CALI_URL))[:16]
        if not top:
            return await send(interaction, "No data available.")
        lines = ["**🏆 Cali Masters Top 16 🏆**"]
        lines += [f"{i}. **{r['first_name']} {r['last_name']}** — {r['top4_sum']} pts" for i, r in enumerate(top, 1)]
        lines += ["", "Full table: https://aos-events.com/calimasters"]
        await send(interaction, "\n".join(lines))
