"""
Faction / player statistics from aos-events.com.

/winrates  /rollwr  /popularity  /artefacts  /traits  /formations  /units  /hof  /playerwr
"""

from __future__ import annotations

import asyncio
import logging
import re
import string
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Literal

import aiohttp
import discord
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from discord import app_commands
from discord.ext import commands

from ..api import (
    bcp_itc_placings, fetch_enhancement, fetch_five_win_players, fetch_popularity,
    fetch_release_events, fetch_rolling_winrates, fetch_winrates,
)
from ..autocomplete import faction_autocomplete
from ..config import (
    ALLIANCE_COLORS, AOS_COACH_SERVER_ID, BOT_ACTIONS_CHANNEL_ID, CURRENT_LEAGUE_YEAR,
    EMOJI_MAP, EXCLUDE_FACTIONS, FACTION_ALLIANCE, LEAGUE_YEARS, TIME_LABELS, resolve_faction,
)
from ..reply import send, send_lines, warn

log = logging.getLogger(__name__)

TimeFilter = Literal["all", "current", "recent", "battlescroll"]
SOURCE = "Source: https://aos-events.com"


def pct(wins, games) -> float:
    return (wins / games * 100) if games else 0.0


# ── Rolling win-rate chart ───────────────────────────────────────────────────

MIN_GAMES = 15   # trim observations with too few games (same logic as web UI)


