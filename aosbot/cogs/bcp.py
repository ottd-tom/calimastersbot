"""
Best Coast Pairings lookups.

/standings  /standingsfull  /pairings  /itcrank  /itcstandings
"""

from __future__ import annotations

import logging
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from pairings_image import fonts_available, render_pairings_images_async, render_standings_images_async

from ..api import (
    bcp_army_id, bcp_events, bcp_itc_placings, bcp_pairings, bcp_players,
    metric_map, player_name, search_events, side_points,
)
from ..autocomplete import faction_autocomplete
from ..config import resolve_faction, shortest_alias
from ..reply import pick_event, send, send_files, send_lines, warn

log = logging.getLogger(__name__)

USE_IMAGES = fonts_available()   # evaluated once; falls back to text if False
MAX_ROUND = 8


def _cell(v) -> str:
    return "" if v is None else str(v)


def _placings_url(ev_id: str, tab: str) -> str:
    return f"https://www.bestcoastpairings.com/event/{ev_id}?active_tab={tab}"


async def _find_events(interaction: discord.Interaction, query: str) -> list[dict] | None:
    """Search this week's events; sends the 'no match' message itself and returns None."""
    events = await bcp_events(days_back=7, days_ahead=3, skip_team_events=False)
    matches = search_events(events, query)
    if not matches:
        await send(interaction, f":mag: No AoS events this week matching `{query}`.")
        return None
    return matches


# ── Standings ────────────────────────────────────────────────────────────────

async def _send_standings(interaction, ev_name, subtitle, metric_names, rows, faction_col, text_lines):
    if USE_IMAGES:
        try:
            buffers = await render_standings_images_async(ev_name, subtitle, metric_names, rows,
                                                          faction_col=faction_col)
            await send_files(interaction, [discord.File(b, filename=f"standings_{i}.png")
                                           for i, b in enumerate(buffers, 1)])
            return
        except Exception:
            log.exception("Standings image render failed, falling back to text")
    await send_lines(interaction, text_lines)


async def do_standings(interaction: discord.Interaction, ev: dict, *, full: bool) -> None:
    ev_name, ev_id = ev["name"], ev["id"]
    players = await bcp_players(ev_id)
    if not players:
        return await send(interaction, f":warning: No players for `{ev_name}` ({ev_id}).")

    metric_names = [m["name"] for m in (players[0].get("metrics") or [])]
    n = len(players)
    plural = "s" if n != 1 else ""

    if full:
        rows = [[_cell(p.get("placing")), player_name(p)] + [_cell(metric_map(p).get(m)) for m in metric_names]
                for p in players]
        header = " | ".join(["Place", "Name"] + metric_names)
        text = [f"Standings for {ev_name} ({ev_id}):", header, "-" * len(header)] + [" | ".join(r) for r in rows]
        await _send_standings(interaction, ev_name, f"Full standings · {n} player{plural}",
                              metric_names, rows, False, text)
    else:
        if "Wins" not in metric_names:
            return await send(interaction, f":warning: No “Wins” metric in `{ev_name}` ({ev_id}).")
        rows = [(_cell(p.get("placing")),
                 shortest_alias((p.get("faction") or {}).get("name", "")),
                 player_name(p),
                 _cell(metric_map(p).get("Wins"))) for p in players]
        header = "Place | Faction | Name                     | Wins"
        text = [f"Standings for {ev_name} ({ev_id}):", header, "-" * len(header)]
        text += [f"{pl:<5} | {fa:<7} | {nm:<24} | {wn:^4}" for pl, fa, nm, wn in rows]
        await _send_standings(interaction, ev_name, f"Standings · {n} player{plural}",
                              ["Wins"], rows, True, text)

    await send(interaction, f"View full placings: {_placings_url(ev_id, 'placings')}")


# ── Pairings ─────────────────────────────────────────────────────────────────

async def do_pairings(interaction: discord.Interaction, ev: dict,
                      requested_round: int | None = None, first_names: set[str] | None = None) -> None:
    ev_name, ev_id = ev["name"], ev["id"]
    pairings, chosen_round = [], requested_round

    async with aiohttp.ClientSession() as session:
        for rnd in ([requested_round] if requested_round else range(MAX_ROUND, 0, -1)):
            rows = await bcp_pairings(ev_id, rnd, session=session)
            if rows:
                pairings, chosen_round = rows, rnd
                break

    if not pairings:
        where = f" in round {requested_round}" if requested_round else ""
        return await send(interaction, f":warning: No pairings found for `{ev_name}` ({ev_id}){where}.")

    if first_names:
        def hit(p):
            for side in ("player1", "player2"):
                u = (p.get(side) or {}).get("user") or {}
                if (u.get("firstName") or "").lower() in first_names:
                    return True
            return False
        pairings = [p for p in pairings if hit(p)]
        if not pairings:
            return await send(interaction, f":mag: No pairings in round {chosen_round} for requested names at `{ev_name}`.")

    def table_no(p) -> str:
        return str(p.get("table") or p.get("tableNumber") or "")

    rows = []
    for p in sorted(pairings, key=lambda p: int(table_no(p) or 0)):
        n1, p1 = player_name(p.get("player1")), side_points(p, "player1Game")
        if p.get("player2"):
            n2, p2 = player_name(p.get("player2")), side_points(p, "player2Game")
        else:
            n2, p2 = "(bye)", ""
        rows.append((table_no(p), n1, p1, n2, p2))

    subtitle = f"Round {chosen_round} · {len(rows)} pairing{'s' if len(rows) != 1 else ''}"
    if first_names:
        subtitle += " · filtered"

    sent = False
    if USE_IMAGES:
        try:
            buffers = await render_pairings_images_async(ev_name, subtitle, rows)
            await send_files(interaction, [discord.File(b, filename=f"pairings_r{chosen_round}_{i}.png")
                                           for i, b in enumerate(buffers, 1)])
            sent = True
        except Exception:
            log.exception("Pairings image render failed, falling back to text")

    if not sent:
        header = f"Pairings for {ev_name} ({ev_id}) — Round {chosen_round}" + (" [filtered]" if first_names else "")
        cols = "Player 1 Name         | Pts | Player 2 Name         | Pts"
        lines = [header, cols, "-" * len(cols)]
        lines += [f"{n1:<22} | {p1:^3} | {n2:<22} | {p2:^3}" for _, n1, p1, n2, p2 in rows]
        await send_lines(interaction, lines)

    if not first_names:
        await send(interaction, f"View full pairings: {_placings_url(ev_id, 'pairings')}")


