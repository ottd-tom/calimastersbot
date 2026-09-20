"""
Scion tracker: where are the tracked players playing this weekend and how are they doing?

/sciontracker  /scionlist  /scionid
"""

from __future__ import annotations

import asyncio
import logging
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from scion_image import render_scion_images_async, scion_fonts_available

from ..api import (
    bcp_events, bcp_itc_placings, bcp_pairings, bcp_players, metric_map,
    player_name, side_points, user_id_of,
)
from ..config import (
    SCIONS, SCION_CACHE_TTL, SCION_CONCURRENCY, SCION_LOOKAHEAD_DAYS, SCION_LOOKBACK_DAYS,
    SCION_MAX_ROUNDS, SCION_SKIP_TEAM_EVENTS, faction_colour, shortest_alias,
)
from ..reply import send, send_files, send_lines, warn

log = logging.getLogger(__name__)

USE_IMAGES = scion_fonts_available()
_cache: dict[tuple, tuple[float, tuple]] = {}


def _event_max_round(ev: dict) -> int:
    for key in ("numberOfRounds", "rounds", "totalRounds", "numRounds"):
        v = ev.get(key)
        if isinstance(v, int) and 1 <= v <= SCION_MAX_ROUNDS:
            return v
    return SCION_MAX_ROUNDS


def _record_of(p: dict) -> str:
    mm = metric_map(p)
    w, l, d = mm.get("Wins"), mm.get("Losses"), mm.get("Draws", mm.get("Ties"))
    if w is None and l is None:
        return ""
    parts = [str(w or 0), str(l or 0)]
    if d not in (None, 0, "0"):
        parts.append(str(d))
    return "-".join(parts)


def _result_str(my_game: dict | None, opp_game: dict | None) -> str:
    """W / L / D, or '' if the game isn't scored yet."""
    r = (my_game or {}).get("gameResult")
    if isinstance(r, str) and r.strip():
        return r.strip()[0].upper()
    if isinstance(r, int) and r in (1, 2, 3):        # observed BCP coding
        return {1: "W", 2: "L", 3: "D"}[r]
    a, b = (my_game or {}).get("points"), (opp_game or {}).get("points")
    if a is None or b is None:
        return ""
    return "W" if a > b else "L" if a < b else "D"


async def _scan_event(session, ev: dict, sem: asyncio.Semaphore) -> dict | None:
    """One /players call decides whether this event matters."""
    try:
        players = await bcp_players(ev["id"], session=session, sem=sem)
    except Exception:
        log.exception("sciontracker: player fetch failed for %s", ev.get("id"))
        return None

    by_uid = {uid: p for p in players if (uid := user_id_of(p))}
    present = [uid for uid in SCIONS if uid in by_uid]
    if not present:
        return None

    rnd, pairings = None, []
    for candidate in range(_event_max_round(ev), 0, -1):
        try:
            rows = await bcp_pairings(ev["id"], candidate, session=session, sem=sem)
        except Exception:
            log.exception("sciontracker: pairing fetch failed for %s r%s", ev.get("id"), candidate)
            continue
        if rows:
            rnd, pairings = candidate, rows
            break

    out = []
    for uid in present:
        me = by_uid[uid]
        canon = (me.get("faction") or {}).get("name", "") or ""
        row = {"player": SCIONS.get(uid) or player_name(me), "faction": shortest_alias(canon),
               "colour": faction_colour(canon), "record": _record_of(me),
               "score": "", "result": "", "opponent": "", "opp_faction": ""}

        match = side = None
        for p in pairings:
            for s in ("player1", "player2"):
                if user_id_of(p.get(s)) == uid:
                    match, side = p, s
                    break
            if match:
                break

        if match:
            other = "player2" if side == "player1" else "player1"
            if match.get(other):
                row["opponent"] = player_name(match.get(other))
                opp_rec = by_uid.get(user_id_of(match.get(other)))
                if opp_rec:
                    row["opp_faction"] = shortest_alias((opp_rec.get("faction") or {}).get("name", ""))
                mp, op = side_points(match, f"{side}Game"), side_points(match, f"{other}Game")
                if mp or op:
                    row["score"] = f"{mp or '-'}-{op or '-'}"
                row["result"] = _result_str(match.get(f"{side}Game"), match.get(f"{other}Game"))
            else:
                row["opponent"], row["result"] = "(bye)", "W"
        else:
            row["opponent"] = "not paired yet" if rnd else "pairings not posted"
        out.append(row)

    out.sort(key=lambda r: r["player"].lower())
    return {"event": ev.get("name", "Unknown event"),
            "round": f"Round {rnd}" if rnd else "No pairings posted",
            "rows": out}


