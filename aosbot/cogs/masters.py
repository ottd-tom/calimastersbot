"""
/top8 and /rank for the Cali Masters and Texas Masters bots.

One cog class, instantiated once per bot with the region's settings.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from functools import lru_cache

import discord
from discord import app_commands
from discord.ext import commands

from ..api import fetch_json
from ..config import CALI_URL, TEXAS_URL
from ..reply import send, warn

_EVENT_KEY = re.compile(r"^event_(\d+)_id$")


@dataclass(frozen=True)
class Region:
    name: str          # "Cali" / "Texas"
    url: str           # scores API
    sum_key: str       # "top4_sum" / "top5_sum"
    events_counted: int
    table_url: str
    token_joke: bool = False   # 20% "please donate" on /top8


CALI  = Region("Cali",  CALI_URL,  "top4_sum", 4, "https://aos-events.com/calimasters", token_joke=True)
TEXAS = Region("Texas", TEXAS_URL, "top5_sum", 5, "https://aos-events.com/texmasters")


@lru_cache(maxsize=1)
def _words_by_letter() -> dict[str, list[str]]:
    from wordfreq import top_n_list          # slow import; only when first needed
    common = top_n_list("en", 20000)
    return {ch: [w.capitalize() for w in common if w.startswith(ch)] for ch in "abcdefghijklmnopqrstuvwxyz"}


def random_acronym(letters: str) -> str:
    buckets = _words_by_letter()
    return " ".join(random.choice(buckets[ch]) if buckets.get(ch) else ch.upper()
                    for ch in letters.lower())


EASTER_EGGS = {
    "corsairs": "utter trash",
    "ligmar":   "BALLS!",
    "jessica":  "☠️ Best Corsair ☠️",
}


class MastersCog(commands.Cog):
    def __init__(self, bot: commands.Bot, region: Region):
        self.bot = bot
        self.region = region

    @app_commands.command(name="top8", description="Show the current Masters top 8")
    async def top8(self, interaction: discord.Interaction):
        r = self.region
        if r.token_joke and random.random() < 0.2:
            return await send(interaction, "Bot tokens expired, please donate")

        await interaction.response.defer()
        data = await fetch_json(r.url)
        top = data[:8]
        if not top:
            return await send(interaction, "No data available.")

        lines = [f"**🏆 {r.name} Masters Top 8 🏆**"]
        for i, rec in enumerate(top, 1):
            lines.append(f"{i}. **{rec['first_name']} {rec['last_name']}** — {rec[r.sum_key]} pts")
        lines += ["", f"Full table: {r.table_url}"]
        await send(interaction, "\n".join(lines))

    @app_commands.command(name="rank", description="Show rank, score and event count for a player")
    @app_commands.describe(player="First name, last name, or full name")
    async def rank(self, interaction: discord.Interaction, player: str):
        r = self.region
        key = player.strip().lower()
        if key in EASTER_EGGS:
            return await send(interaction, EASTER_EGGS[key])
        if key == "tsd":
            return await send(interaction, f"`TSD` stands for: **{random_acronym('TSD')}**")

        await interaction.response.defer()
        data = await fetch_json(r.url)
        matches = [
            (i, rec) for i, rec in enumerate(data, 1)
            if key in (f"{rec['first_name']} {rec['last_name']}".lower(),
                       rec["first_name"].lower(), rec["last_name"].lower())
        ]
        if not matches:
            return await warn(interaction, f"No player found matching `{player}`.")

        lines = []
        for pos, rec in matches:
            played = sum(1 for k, v in rec.items() if _EVENT_KEY.match(k) and v)
            cnt = min(played, r.events_counted)
            lines.append(f"#{pos} **{rec['first_name']} {rec['last_name']}** — "
                         f"{rec[r.sum_key]} pts ({cnt} of {r.events_counted})")
        await send(interaction, "\n".join(lines))
