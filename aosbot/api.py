"""
HTTP access to aos-events.com and Best Coast Pairings.

All the headers/params boilerplate that was copy-pasted into every command
lives here once.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp

from .config import (
    API_URL, BASE_EVENT_URL, BCP_BASE, BCP_API_KEY, BCP_CLIENT_ID,
    ITC_LEAGUE_ID, ITC_REGION_ID,
)

# ── aos-events.com ───────────────────────────────────────────────────────────

async def fetch_json(url: str, *, params: dict | None = None, headers: dict | None = None) -> Any:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()


async def fetch_winrates(time_filter: str = "all") -> dict:
    return await fetch_json(f"{API_URL}/api/aos/winrates", params={"time": time_filter})


async def fetch_enhancement(time_filter: str = "all", rounds_filter: str = "all") -> dict:
    return await fetch_json(f"{API_URL}/api/aos/enhancement_winrates",
                            params={"time": time_filter, "rounds": rounds_filter})


async def fetch_popularity(time_filter: str = "all") -> dict:
    return await fetch_json(f"{API_URL}/api/aos/popularity", params={"time": time_filter})


async def fetch_five_win_players() -> list[dict]:
    return await fetch_json(f"{API_URL}/api/aos/five_win_players")


async def fetch_rolling_winrates(faction: str, window: int) -> dict:
    return await fetch_json(f"{API_URL}/api/aos/rolling_winrates/faction/{quote(faction)}",
                            params={"window": window})


async def fetch_release_events() -> dict | None:
    try:
        return await fetch_json(f"{API_URL}/api/aos/release_events")
    except Exception:
        return None


# ── Best Coast Pairings ──────────────────────────────────────────────────────

def bcp_headers(user_agent: str = "AoSBot/1.0") -> dict:
    return {
        "Accept":     "application/json",
        "x-api-key":  BCP_API_KEY,
        "client-id":  BCP_CLIENT_ID,
        "User-Agent": user_agent,
    }


async def bcp_get(path: str, params: dict | None = None, *,
                  session: aiohttp.ClientSession | None = None,
                  sem: asyncio.Semaphore | None = None) -> Any:
    """GET {BCP_BASE}/{path}. Reuses `session` if given."""
    url = path if path.startswith("http") else f"{BCP_BASE}/{path.lstrip('/')}"

    async def _do(s):
        async with s.get(url, params=params, headers=bcp_headers()) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _run(s):
        if sem:
            async with sem:
                return await _do(s)
        return await _do(s)

    if session is not None:
        return await _run(session)
    async with aiohttp.ClientSession() as s:
        return await _run(s)


def extract_players(raw: dict) -> list[dict]:
    if isinstance(raw, dict):
        if isinstance(raw.get("active"), list):
            return raw["active"]
        if isinstance(raw.get("data"), list):
            return raw["data"]
    return []


async def bcp_events(days_back: int = 7, days_ahead: int = 3, *, session=None, sem=None,
                     skip_team_events: bool = True) -> list[dict]:
    """AoS (gameType 4) events in a date window around today."""
    today = datetime.utcnow().date()
    params = {
        "limit":         100,
        "sortAscending": "true",
        "sortKey":       "eventDate",
        "startDate":     (today - timedelta(days=days_back)).isoformat(),
        "endDate":       (today + timedelta(days=days_ahead)).isoformat(),
        "gameType":      "4",
    }
    data = await bcp_get("events", params, session=session, sem=sem)
    events = data.get("data", [])
    if skip_team_events:
        events = [e for e in events if not (e.get("teamEvent") or e.get("doublesEvent"))]
    return events


def search_events(events: list[dict], query: str) -> list[dict]:
    """Events whose name, address or city contains `query` (case-insensitive)."""
    q = query.lower()
    out = []
    for e in events:
        if e.get("teamEvent") or e.get("doublesEvent"):
            continue
        hay = " ".join((e.get(k) or "") for k in ("name", "formatted_address", "city")).lower()
        if q in hay:
            out.append(e)
    return out


async def bcp_players(event_id: str, *, session=None, sem=None) -> list[dict]:
    raw = await bcp_get(f"events/{event_id}/players", {"placings": "true", "limit": 500},
                        session=session, sem=sem)
    return extract_players(raw)


async def bcp_pairings(event_id: str, rnd: int, *, session=None, sem=None) -> list[dict]:
    raw = await bcp_get(f"events/{event_id}/pairings",
                        {"eventId": event_id, "round": rnd, "pairingType": "Pairing"},
                        session=session, sem=sem)
    return raw.get("active") or raw.get("data") or []


async def bcp_itc_placings(limit: int = 2000, *, placings_type: str = "player",
                           league_id: str = ITC_LEAGUE_ID, army_id: str | None = None,
                           session=None) -> list[dict]:
    params = {
        "limit":         limit,
        "placingsType":  placings_type,
        "leagueId":      league_id,
        "regionId":      ITC_REGION_ID,
        "sortAscending": "false",
    }
    if army_id:
        params["armyId"] = army_id
    data = await bcp_get("placings", params, session=session)
    return data.get("data", [])


async def bcp_army_id(canonical: str, *, session=None) -> str | None:
    data = await bcp_get("armies", {"gameType": 4}, session=session)
    for a in data.get("data", []):
        if a["name"].lower() == canonical.lower() or a.get("gwFactionName", "").lower() == canonical.lower():
            return a["id"]
    return None


# ── Small shape helpers for BCP objects ─────────────────────────────────────

def player_name(side: dict | None) -> str:
    user = (side or {}).get("user") or {}
    full = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
    return full or "?"


def metric_map(p: dict) -> dict:
    """p['metrics'] can be missing OR present-but-None."""
    return {m.get("name"): m.get("value") for m in (p.get("metrics") or [])}


def side_points(pairing: dict, key: str) -> str:
    """'player1Game' can be missing OR present-but-None."""
    val = (pairing.get(key) or {}).get("points")
    return "" if val is None else str(val)


def user_id_of(obj: dict | None) -> str | None:
    """BCP isn't consistent about where userId lives; try the plausible spots."""
    if not obj:
        return None
    for key in ("userId", "user_id"):
        if obj.get(key):
            return str(obj[key])
    user = obj.get("user") or {}
    for key in ("id", "userId", "_id"):
        if user.get(key):
            return str(user[key])
    return None