def build_rolling_chart(faction: str, points: list[dict], window: int,
                        release_events: dict | None = None) -> BytesIO:
    """Render a rolling win-rate line chart and return a PNG BytesIO."""
    pts = sorted(points, key=lambda d: d["date"])
    lo, hi = 0, len(pts) - 1
    while lo < hi and pts[lo]["games"] <= MIN_GAMES:
        lo += 1
    while hi > lo and pts[hi]["games"] <= MIN_GAMES:
        hi -= 1
    pts = pts[lo:hi + 1]
    if not pts:
        raise ValueError("No data remaining after trimming low-sample observations.")

    dates    = [datetime.strptime(p["date"], "%Y-%m-%d") for p in pts]
    winrates = [p["win_rate_pct"] for p in pts]
    games    = [p["games"] for p in pts]
    lower    = [p["lower_95"] for p in pts]
    upper    = [p["upper_95"] for p in pts]
    color = ALLIANCE_COLORS.get(FACTION_ALLIANCE.get(faction, ""), "#5865F2")

    fig, ax = plt.subplots(figsize=(9, 4), dpi=130)
    fig.patch.set_facecolor("#2b2d31")
    ax.set_facecolor("#2b2d31")

    if all(v is not None for v in lower + upper):
        ax.fill_between(dates, lower, upper, color=color, alpha=0.12, zorder=1, label="_nolegend_")
    ax.axhline(50, color="#ffffff", linewidth=0.8, linestyle="--", alpha=0.4, zorder=1)
    ax.plot(dates, winrates, color=color, linewidth=2.2, zorder=3)

    if release_events:
        start, end = dates[0], dates[-1]
        for bs_str in release_events.get("battlescrolls", []):
            d = datetime.strptime(bs_str, "%Y-%m-%d")
            if start <= d <= end:
                ax.axvline(d, color="#aaaaaa", linewidth=1.0, linestyle="--", alpha=0.7, zorder=2)
                ax.text(d, 31.5, "BS", color="#aaaaaa", fontsize=7, ha="center", va="bottom", zorder=4)
        for entry in release_events.get("faction_books", []):
            if faction not in entry.get("factions", []):
                continue
            d = datetime.strptime(entry["date"], "%Y-%m-%d")
            if start <= d <= end:
                ax.axvline(d, color="#f0c040", linewidth=1.5, linestyle="-", alpha=0.85, zorder=2)
                ax.text(d, 31.5, "Book", color="#f0c040", fontsize=7, ha="center", va="bottom", zorder=4)

    ax.set_ylim(30, 70)
    ax.set_xlim(dates[0], dates[-1])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8, color="#dcddde")
    plt.setp(ax.get_yticklabels(), fontsize=8, color="#dcddde")
    for spine in ax.spines.values():
        spine.set_edgecolor("#40444b")
    ax.tick_params(colors="#40444b", which="both")
    ax.grid(axis="y", color="#40444b", linewidth=0.5, alpha=0.6)

    ax.annotate(f"{winrates[-1]:.1f}%", xy=(dates[-1], winrates[-1]),
                xytext=(-42, 8), textcoords="offset points",
                fontsize=9, color="#ffffff", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#aaaaaa", lw=0.8))
    ax.set_title(f"{faction}  —  {window}-day rolling win rate",
                 color="#ffffff", fontsize=11, fontweight="bold", pad=10)
    ax.set_ylabel("Win Rate", color="#dcddde", fontsize=9)
    fig.text(0.99, 0.01,
             f"{dates[0].strftime('%d %b %Y')} – {dates[-1].strftime('%d %b %Y')}  |  "
             f"latest window: {games[-1]} games  |  aos-events.com",
             ha="right", va="bottom", fontsize=7, color="#72767d")
    plt.tight_layout(pad=1.2)

    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


async def make_rolling_chart_file(faction: str, window: int) -> discord.File:
    """Fetch data + render. Raises ValueError with a user-facing message on no data."""
    data = await fetch_rolling_winrates(faction, window)
    points = (data.get("series") or {}).get(f"{window}_all", [])
    if not points:
        raise ValueError(f"No rolling win-rate data found for **{faction}** ({window}-day).")
    release_events = await fetch_release_events()
    loop = asyncio.get_running_loop()
    buf = await loop.run_in_executor(None, build_rolling_chart, faction, points, window, release_events)
    return discord.File(buf, filename=f"rollwr_{faction.replace(' ', '_')}_{window}d.png")


ROLLWR_WARNING = (
    "The rolling win-rate command is intended to augment discussion on a faction's "
    "performance and should only be used as part of lively debate. It is not intended "
    "as a tool to quickly produce a chart just for the sake of doing so.  If you are "
    "interested in seeing the rolling win-rates of factions, please visit "
    "https://aos-events.com/winrate_stats#rolling where you can also find many other "
    "useful statistics.  If you must use it in the AoS Coach server, please do so in "
    f"<#{BOT_ACTIONS_CHANNEL_ID}>.  Spamming the bot for anything other than contribution "
    "towards discussion may result in moderator action against you.  Are you sure you "
    "would like to continue?"
)


class RollWrConfirmView(discord.ui.View):
    """Yes / No / Post in #bot-actions gate used on the AoS Coach server."""

    def __init__(self, user_id: int, faction: str, window: int, *, timeout=120):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.faction = faction
        self.window = window

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("These buttons aren't for you.", ephemeral=True)
            return False
        return True

    def _disable_all(self):
        for child in self.children:
            child.disabled = True

    async def on_timeout(self):
        self._disable_all()

    async def _run(self, interaction: discord.Interaction, channel: discord.abc.Messageable):
        self._disable_all()
        self.stop()
        await interaction.response.edit_message(
            content=f"Posting chart in {getattr(channel, 'mention', 'this channel')}…", view=self)
        try:
            file = await make_rolling_chart_file(self.faction, self.window)
        except ValueError as e:
            return await channel.send(f":warning: {e}")
        except Exception as e:
            log.exception("rollwr chart build failed")
            return await channel.send(f":x: Chart error: {e}")
        await channel.send(file=file)

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def yes_button(self, interaction: discord.Interaction, _):
        await self._run(interaction, interaction.channel)

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no_button(self, interaction: discord.Interaction, _):
        self._disable_all()
        self.stop()
        await interaction.response.edit_message(content="Cancelled — no chart posted.", view=self)

    @discord.ui.button(label="Post in #bot-actions", style=discord.ButtonStyle.success)
    async def bot_actions_button(self, interaction: discord.Interaction, _):
        channel = interaction.guild.get_channel(BOT_ACTIONS_CHANNEL_ID) if interaction.guild else None
        if channel is None:
            return await interaction.response.send_message(":x: Couldn't find the #bot-actions channel.", ephemeral=True)
        await self._run(interaction, channel)


# ── /playerwr helpers ────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("’", "'").replace("‘", "'").replace("`", "'")
    name = name.casefold().translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", name).strip()


async def _placings_for_year(session: aiohttp.ClientSession, player_name: str, league_id: str,
                             target_user_id: str | None = None) -> dict | None:
    """{'wins','ties','losses','userId'} for a player in one league year, or None."""
    try:
        data = await bcp_itc_placings(league_id=league_id, session=session)
    except Exception:
        log.exception("playerwr: placings fetch failed for league %s", league_id)
        return None

    want = normalize_name(player_name)
    for entry in data:
        user = entry.get("user")
        if not user:
            continue
        uid = entry.get("userId")
        if target_user_id:
            hit = uid == target_user_id
        else:
            hit = normalize_name(f"{user.get('firstName', '')} {user.get('lastName', '')}") == want
        if hit:
            return {"wins": entry.get("wins", 0), "ties": entry.get("ties", 0),
                    "losses": entry.get("losses", 0), "userId": uid}
    return None


PLAYERWR_EGGS = {
    "the noog": "I dunno man, that's a tricky one. A lot of his events have dubious records and "
                "can't be verified. The most accurate data we have says its around 19% though.",
    "gareth thomas": "I dunno man, that's a tricky one. Genius of that level is hard to quantify.  "
                     "Must be like over 90% though.",
}


# ── Cog ──────────────────────────────────────────────────────────────────────

class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # /winrates -------------------------------------------------------------
    @app_commands.command(name="winrates", description="Faction win rates (all factions, or one)")
    @app_commands.describe(faction="Leave empty for all factions", time="Time window")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def winrates(self, interaction: discord.Interaction,
                       faction: str | None = None, time: TimeFilter = "all"):
        canonical = resolve_faction(faction)
        if faction and not canonical:
            return await warn(interaction, f"Unknown faction `{faction}`.")
        await interaction.response.defer()
        data = await fetch_winrates(time)
        label = TIME_LABELS[time]

        if canonical:
            f = next((x for x in data.get("factions", []) if x["name"] == canonical), None)
            if not f:
                return await send(interaction, f"Faction '{canonical}' not found.")
            return await send(interaction,
                              f"{EMOJI_MAP.get(canonical, '')} **{canonical}** ({label}): "
                              f"{f['wins']}/{f['games']} ({pct(f['wins'], f['games']):.2f}%)\n{SOURCE}")

        items = [f for f in data.get("factions", []) if f["name"] not in EXCLUDE_FACTIONS]
        items.sort(key=lambda f: pct(f["wins"], f["games"]), reverse=True)
        lines = [f"AoS Faction Win Rates ({label}) sorted:"]
        lines += [f"{EMOJI_MAP.get(f['name'], '')} {f['name']}: {f['wins']}/{f['games']} "
                  f"({pct(f['wins'], f['games']):.2f}%)" for f in items]
        lines += ["", SOURCE]
        await send_lines(interaction, lines)

    # /rollwr ---------------------------------------------------------------
    @app_commands.command(name="rollwr", description="Rolling win-rate chart for a faction")
    @app_commands.describe(faction="Faction", window="Rolling window in days")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def rollwr(self, interaction: discord.Interaction, faction: str,
                     window: Literal[28, 70] = 28):
        canonical = resolve_faction(faction)
        if not canonical:
            return await warn(interaction, f"Unknown faction `{faction}`. Try an alias like `fec`, `sce`, `dok`…")

        gated = interaction.guild is not None and interaction.guild.id == AOS_COACH_SERVER_ID
        if gated and interaction.channel_id != BOT_ACTIONS_CHANNEL_ID:
            view = RollWrConfirmView(interaction.user.id, canonical, window)
            return await interaction.response.send_message(ROLLWR_WARNING, view=view, ephemeral=True)

        await interaction.response.defer()
        try:
            file = await make_rolling_chart_file(canonical, window)
        except ValueError as e:
            return await send(interaction, f":warning: {e}")
        except Exception as e:
            log.exception("rollwr chart build failed")
            return await send(interaction, f":x: Chart error: {e}")
        await send(interaction, file=file)

    # /popularity -----------------------------------------------------------
    @app_commands.command(name="popularity", description="Faction / manifestation / drop popularity")
    async def popularity(self, interaction: discord.Interaction,
                         category: Literal["factions", "manifestations", "drops"] = "factions",
                         time: TimeFilter = "all"):
        await interaction.response.defer()
        items = (await fetch_popularity(time)).get(category, [])
        if not items:
            return await send(interaction, f"No popularity data for {category} ({time}).")
        total = sum(it["games"] for it in items)
        lines = [f"📊 Popularity for {category.capitalize()} ({TIME_LABELS[time]}):"]
        for it in sorted(items, key=lambda x: x["games"], reverse=True):
            prefix = EMOJI_MAP.get(it["name"], "") + " " if category == "factions" else ""
            lines.append(f"{prefix}{it['name']}: {it['games']} games ({pct(it['games'], total):.2f}%)")
        lines += ["", "More info: https://aos-events.com/faction_stats#popularity"]
        await send_lines(interaction, lines)

    # /artefacts /traits /formations ----------------------------------------
    async def _enhancement(self, interaction, faction, time, key, singular, title):
        canonical = resolve_faction(faction)
        if not canonical:
            return await warn(interaction, f"Unknown faction `{faction}`.")
        await interaction.response.defer()
        items = [i for i in (await fetch_enhancement(time)).get(key, []) if i.get("faction") == canonical]
        if not items:
            return await send(interaction, f"No {singular} data for {canonical}.")
        lines = [f"🏹 {title} Win Rates for {canonical} ({TIME_LABELS[time]}) 🏹"]
        lines += [f"{i[singular]}: {i['wins']}/{i['games']} wins ({i['win_rate_pct']:.2f}%)" for i in items]
        lines += ["", SOURCE]
        await send_lines(interaction, lines)

    @app_commands.command(name="artefacts", description="Artefact win rates for a faction")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def artefacts(self, interaction: discord.Interaction, faction: str, time: TimeFilter = "all"):
        await self._enhancement(interaction, faction, time, "artifacts", "artifact", "Artefact")

    @app_commands.command(name="traits", description="Trait win rates for a faction")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def traits(self, interaction: discord.Interaction, faction: str, time: TimeFilter = "all"):
        await self._enhancement(interaction, faction, time, "traits", "trait", "Trait")

    @app_commands.command(name="formations", description="Formation win rates for a faction")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def formations(self, interaction: discord.Interaction, faction: str, time: TimeFilter = "all"):
        await self._enhancement(interaction, faction, time, "formations", "formation", "Formation")

    # /units ----------------------------------------------------------------
    @app_commands.command(name="units", description="Unit win rates for a faction")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def units(self, interaction: discord.Interaction, faction: str, time: TimeFilter = "all"):
        canonical = resolve_faction(faction)
        if not canonical:
            return await warn(interaction, f"Unknown faction `{faction}`.")
        await interaction.response.defer()
        units = [u for u in (await fetch_winrates(time)).get("units", []) if u.get("faction") == canonical]
        if not units:
            return await send(interaction, f"No unit data for {canonical} ({time}).")
        units.sort(key=lambda u: pct(u["wins"], u["games"]), reverse=True)
        lines = [f"🏹 Unit Win-Rates for {canonical} ({TIME_LABELS[time]}) 🏹"]
        lines += [f"{u['name']}: {u['wins']}/{u['games']} wins ({pct(u['wins'], u['games']):.2f}%)" for u in units]
        lines += ["", "Full stats at: https://aos-events.com/faction_stats#units"]
        await send_lines(interaction, lines)

    # /hof ------------------------------------------------------------------
    @app_commands.command(name="hof", description="Hall of Fame (5+ win) players for a faction")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def hof(self, interaction: discord.Interaction, faction: str):
        if faction.strip().lower() == "legions of nagash":
            return await send(interaction, "Legions of Nagash are no longer legal... however, "
                                           "Gareth Thomas was the last winner of ITC LoN.")
        canonical = resolve_faction(faction)
        if not canonical:
            return await warn(interaction, f"Unknown faction `{faction}`.")
        await interaction.response.defer()
        entries = [e for e in await fetch_five_win_players() if e.get("faction") == canonical]
        if not entries:
            return await send(interaction, f"No Hall of Fame entries for {canonical}.")
        lines = [f"🏆 Hall of Fame for {canonical} 🏆"]
        for e in entries:
            date_str = (e.get("event_date") or "").split("T")[0]
            lines.append(f"{date_str} - {e.get('player_name')} at {e.get('event_name')} (Wins: {e.get('wins')})")
        lines += ["", "For lists and more info: https://aos-events.com/faction_stats#hof"]
        await send_lines(interaction, lines)

    # /playerwr -------------------------------------------------------------
    @app_commands.command(name="playerwr", description="Yearly and overall ITC win rates for a player")
    @app_commands.describe(first_name="First name", last_name="Last name")
    async def playerwr(self, interaction: discord.Interaction, first_name: str, last_name: str):
        display = f"{first_name.strip()} {last_name.strip()}"
        key = display.lower()
        if key in PLAYERWR_EGGS:
            return await send(interaction, PLAYERWR_EGGS[key])
        if key == "gareth thomasx":
            key = "gareth thomas"

        await interaction.response.defer()
        stats: dict[int, dict] = {}
        user_id = None
        years = [CURRENT_LEAGUE_YEAR] + sorted((y for y in LEAGUE_YEARS if y != CURRENT_LEAGUE_YEAR), reverse=True)

        async with aiohttp.ClientSession() as session:
            for year in years:
                if year == CURRENT_LEAGUE_YEAR:
                    res = await _placings_for_year(session, key, LEAGUE_YEARS[year])
                    if res:
                        user_id = res.get("userId")
                elif user_id:
                    res = await _placings_for_year(session, key, LEAGUE_YEARS[year], target_user_id=user_id)
                else:
                    res = None
                stats[year] = res or {"wins": "N/A", "ties": "N/A", "losses": "N/A"}

        tw = tt = tl = 0
        for s in stats.values():
            if all(isinstance(s[k], int) for k in ("wins", "ties", "losses")):
                g = s["wins"] + s["ties"] + s["losses"]
                s["win_rate"] = f"{s['wins'] / g * 100:.2f}%" if g else "N/A"
                tw, tt, tl = tw + s["wins"], tt + s["ties"], tl + s["losses"]
            else:
                s["win_rate"] = "N/A"
        total = tw + tt + tl
        overall = f"{tw / total * 100:.2f}%" if total else "N/A"

        lines = ["=" * 55, f"ITC Wins/Ties/Losses/Win Rate for {display}", "=" * 55,
                 f"{'Year':<8} | {'Wins':<6} | {'Ties':<6} | {'Losses':<6} | {'Win Rate':<10}", "-" * 55]
        for year in sorted(stats, reverse=True):
            s = stats[year]
            lines.append(f"{year:<8} | {str(s['wins']):<6} | {str(s['ties']):<6} | "
                         f"{str(s['losses']):<6} | {s['win_rate']:<10}")
        lines += ["-" * 55, f"{'Total':<8} | {tw:<6} | {tt:<6} | {tl:<6} | {overall:<10}",
                  "=" * 55, "Donate at aos-events.com"]
        await send_lines(interaction, lines)