# ── Cog ──────────────────────────────────────────────────────────────────────

class BcpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="standings", description="Current standings at an event this week")
    @app_commands.describe(event="Part of the event name, city or address (4+ characters)")
    async def standings(self, interaction: discord.Interaction, event: str):
        if len(event.strip()) < 4:
            return await warn(interaction, ":warning: Please use at least 4 characters for your search.")
        await interaction.response.defer()
        if matches := await _find_events(interaction, event.strip()):
            await pick_event(interaction, matches, lambda i, ev: do_standings(i, ev, full=False))

    @app_commands.command(name="standingsfull", description="Full standings (all metrics) at an event this week")
    @app_commands.describe(event="Part of the event name, city or address (4+ characters)")
    async def standingsfull(self, interaction: discord.Interaction, event: str):
        if len(event.strip()) < 4:
            return await warn(interaction, ":warning: Please use at least 4 characters for your search.")
        await interaction.response.defer()
        if matches := await _find_events(interaction, event.strip()):
            await pick_event(interaction, matches, lambda i, ev: do_standings(i, ev, full=True))

    @app_commands.command(name="pairings", description="Pairings for an event this week")
    @app_commands.describe(event="Part of the event name, city or address (4+ characters)",
                           round="Round number (defaults to the latest with pairings)",
                           names="Only show tables with these first names (comma/space separated)")
    async def pairings(self, interaction: discord.Interaction, event: str,
                       round: app_commands.Range[int, 1, MAX_ROUND] | None = None,
                       names: str | None = None):
        if len(event.strip()) < 4:
            return await warn(interaction, ":warning: Please use at least 4 characters for your search.")
        first_names = {n.lower() for n in re.split(r"[,\s]+", names.strip()) if n} if names else None
        await interaction.response.defer()
        if matches := await _find_events(interaction, event.strip()):
            await pick_event(interaction, matches,
                             lambda i, ev: do_pairings(i, ev, requested_round=round, first_names=first_names))

    @app_commands.command(name="itcrank", description="ITC placing and points for a player")
    @app_commands.describe(name="Any part of the player's name (3+ characters)")
    async def itcrank(self, interaction: discord.Interaction, name: str):
        name = name.strip()
        prefix = ""
        if name.lower() == "e":
            prefix, name = "Dirty creature\n", "e pryor"
        if len(name) < 3:
            return await warn(interaction, "Please provide at least 3 characters for the name search.")

        await interaction.response.defer()
        data = await bcp_itc_placings()
        key = name.lower()
        matches = [e for e in data if key in player_name(e).lower()]
        if not matches:
            return await send(interaction, f"{prefix}No ITC placings found for **{name}**.")

        lines = [f"{prefix}**ITC Placings for “{name}”**"]
        for rec in matches:
            pts = rec.get("ITCPoints", rec.get("totalPoints", 0))
            lines.append(f"{player_name(rec)} — Placing: {rec.get('placing')}, Points: {pts:.2f}")
        await send_lines(interaction, lines)

    @app_commands.command(name="itcstandings", description="Top 10 ITC standings, optionally for one faction")
    @app_commands.autocomplete(faction=faction_autocomplete)
    async def itcstandings(self, interaction: discord.Interaction, faction: str | None = None):
        canonical = resolve_faction(faction)
        if faction and not canonical:
            return await warn(interaction, f":warning: Unknown faction `{faction}`.")
        await interaction.response.defer()

        async with aiohttp.ClientSession() as session:
            if canonical:
                army_id = await bcp_army_id(canonical, session=session)
                if not army_id:
                    return await send(interaction, f":warning: Couldn’t find army ID for `{canonical}`.")
                entries = await bcp_itc_placings(10, placings_type="army", army_id=army_id, session=session)
            else:
                entries = await bcp_itc_placings(10, session=session)

        if not entries:
            return await send(interaction, ":warning: No ITC standings found.")

        header = "Placing | Name                     | Points"
        lines = [header, "-" * len(header)]
        for e in entries:
            pts = e.get("ITCPoints", e.get("totalPoints", 0))
            lines.append(f"{e.get('placing', ''):<7} | {player_name(e):<24} | {pts:>7.2f}")
        await send(interaction, "```" + "\n".join(lines) + "```")