def _text_fallback(sections: list[dict]) -> list[str]:
    lines = []
    for sec in sections:
        lines.append(f"{sec['event']} - {sec['round']}")
        for r in sec["rows"]:
            who = f"{r['player']} ({r['faction']})" if r["faction"] else r["player"]
            rec = f"[{r['record']}]" if r["record"] else ""
            opp = f"{r['opponent']} ({r['opp_faction']})" if r["opp_faction"] else r["opponent"]
            lines.append(f"  {who:<32} {rec:<8} {r['score'] or '-':>7} {r['result'] or ' ':<2} vs  {opp}")
        lines.append("")
    return lines


async def _send_output(interaction, sections: list[dict], scanned: int):
    total = sum(len(s["rows"]) for s in sections)
    subtitle = (f"{total} scion{'s' if total != 1 else ''} · "
                f"{len(sections)} event{'s' if len(sections) != 1 else ''} · "
                f"{scanned} live event{'s' if scanned != 1 else ''} scanned")
    if USE_IMAGES:
        try:
            buffers = await render_scion_images_async(sections, title="Scion Tracker", subtitle=subtitle)
            await send_files(interaction, [discord.File(b, filename=f"scions_{i}.png")
                                           for i, b in enumerate(buffers, 1)])
            return
        except Exception:
            log.exception("Scion image render failed, falling back to text")
    await send_lines(interaction, _text_fallback(sections))


class ScionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sciontracker", description="Current pairings and results for tracked players")
    @app_commands.describe(days="Include events that started up to this many days ago")
    async def sciontracker(self, interaction: discord.Interaction,
                           days: app_commands.Range[int, 0, 14] = SCION_LOOKBACK_DAYS):
        if not SCIONS:
            return await warn(interaction, ":warning: The `SCIONS` roster is empty. Add BCP userIds with `/scionid`.")

        cache_key = (days, tuple(sorted(SCIONS)))
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < SCION_CACHE_TTL:
            await interaction.response.defer()
            return await _send_output(interaction, *cached[1])

        await interaction.response.defer()
        sem = asyncio.Semaphore(SCION_CONCURRENCY)
        async with aiohttp.ClientSession() as session:
            try:
                events = await bcp_events(days, SCION_LOOKAHEAD_DAYS, session=session, sem=sem,
                                          skip_team_events=SCION_SKIP_TEAM_EVENTS)
            except Exception as e:
                return await send(interaction, f":x: Couldn't fetch events: {e}")
            if not events:
                return await send(interaction, ":mag: No AoS events found in that window.")
            results = await asyncio.gather(*[_scan_event(session, ev, sem) for ev in events])

        sections = [s for s in results if s]
        if not sections:
            return await send(interaction, f":mag: No tracked players found at any of the {len(events)} live event(s).")

        _cache[cache_key] = (time.time(), (sections, len(events)))
        await _send_output(interaction, sections, len(events))

    @app_commands.command(name="scionlist", description="Show the tracked scion roster")
    async def scionlist(self, interaction: discord.Interaction):
        if not SCIONS:
            return await send(interaction, "No scions tracked yet. Use `/scionid` to find BCP userIds.")
        lines = [f"Tracked scions ({len(SCIONS)}):"] + [f"{name:<28} {uid}" for uid, name in SCIONS.items()]
        await send_lines(interaction, lines)

    @app_commands.command(name="scionid", description="Look up a BCP userId by player name")
    @app_commands.describe(name="Any part of the player's name (3+ characters)")
    async def scionid(self, interaction: discord.Interaction, name: str):
        name = name.strip()
        if len(name) < 3:
            return await warn(interaction, ":warning: Give me at least 3 characters.")
        await interaction.response.defer()
        data = await bcp_itc_placings()
        key = name.lower()
        matches = [e for e in data if key in player_name(e).lower()]
        if not matches:
            return await send(interaction, f"No ITC entries matching **{name}**. "
                                           "They may not have played a ranked event this season.")
        lines = [f'BCP userIds matching "{name}":', ""]
        lines += [f'"{user_id_of(e) or "?"}": "{player_name(e)}",' for e in matches[:25]]
        if len(matches) > 25:
            lines.append(f"... and {len(matches) - 25} more; narrow your search.")
        await send_lines(interaction, lines)
