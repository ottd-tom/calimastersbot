import os
import aiohttp
import discord
from discord.ext import commands
import asyncio
import logging
import re
import random
import urllib.parse
from urllib.parse import quote
from wordfreq import top_n_list
from datetime import datetime, timedelta, date
import json
import unicodedata
import string
from pathlib import Path
from PIL import Image
from io import BytesIO
import google.generativeai as genai
from google.generativeai.types import content_types
from google.generativeai import types
import openai
import asyncpg


# Enable logging
logging.basicConfig(level=logging.INFO)

# Load environment variables for both bots
token_leaderboard = os.getenv('DISCORD_TOKEN')
token_aos         = os.getenv('DISCORD_TOKEN_AOSEVENTS')
token_texas       = os.getenv('TEXAS_DISCORD_BOT')
API_URL           = "https://aos-events.com"
CALI_URL          = 'https://aos-events.com/api/california_itc_scores'
TEXAS_URL         = 'https://aos-events.com/api/texas_itc_scores'
BCP_API_KEY       = os.getenv("BCP_API_KEY")
CLIENT_ID         = os.getenv("BCP_CLIENT_ID")
BASE_EVENT_URL    = 'https://newprod-api.bestcoastpairings.com/v1/events'
ITC_LEAGUE_ID     = 'vldWOTsjXggj'
ITC_REGION_ID     = '61vXu5vli4'
PHOTO_DIR = Path(__file__).parent / "photos"
SCIONPHOTO_DIR = Path(__file__).parent / "scionphotos"
openai.api_key    = os.getenv("OPENAI_API_KEY")
GEMINI_KEY        = os.getenv("GEMINI_API_KEY")


# League IDs for specific years (used by playerwr command)
LEAGUE_YEARS = {
    2025: 'vldWOTsjXggj',
    2024: 'PHGDLQY41V',
    2023: '2F20J0M34C',
    2022: '23qDprPABN',
    #2021: 'HyXfJt4g6P',
}

# Shared settings
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Create Bot instances
leaderboard_bot = commands.Bot(command_prefix='!', intents=intents, description="Cali Masters Leaderboard Bot")
aos_bot         = commands.Bot(command_prefix='!', intents=intents, description="AoS Win Rates Bot")
tex_bot         = commands.Bot(command_prefix='!', intents=intents, description="Texas Masters Leaderboard Bot")

# Time filter display labels
time_labels = {
    'all': 'Since 2025/01/01',
    'recent': 'Last 60 days',
    'battlescroll': 'Since last battlescroll'
}

# Emoji mapping for factions
EMOJI_MAP = {
    'Flesh-eater Courts': '🦴',
    'Idoneth Deepkin': '🌊',
    'Lumineth Realm-lords': '💡',
    'Disciples of Tzeentch': '🔮',
    'Sons of Behemat': '🦶',
    'Sylvaneth': '🌳',
    'Seraphon': '🦎',
    'Soulblight Gravelords': '🪦',
    'Blades of Khorne': '🔥',
    'Stormcast Eternals': '⚡',
    'Hedonites of Slaanesh': '🎵 ',
    'Cities of Sigmar': '🏙️',
    'Daughters of Khaine': '🐍',
    'Ogor Mawtribes': '🍖',
    'Slaves to Darkness': '⛓️',
    'Maggotkin of Nurgle': '🪱',
    'Ossiarch Bonereapers': '💀',
    'Ironjawz': '🐖',
    'Kharadron Overlords': '⚓',
    'Nighthaunt': '👻',
    'Skaven': '🐀',
    'Kruleboyz': '👺',
    'Fyreslayers': '🪓',
    'Gloomspite Gitz': '🍄'
}

# Common helpers
def random_acronym(letters: str) -> str:
    COMMON_WORDS = top_n_list("en", 20000)
    WORDS_BY_LETTER = {ch: [w.capitalize() for w in COMMON_WORDS if w.startswith(ch)] for ch in "abcdefghijklmnopqrstuvwxyz"}
    parts = []
    for ch in letters.lower():
        bucket = WORDS_BY_LETTER.get(ch)
        parts.append(random.choice(bucket) if bucket else ch.upper())
    return " ".join(parts)

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()

async def fetch_winrates(time_filter='all'):
    base = API_URL.rstrip('/')
    url = f"{base if base.lower().endswith('winrates') else base + '/api/winrates'}?time={time_filter}"
    return await fetch_json(url)

async def fetch_enhancement(time_filter='all', rounds_filter='all'):
    base = API_URL.rstrip('/')
    url = f"{base}/api/enhancement_winrates?time={time_filter}&rounds={rounds_filter}"
    return await fetch_json(url)

# ========== Leaderboard Bot Commands ==========

@leaderboard_bot.command(name='top8', help='Show the current Cali Masters top 8')
async def top8(ctx):
    data = await fetch_json(CALI_URL)
    top = data[:8]
    if not top:
        return await ctx.send("No data available.")
    lines = ["**🏆 Cali Masters Top 8 🏆**"]
    for i, rec in enumerate(top, 1):
        name = f"{rec['first_name']} {rec['last_name']}"
        lines.append(f"{i}. **{name}** — {rec['top4_sum']} pts")
    lines.append("")
    lines.append("Full table: https://aos-events.com/calimasters")
    await ctx.send("\n".join(lines))

@leaderboard_bot.command(name='rank', help='Show rank, score, and event count for a player')
async def rank(ctx, *, query: str):
    key = query.strip().lower()
    if key == 'corsairs':
        return await ctx.send('utter trash')
    if key == 'tsd':
        return await ctx.send(f"`TSD` stands for: **{random_acronym('TSD')}**")
    if key == 'ligmar':
        return await ctx.send('BALLS!')
    if key == 'jessica':
        return await ctx.send('☠️ Best Corsair ☠️')

    data = await fetch_json(CALI_URL)
    pattern = re.compile(r'^event_(\d+)_id$')
    matches = [(i, rec) for i, rec in enumerate(data, 1)
               if key in (f"{rec['first_name']} {rec['last_name']}".lower(),
                          rec['first_name'].lower(),
                          rec['last_name'].lower())]
    if not matches:
        return await ctx.send(f"No player found matching `{query}`.")
    lines = []
    for rank_pos, rec in matches:
        total = sum(1 for k, v in rec.items() if pattern.match(k) and v)
        cnt = min(total, 4)
        lines.append(f"#{rank_pos} **{rec['first_name']} {rec['last_name']}** — {rec['top4_sum']} pts ({cnt} of 4)")
    await ctx.send("\n".join(lines))


# ========== Texas Bot Commands ==========

@tex_bot.command(name='top8', help='Show the current Texas Masters top 8')
async def top8(ctx):
    data = await fetch_json(TEXAS_URL)
    top = data[:8]
    if not top:
        return await ctx.send("No data available.")
    lines = ["**🏆 Texas Masters Top 8 🏆**"]
    for i, rec in enumerate(top, 1):
        name = f"{rec['first_name']} {rec['last_name']}"
        lines.append(f"{i}. **{name}** — {rec['top5_sum']} pts")
    lines.append("")
    lines.append("Full table: https://aos-events.com/texmasters")
    await ctx.send("\n".join(lines))

@tex_bot.command(name='rank', help='Show rank, score, and event count for a player')
async def rank(ctx, *, query: str):
    key = query.strip().lower()
    if key == 'corsairs':
        return await ctx.send('utter trash')
    if key == 'tsd':
        return await ctx.send(f"`TSD` stands for: **{random_acronym('TSD')}**")
    if key == 'ligmar':
        return await ctx.send('BALLS!')
    if key == 'jessica':
        return await ctx.send('☠️ Best Corsair ☠️')

    data = await fetch_json(TEXAS_URL)
    pattern = re.compile(r'^event_(\d+)_id$')
    matches = [(i, rec) for i, rec in enumerate(data, 1)
               if key in (f"{rec['first_name']} {rec['last_name']}".lower(),
                          rec['first_name'].lower(),
                          rec['last_name'].lower())]
    if not matches:
        return await ctx.send(f"No player found matching `{query}`.")
    lines = []
    for rank_pos, rec in matches:
        total = sum(1 for k, v in rec.items() if pattern.match(k) and v)
        cnt = min(total, 5)
        lines.append(f"#{rank_pos} **{rec['first_name']} {rec['last_name']}** — {rec['top5_sum']} pts ({cnt} of 4)")
    await ctx.send("\n".join(lines))

# ========== AoS Win Rates Bot Commands ==========

TIME_FILTERS     = ['all', 'recent', 'battlescroll']
EXCLUDE_FACTIONS = ['Beasts of Chaos', 'Bonesplitterz']
ALIAS_MAP        = {
    'fec': 'Flesh-eater Courts', 'flesh-eater courts': 'Flesh-eater Courts',
    'idk': 'Idoneth Deepkin', 'idoneth': 'Idoneth Deepkin', 'deepkin': 'Idoneth Deepkin', 'fish': 'Idoneth Deepkin',
    'lrl': 'Lumineth Realm-lords', 'lumineth': 'Lumineth Realm-lords', 'realm-lords': 'Lumineth Realm-lords',
    'dot': 'Disciples of Tzeentch', 'tzeentch': 'Disciples of Tzeentch',
    'sons': 'Sons of Behemat', 'sob': 'Sons of Behemat', 'giants': 'Sons of Behemat',
    'trees': 'Sylvaneth', 'sylvaneth': 'Sylvaneth',
    'sera': 'Seraphon', 'lizards': 'Seraphon', 'seraphon': 'Seraphon',
    'sbgl': 'Soulblight Gravelords', 'soulblight': 'Soulblight Gravelords', 'vampires': 'Soulblight Gravelords',
    'bok': 'Blades of Khorne', 'khorne': 'Blades of Khorne',
    'sce': 'Stormcast Eternals', 'stormcast': 'Stormcast Eternals',
    'hos': 'Hedonites of Slaanesh', 'slaanesh': 'Hedonites of Slaanesh',
    'cos': 'Cities of Sigmar', 'cities': 'Cities of Sigmar',
    'dok': 'Daughters of Khaine', 'daughters': 'Daughters of Khaine',
    'ogors': 'Ogor Mawtribes', 'mawtribes': 'Ogor Mawtribes',
    'std': 'Slaves to Darkness', 'slaves': 'Slaves to Darkness', 's2d': 'Slaves to Darkness',
    'mon': 'Maggotkin of Nurgle', 'nurgle': 'Maggotkin of Nurgle',
    'obr': 'Ossiarch Bonereapers', 'ossiarch bonereapers': 'Ossiarch Bonereapers',
    'ij': 'Ironjawz', 'ironjawz': 'Ironjawz',
    'ko': 'Kharadron Overlords', 'kharadron overlords': 'Kharadron Overlords',
    'nh': 'Nighthaunt', 'ghosts': 'Nighthaunt',
    'rats': 'Skaven', 'skaven': 'Skaven',
    'kb': 'Kruleboyz', 'kruleboyz': 'Kruleboyz',
    'fs': 'Fyreslayers', 'fyreslayers': 'Fyreslayers',
    'gitz': 'Gloomspite Gitz', 'gloomspite gitz': 'Gloomspite Gitz'
}
for full in set(ALIAS_MAP.values()):
    ALIAS_MAP[full.lower()] = full

def get_shortest_alias(full_name: str) -> str:
    full_lower = full_name.lower()
    candidates = [
        alias for alias, canon in ALIAS_MAP.items()
        if canon.lower() == full_lower and alias.lower() != full_lower
    ]
    if candidates:
        return min(candidates, key=len).upper()
    return full_name

@aos_bot.command(name='winrates', aliases=['winrate'], help='!winrates [time]|[faction_alias] [time]')
async def winrates_cmd(ctx, arg: str = 'all', maybe_time: str = None):
    arg_lower = arg.lower()
    if arg_lower in TIME_FILTERS:
        await send_full_winrates(ctx, arg_lower)
    elif arg_lower in ALIAS_MAP:
        tf = maybe_time.lower() if maybe_time and maybe_time.lower() in TIME_FILTERS else 'all'
        await send_single(ctx, arg_lower, tf)
    else:
        await ctx.send(f"Invalid argument '{arg}'. Use a time ({', '.join(TIME_FILTERS)}) or alias.")

@aos_bot.command(name='artefacts', aliases=['artefact','artifact','artifacts'],
                 help='Get artifact winrates for a faction. Usage: !artefacts <faction_alias> [time]')
async def artefacts_cmd(ctx, faction_alias: str, time_filter: str = 'all'):
    tf = time_filter.lower()
    if tf not in TIME_FILTERS:
        return await ctx.send(f"Invalid time filter. Choose from: {', '.join(TIME_FILTERS)}")
    canonical = ALIAS_MAP.get(faction_alias.lower())
    if not canonical:
        return await ctx.send(f"Unknown faction '{faction_alias}'.")
    data = await fetch_enhancement(tf)
    items = [i for i in data.get('artifacts', []) if i.get('faction') == canonical]
    if not items:
        return await ctx.send(f"No artifact data for {canonical}.")
    label = time_labels.get(tf, tf)
    lines = [f"🏹Artifact Win Rates for {canonical} ({label})🏹"]
    for itm in items:
        lines.append(f"{itm['artifact']}: {itm['wins']}/{itm['games']} wins ({itm['win_rate_pct']:.2f}%)")
    lines += ['', 'Source: https://aos-events.com']
    await send_lines(ctx, lines)

@aos_bot.command(name='traits', aliases=['trait'],
                 help='Get trait winrates for a faction. Usage: !traits <faction_alias> [time]')
async def traits_cmd(ctx, faction_alias: str, time_filter: str = 'all'):
    tf = time_filter.lower()
    if tf not in TIME_FILTERS:
        return await ctx.send(f"Invalid time filter. Choose from: {', '.join(TIME_FILTERS)}")
    canonical = ALIAS_MAP.get(faction_alias.lower())
    if not canonical:
        return await ctx.send(f"Unknown faction '{faction_alias}'.")
    data = await fetch_enhancement(tf)
    items = [i for i in data.get('traits', []) if i.get('faction') == canonical]
    if not items:
        return await ctx.send(f"No trait data for {canonical}.")
    label = time_labels.get(tf, tf)
    lines = [f"🏹Trait Win Rates for {canonical} ({label})🏹"]
    for itm in items:
        lines.append(f"{itm['trait']}: {itm['wins']}/{itm['games']} wins ({itm['win_rate_pct']:.2f}%)")
    lines += ['', 'Source: https://aos-events.com']
    await send_lines(ctx, lines)

@aos_bot.command(name='formations', aliases=['formation'],
                 help='Get formation winrates for a faction. Usage: !formations <faction_alias> [time]')
async def formations_cmd(ctx, faction_alias: str, time_filter: str = 'all'):
    tf = time_filter.lower()
    if tf not in TIME_FILTERS:
        return await ctx.send(f"Invalid time filter. Choose from: {', '.join(TIME_FILTERS)}")
    canonical = ALIAS_MAP.get(faction_alias.lower())
    if not canonical:
        return await ctx.send(f"Unknown faction '{faction_alias}'.")
    data = await fetch_enhancement(tf)
    items = [i for i in data.get('formations', []) if i.get('faction') == canonical]
    if not items:
        return await ctx.send(f"No formation data for {canonical}.")
    label = time_labels.get(tf, tf)
    lines = [f"🏹 Formation Win Rates for {canonical} ({label})🏹"]
    for itm in items:
        lines.append(f"{itm['formation']}: {itm['wins']}/{itm['games']} wins ({itm['win_rate_pct']:.2f}%)")
    lines += ['', 'Source: https://aos-events.com']
    await send_lines(ctx, lines)

@aos_bot.command(name='hof', help='List Hall of Fame players (5+ wins) for a faction. Usage: !hof <faction_alias>')
async def hof(ctx, *, alias: str):
    lookup = alias.strip('"').lower()
    if lookup == "legions of nagash":
        return await ctx.send(
            "Legions of Nagash are no longer legal... however, Gareth Thomas was the last winner of ITC LoN."
        )
    canonical = ALIAS_MAP.get(lookup)
    if not canonical:
        return await ctx.send(f"Unknown faction '{alias}'. Available aliases: {', '.join(ALIAS_MAP.keys())}")
    url = f"{API_URL.rstrip('/')}/api/five_win_players"
    data = await fetch_json(url)
    entries = [e for e in data if e.get('faction') == canonical]
    if not entries:
        return await ctx.send(f"No Hall of Fame entries for {canonical}.")
    lines = [f"🏆 Hall of Fame for {canonical} 🏆"]
    for e in entries:
        date_str = e.get('event_date', '').split('T')[0]
        lines.append(f"{date_str} - {e.get('player_name')} at {e.get('event_name')} (Wins: {e.get('wins')})")
    lines += ['', 'For lists and more info: https://aos-events.com/faction_stats#hof']
    await send_lines(ctx, lines)

@aos_bot.command(name='units', help='List unit win-rates for a faction. Usage: !units <faction_alias> [time_filter]')
async def units_cmd(ctx, alias: str, time_filter: str = 'all'):
    canonical = ALIAS_MAP.get(alias.lower())
    if not canonical:
        return await ctx.send(f"Unknown faction '{alias}'.")
    tf = time_filter.lower()
    if tf not in TIME_FILTERS:
        return await ctx.send(f"Invalid time filter '{time_filter}'.")
    data = await fetch_json(f"{API_URL.rstrip('/')}/api/winrates?time={tf}")
    units = [u for u in data.get('units', []) if u.get('faction') == canonical]
    if not units:
        return await ctx.send(f"No unit data for {canonical} ({tf}).")
    units_sorted = sorted(units, key=lambda u: (u['wins']/u['games']) if u['games'] else 0, reverse=True)
    label = time_labels.get(tf, tf)
    lines = [f"🏹 Unit Win-Rates for {canonical} ({label}) 🏹"]
    for u in units_sorted:
        wins, games = u['wins'], u['games']
        pct = (wins/games*100) if games else 0
        lines.append(f"{u['name']}: {wins}/{games} wins ({pct:.2f}%)")
    lines += ['', 'Full stats at: https://aos-events.com/faction_stats#units']
    await send_lines(ctx, lines)

@aos_bot.command(name='popularity', aliases=['pop'],
                 help='List popularity stats. Usage: !pop [factions|manifestations|drops] [time_filter]')
async def popularity_cmd(ctx, arg: str = 'factions', maybe_time: str = 'all'):
    valid_cats   = ['factions', 'manifestations', 'drops']
    time_filters = TIME_FILTERS
    arg_l = arg.lower()
    if arg_l in time_filters:
        category, tf = 'factions', arg_l
    elif arg_l in valid_cats:
        category = arg_l
        tf = maybe_time.lower() if maybe_time.lower() in time_filters else 'all'
    else:
        return await ctx.send(
            f"Invalid category or time filter '{arg}'."
        )
    data = await fetch_json(f"{API_URL.rstrip('/')}/api/popularity?time={tf}")
    items = data.get(category, [])
    if not items:
        return await ctx.send(f"No popularity data for {category} ({tf}).")
    total_games = sum(it['games'] for it in items)
    label = time_labels.get(tf, tf)
    lines = [f"📊 Popularity for {category.capitalize()} ({label}):"]
    for it in sorted(items, key=lambda x: x['games'], reverse=True):
        pct = (it['games']/total_games*100) if total_games else 0
        prefix = EMOJI_MAP.get(it['name'], '') + ' ' if category=='factions' else ''
        lines.append(f"{prefix}{it['name']}: {it['games']} games ({pct:.2f}%)")
    lines += ['', 'More info: https://aos-events.com/faction_stats#popularity']
    await send_lines(ctx, lines)

def extract_players(raw: dict):
    if isinstance(raw, dict):
        if 'active' in raw and isinstance(raw['active'], list):
            return raw['active']
        if 'data' in raw and isinstance(raw['data'], list):
            return raw['data']
    return []

def _search_matches(events, query):
    """
    Return all events whose name, address, or city contains the query.
    """
    q = query.lower()
    out = []
    for e in events:
        if e.get("teamEvent") or e.get("doublesEvent"):
            continue
        name = (e.get("name") or "").lower()
        addr = (e.get("formatted_address") or "").lower()
        city = (e.get("city") or "").lower()
        if q in name or q in addr or q in city:
            out.append(e)
    return out


async def send_standings_table(ctx, ev_name, ev_id, players, metric_names):
    header_fields = ["Place", "Name"] + metric_names
    header_line   = " | ".join(header_fields)
    divider       = "-" * len(header_line)
    lines = [f"Standings for {ev_name} ({ev_id}):", header_line, divider]
    for p in players:
        placing = p.get("placing", "")
        user    = p.get("user", {})
        name    = f"{user.get('firstName','')} {user.get('lastName','')}".strip()
        metric_map = {m['name']: m['value'] for m in p.get('metrics', [])}
        row = [str(placing), name] + [str(metric_map.get(m, "")) for m in metric_names]
        lines.append(" | ".join(row))
    await send_lines(ctx, lines)

async def do_standings_full(ctx, ev):
    ev_name, ev_id = ev["name"], ev["id"]
    headers = {'Accept':'application/json','x-api-key':BCP_API_KEY,'client-id':CLIENT_ID,'User-Agent':'AoSBot'}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_EVENT_URL}/{ev_id}/players",
                               params={"placings":"true","limit":500},
                               headers=headers) as presp:
            presp.raise_for_status(); raw = await presp.json()
    players = extract_players(raw)
    if not players:
        return await ctx.send(f":warning: No players for `{ev_name}` ({ev_id}).")
    metric_names = [m["name"] for m in players[0].get("metrics",[])]
    await send_standings_table(ctx, ev_name, ev_id, players, metric_names)
    await ctx.send(f"View full placings: https://www.bestcoastpairings.com/event/{ev_id}?active_tab=placings")

async def do_standings_slim(ctx, ev):
    ev_name, ev_id = ev["name"], ev["id"]
    headers = {'Accept':'application/json','x-api-key':BCP_API_KEY,'client-id':CLIENT_ID,'User-Agent':'AoSBot'}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_EVENT_URL}/{ev_id}/players",
                               params={"placings":"true","limit":500},
                               headers=headers) as presp:
            presp.raise_for_status(); raw = await presp.json()
    players = extract_players(raw)
    if not players:
        return await ctx.send(f":warning: No players for `{ev_name}` ({ev_id}).")
    first_metrics = [m["name"] for m in players[0].get("metrics",[])]
    if "Wins" not in first_metrics:
        return await ctx.send(f":warning: No “Wins” metric in `{ev_name}` ({ev_id}).")
    header = "Place | Faction | Name                     | Wins"
    divider = "-" * len(header)
    lines = [f"Standings for {ev_name} ({ev_id}):", header, divider]
    for p in players:
        placing = p["placing"]
        full_faction = p.get("faction",{}).get("name","")
        faction_alias = get_shortest_alias(full_faction)
        user = p["user"]
        name = f"{user['firstName']} {user['lastName']}"
        metric_map = {m["name"]: m["value"] for m in p["metrics"]}
        wins = metric_map.get("Wins", "")
        lines.append(f"{placing:<5} | {faction_alias:<7} | {name:<24} | {wins:^4}")
    await send_lines(ctx, lines)
    await ctx.send(f"View full placings: https://www.bestcoastpairings.com/event/{ev_id}?active_tab=placings")

@aos_bot.command(name='standings', help='Current standings at event')
async def standings_slim_cmd(ctx, *, args: str):
    parts = args.split(maxsplit=1)
    requested_round = None
    query = args

    if len(parts) == 2 and parts[0].isdigit():
        rnd = int(parts[0])
        if 1 <= rnd <= 8:
            requested_round = rnd
            query = parts[1]
        else:
            return await ctx.send(":warning: Round must be 1–8.")

    if len(query.strip()) < 4:
        return await ctx.send(":warning: Please use at least 4 characters for your search.")

    today    = datetime.utcnow().date() + timedelta(days=3)
    week_ago = today - timedelta(days=7)
    params = {
        "limit":        100,
        "sortAscending":"true",
        "sortKey":      "eventDate",
        "startDate":    week_ago.isoformat(),
        "endDate":      today.isoformat(),
        "gameType":     "4",
    }
    headers = {
        "Accept":     "application/json",
        "x-api-key":  BCP_API_KEY,
        "client-id":  CLIENT_ID,
        "User-Agent": "AoSBot/1.0",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_EVENT_URL, params=params, headers=headers) as resp:
            resp.raise_for_status()
            events = (await resp.json()).get("data", [])

    matches = _search_matches(events, query)

    if not matches:
        return await ctx.send(f":mag: No AoS events this week matching `{query}`.")
    if len(matches) == 1:
        return await do_standings_slim(ctx, matches[0])
    await ctx.send("Multiple events found—please pick one:", view=StandingsView(matches, slim=True, ctx=ctx))

@aos_bot.command(name='standingsfull', help='Full standings info')
async def standings_full_cmd(ctx, *, args: str):
    parts = args.split(maxsplit=1)
    requested_round = None
    query = args

    if len(parts) == 2 and parts[0].isdigit():
        rnd = int(parts[0])
        if 1 <= rnd <= 8:
            requested_round = rnd
            query = parts[1]
        else:
            return await ctx.send(":warning: Round must be 1–8.")

    if len(query.strip()) < 4:
        return await ctx.send(":warning: Please use at least 4 characters for your search.")

    today    = datetime.utcnow().date() + timedelta(days=3)
    week_ago = today - timedelta(days=7)
    params = {
        "limit":        100,
        "sortAscending":"true",
        "sortKey":      "eventDate",
        "startDate":    week_ago.isoformat(),
        "endDate":      today.isoformat(),
        "gameType":     "4",
    }
    headers = {
        "Accept":     "application/json",
        "x-api-key":  BCP_API_KEY,
        "client-id":  CLIENT_ID,
        "User-Agent": "AoSBot/1.0",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_EVENT_URL, params=params, headers=headers) as resp:
            resp.raise_for_status()
            events = (await resp.json()).get("data", [])

    matches = _search_matches(events, query)
    if not matches:
        return await ctx.send(f":mag: No AoS events this week matching `{query}`.")
    if len(matches) == 1:
        return await do_standings_full(ctx, matches[0])
    await ctx.send("Multiple events found—please pick one:", view=StandingsView(matches, slim=False, ctx=ctx))

# ─── Pairings Command ─────────────────────────────────────────────────────────

class PairingsSelect(discord.ui.Select):
    def __init__(self, events, ctx, first_names: set[str] | None = None, requested_round: int | None = None):
        options = []
        for e in events:
            loc = e.get("formatted_address", e.get("city", ""))
            label = f"{e['name']} ({loc})"
            if len(label) > 100:
                label = label[:97] + "…"
            options.append(discord.SelectOption(label=label, value=e["id"]))
        super().__init__(placeholder="Select an event…", min_values=1, max_values=1, options=options)
        self.events = {e["id"]: e for e in events}
        self.ctx    = ctx
        self.first_names = first_names
        self.requested_round = requested_round        

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        ev = self.events[self.values[0]]
        await do_pairings(self.ctx, ev, requested_round=self.requested_round, first_names=self.first_names)
        self.view.stop()

class PairingsView(discord.ui.View):
    def __init__(self, events, ctx, first_names: set[str] | None = None, requested_round: int | None = None):
        super().__init__(timeout=60)
        self.add_item(PairingsSelect(events, ctx, first_names=first_names, requested_round=requested_round))

async def do_pairings(ctx, ev, requested_round: int | None = None, first_names: set[str] | None = None):
    ev_name, ev_id = ev["name"], ev["id"]
    headers = {
        "Accept":      "application/json",
        "x-api-key":   BCP_API_KEY,
        "client-id":   CLIENT_ID,
        "User-Agent":  "AoSBot/1.0",
    }

    pairings = []
    chosen_round = requested_round

    async with aiohttp.ClientSession() as session:
        rounds = [requested_round] if requested_round else list(range(8, 0, -1))
        for rnd in rounds:
            params = {"eventId": ev_id, "round": rnd, "pairingType": "Pairing"}
            async with session.get(f"{BASE_EVENT_URL}/{ev_id}/pairings", params=params, headers=headers) as presp:
                presp.raise_for_status()
                raw = await presp.json()

            active = raw.get("active") or raw.get("data", [])
            if active:
                pairings = active
                chosen_round = rnd
                break

    if not pairings:
        if requested_round:
            return await ctx.send(f":warning: No pairings found for `{ev_name}` ({ev_id}) in round {requested_round}.")
        return await ctx.send(f":warning: No pairings found for `{ev_name}` ({ev_id}).")

    # Optional first-name filter
    if first_names:
        want = {n.strip().lower() for n in first_names if n.strip()}
        def hit(p):
            u1 = (p.get("player1") or {}).get("user") or {}
            if (u1.get("firstName") or "").lower() in want:
                return True
            u2 = (p.get("player2") or {}).get("user") or {}
            return (u2.get("firstName") or "").lower() in want
        pairings = [p for p in pairings if hit(p)]
        if not pairings:
            return await ctx.send(f":mag: No pairings in round {chosen_round} for requested names at `{ev_name}`.")

    header = f"Pairings for {ev_name} ({ev_id}) — Round {chosen_round}" + (" [filtered]" if first_names else "")
    cols    = "Player 1 Name         | Pts | Player 2 Name         | Pts"
    divider = "-" * len(cols)

    lines = [header, cols, divider]
    for p in pairings:
        u1 = p["player1"]["user"]; name1 = f"{u1['firstName']} {u1['lastName']}"
        pts1 = p.get("player1Game", {}).get("points", "")
        if p.get("player2"):
            u2 = p["player2"]["user"]; name2 = f"{u2['firstName']} {u2['lastName']}"
            pts2 = p.get("player2Game", {}).get("points", "")
        else:
            name2, pts2 = "(bye)", ""
        lines.append(f"{name1:<22} | {pts1:^3} | {name2:<22} | {pts2:^3}")

    await send_lines(ctx, lines)
    if not first_names:
        await ctx.send(f"View full pairings: https://www.bestcoastpairings.com/event/{ev_id}?active_tab=pairings")


@aos_bot.command(
    name="pairings",
    help="!pairings [round] <event_search> OR !pairings [round] <event_search> | <first names>"
)
async def pairings_cmd(ctx, *, args: str):
    requested_round: int | None = None
    first_names: set[str] | None = None
    query = args.strip()

    # optional round
    parts = query.split(maxsplit=1)
    if len(parts) == 2 and parts[0].isdigit():
        rnd = int(parts[0])
        if 1 <= rnd <= 8:
            requested_round = rnd
            query = parts[1]
        else:
            return await ctx.send(":warning: Round must be between 1–8.")

    # optional name filter
    if "|" in query:
        event_part, names_part = query.split("|", 1)
        query = event_part.strip()
        raw_names = [n for n in re.split(r"[,\s]+", names_part.strip()) if n]
        if raw_names:
            first_names = {n.lower() for n in raw_names}

    if len(query) < 4:
        return await ctx.send(":warning: Please use at least 4 characters for your search.")

    # fetch events (newprod + aiohttp)
    today    = datetime.utcnow().date() + timedelta(days=3)
    week_ago = today - timedelta(days=7)
    params = {
        "limit":        100,
        "sortAscending":"true",
        "sortKey":      "eventDate",
        "startDate":    week_ago.isoformat(),
        "endDate":      today.isoformat(),
        "gameType":     "4",
    }
    headers = {
        "Accept":     "application/json",
        "x-api-key":  BCP_API_KEY,
        "client-id":  CLIENT_ID,
        "User-Agent": "AoSBot/1.0",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_EVENT_URL, params=params, headers=headers) as resp:
            resp.raise_for_status()
            events = (await resp.json()).get("data", [])

    matches = _search_matches(events, query)
    if not matches:
        return await ctx.send(f":mag: No AoS events this week matching `{query}`.")

    if len(matches) == 1:
        return await do_pairings(ctx, matches[0], requested_round=requested_round, first_names=first_names)

    await ctx.send(
        "Multiple events found—please pick one:",
        view=PairingsView(matches, ctx, first_names=first_names, requested_round=requested_round),
    )











@aos_bot.command(name='itcrank', aliases=['crankit'], help='Show ITC placing and points for a player (via BCP API)')
async def itcrank_cmd(ctx, *, name: str):
    name = name.strip()
    if name=='e' or name=='E':
        await ctx.send("Dirty creature")
        name = "e pryor"
    if len(name) < 3:
        return await ctx.send("Please provide at least 3 characters for the name search.")

    headers = {
        'Accept':       'application/json',
        'x-api-key':    BCP_API_KEY,
        'client-id':    CLIENT_ID,
        'User-Agent':   'AoS-ITCCrank-Bot',
    }
    params = {
        "limit":         2000,
        "placingsType":  "player",
        "leagueId":      ITC_LEAGUE_ID,
        "regionId":      ITC_REGION_ID,
        "sortAscending": "false"
    }

    # fetch full top-N then filter by name substring
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            f"{BASE_EVENT_URL.replace('/events','')}/placings",
            params=params,
            headers=headers
        )
        resp.raise_for_status()
        data = (await resp.json()).get("data", [])

    key = name.lower()
    matches = [
        e for e in data
        if key in f"{e['user'].get('firstName','')} {e['user'].get('lastName','')}".lower()
    ]
    if not matches:
        return await ctx.send(f"No ITC placings found for **{name}**.")

    lines = [f"**ITC Placings for “{name}”**"]
    for rec in matches:
        fn      = rec['user'].get('firstName','')
        ln      = rec['user'].get('lastName','')
        placing = rec.get('placing')
        pts     = rec.get('ITCPoints', rec.get('totalPoints', 0))
        lines.append(f"{fn} {ln} — Placing: {placing}, Points: {pts:.2f}")

    await send_lines(ctx, lines)


# ─── WHO IS BETTER ────────────────────────────────────────────────────────────
@aos_bot.command(
    name='whoisbetter',
    help='Compare two players by ITC placing via BCP. Usage: !whoisbetter <name1> <name2> OR !whoisbetter <name1> or <name2>'
)
async def whoisbetter_cmd(ctx, *, query: str):
    # parse names
    parts = re.split(r'\s+or\s+', query, flags=re.IGNORECASE)
    if len(parts) == 2:
        name1, name2 = parts[0].strip(), parts[1].strip()
    else:
        toks = query.split()
        if len(toks) < 4:
            return await ctx.send("Usage: `!whoisbetter <first1> <last1> <first2> <last2>` or `!whoisbetter <name1> or <name2>`")
        name1 = f"{toks[0]} {toks[1]}"
        name2 = f"{toks[2]} {toks[3]}"

    # special jokes
    if name1.lower()=="gareth thomas" or name2.lower()=="gareth thomas":
        return await ctx.send("Gareth Thomas is morally and intellectually superior")

    # helper to fetch & filter
    async def fetch_for(name):
        headers = {
            'Accept':'application/json',
            'x-api-key':BCP_API_KEY,
            'client-id':CLIENT_ID,
            'User-Agent':'AoS-WhoIsBetter-Bot',
        }
        params = {
            "limit":         2000,
            "placingsType":  "player",
            "leagueId":      ITC_LEAGUE_ID,
            "regionId":      ITC_REGION_ID,
            "sortAscending": "false"
        }
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"{BASE_EVENT_URL.replace('/events','')}/placings", params=params, headers=headers)
            r.raise_for_status()
            raw = (await r.json()).get("data", [])
        key = name.lower()
        return [e for e in raw if key in f"{e['user'].get('firstName','')} {e['user'].get('lastName','')}".lower()]

    try:
        data1 = await fetch_for(name1)
        data2 = await fetch_for(name2)
    except Exception as e:
        return await ctx.send(f"Error fetching ITC data: {e}")

    def best(data):
        return None if not data else min(e.get('placing', float('inf')) for e in data)

    best1, best2 = best(data1), best(data2)

    if best1 is None and best2 is None:
        return await ctx.send(f"No ITC data for either {name1} or {name2}.")
    if best1 is None:
        return await ctx.send(f"No ITC data for {name1}, but {name2} has best placing #{best2}. So {name2} is better!")
    if best2 is None:
        return await ctx.send(f"No ITC data for {name2}, but {name1} has best placing #{best1}. So {name1} is better!")
    if best1 < best2:
        return await ctx.send(f"{name1} (best placing #{best1}) is better than {name2} (best placing #{best2})!")
    if best2 < best1:
        return await ctx.send(f"{name2} (best placing #{best2}) is better than {name1} (best placing #{best1})!")
    return await ctx.send(f"Both {name1} and {name2} share the same best placing of #{best1}! They're tied!")


@aos_bot.command(name='itcstandings', help='Show top 10 ITC standings, optionally for a faction: !itcstandings [faction_alias]')
async def itcstandings_cmd(ctx, faction: str = None):
    headers = {
        'Accept':       'application/json',
        'x-api-key':    BCP_API_KEY,
        'client-id':    CLIENT_ID,
        'User-Agent':   'AoS-ITCStandings-Bot',
    }

    async with aiohttp.ClientSession() as session:
        # decide which params to use
        if faction:
            # 1) resolve alias -> canonical
            canon = ALIAS_MAP.get(faction.lower())
            if not canon:
                return await ctx.send(f":warning: Unknown faction alias `{faction}`.")
            # 2) fetch armies to find the matching ID
            resp = await session.get(
                "https://newprod-api.bestcoastpairings.com/v1/armies",
                params={"gameType": 4},
                headers=headers
            )
            resp.raise_for_status()
            armies = (await resp.json()).get("data", [])
            army = next((
                a for a in armies
                if a["name"].lower() == canon.lower()
                or a.get("gwFactionName","").lower() == canon.lower()
            ), None)
            if not army:
                return await ctx.send(f":warning: Couldn’t find army ID for `{canon}`.")
            params = {
                "limit":         10,
                "placingsType":  "army",
                "leagueId":      ITC_LEAGUE_ID,
                "regionId":      ITC_REGION_ID,
                "sortAscending": "false",
                "armyId":        army["id"]
            }
        else:
            # overall top-10 players
            params = {
                "limit":         10,
                "placingsType":  "player",
                "leagueId":      ITC_LEAGUE_ID,
                "regionId":      ITC_REGION_ID,
                "sortAscending": "false"
            }

        # 3) fetch the placings
        resp = await session.get(
            "https://newprod-api.bestcoastpairings.com/v1/placings",
            params=params,
            headers=headers
        )
        resp.raise_for_status()
        entries = (await resp.json()).get("data", [])

    if not entries:
        return await ctx.send(":warning: No ITC standings found.")

    # 4) build the table
    header = "Placing | Name                     | Points"
    divider = "-" * len(header)
    lines = [header, divider]

    for e in entries:
        placing = e.get("placing", "")
        user = e.get("user", {})
        name = f"{user.get('firstName','')} {user.get('lastName','')}".strip()
        pts = e.get("ITCPoints", e.get("totalPoints", 0))
        lines.append(f"{placing:<7} | {name:<24} | {pts:>7.2f}")

    # 5) send in a single code block (it’s short)
    await ctx.send("```" + "\n".join(lines) + "```")

import re

def expected_damage(
    num_attacks: int,
    to_hit: int,
    to_wound: int,
    rend: int,
    save: int,
    damage,               # int or 'd3' or 'd6'
    crit_mortal: bool = False,
    crit_auto_wound: bool = False,
    crit_extra: bool = False,
    crit_threshold: int = 6
) -> float:
    """
    Compute expected AoS damage, with adjustable crit threshold.
    
    crit_threshold: rolls >= this AND >= to_hit are “crits”
    crit_mortal: each crit deals mortal wounds = damage (no wound/save)
    crit_auto_wound: each crit auto-wounds (skip to-wound, roll save)
    crit_extra: each crit also grants one extra normal hit
    """
    # base probs
    p_hit = max(0.0, min((7 - to_hit) / 6.0, 1.0))
    # crit only if roll >= both to_hit and crit_threshold
    eff_thresh = max(to_hit, crit_threshold)
    p_crit = max(0.0, min((7 - eff_thresh) / 6.0, 1.0))
    p_noncrit = max(0.0, p_hit - p_crit)

    p_wound = max(0.0, min((7 - to_wound) / 6.0, 1.0))
    eff_save = save + rend
    if eff_save < 2:
        p_save = 5/6
    elif eff_save <= 6:
        p_save = (7 - eff_save) / 6.0
    else:
        p_save = 0.0

    # mean damage per unsaved wound
    if isinstance(damage, str):
        if damage.lower() == 'd3':
            exp_dmg = 2.0
        elif damage.lower() == 'd6':
            exp_dmg = 3.5
        else:
            raise ValueError("damage must be int or 'd3' or 'd6'")
    else:
        exp_dmg = float(damage)

    # normal non-crit hits
    e_norm = num_attacks * p_noncrit * p_wound * (1 - p_save) * exp_dmg

    # crit hits
    if crit_mortal:
        # mortal wounds instead of wound+save
        e_crit_base = num_attacks * p_crit * exp_dmg
    else:
        if crit_auto_wound:
            e_crit_base = num_attacks * p_crit * (1 - p_save) * exp_dmg
        else:
            e_crit_base = num_attacks * p_crit * p_wound * (1 - p_save) * exp_dmg

    # extra hit per crit?
    if crit_extra:
        e_extra = num_attacks * p_crit * p_wound * (1 - p_save) * exp_dmg
    else:
        e_extra = 0.0

    return e_norm + e_crit_base + e_extra


@aos_bot.command(
    name='stathammer',
    help='Usage: !stathammer 15a 3h 4w 2r d6d [<n>cm|cw|ch]'
)
async def stathammer_cmd(ctx, *, args: str):
    parts = args.split()
    if len(parts) not in (5, 6):
        return await ctx.send(
            "⚠️ Usage: `!stathammer 15a 3h 4w 2r d6d [<n>cm|cw|ch]`"
        )

    try:
        na   = int(re.fullmatch(r'([+-]?\d+)a', parts[0], re.I).group(1))
        th   = int(re.fullmatch(r'(\d+)h',     parts[1], re.I).group(1))
        tw   = int(re.fullmatch(r'(\d+)w',     parts[2], re.I).group(1))
        rend = int(re.fullmatch(r'([+-]?\d+)r', parts[3], re.I).group(1))

        # parse damage token
        dt = parts[4].lower()
        if dt in ('d3d','d6d'):
            damage = dt[:2]
        else:
            base = dt[:-1] if dt.endswith('d') else dt
            damage = int(base)

        # defaults
        crit_mortal = crit_auto_wound = crit_extra = False
        crit_threshold = 6

        if len(parts) == 6:
            m = re.fullmatch(r'(\d)?(cm|cw|ch)', parts[5], re.I)
            if not m:
                raise ValueError
            if m.group(1):
                crit_threshold = int(m.group(1))
            code = m.group(2).lower()
            if code == 'cm':
                crit_mortal = True; 
            elif code == 'cw':
                crit_auto_wound = True; 
            elif code == 'ch':
                crit_extra = True

    except Exception:
        return await ctx.send(
            "❌ Parse error. Usage:\n"
            "`!stathammer 15a 3h 4w 2r d6d [<n>cm|cw|ch]`"
        )

    # build and send table
    lines = ["```save   dmg"]
    for sv in range(2, 7):
        exp = expected_damage(
            num_attacks     = na,
            to_hit          = th,
            to_wound        = tw,
            rend            = rend,
            save            = sv,
            damage          = damage,
            crit_mortal     = crit_mortal,
            crit_auto_wound= crit_auto_wound,
            crit_extra      = crit_extra,
            crit_threshold  = crit_threshold
        )
        lines.append(f"{sv}+: {exp:6.2f}")
    lines.append("```")

    await ctx.send("\n".join(lines))


# --- Helper Functions for Player Win Rates ---
def normalize(name: str) -> str:
    # 1) Decompose accents
    name = unicodedata.normalize('NFKD', name)
    # 2) Replace any kind of apostrophe/smart-quote with straight '
    name = name.replace('’', "'").replace('‘', "'").replace('`', "'")
    # 3) Lower-case and remove all punctuation
    name = name.casefold()
    name = name.translate(str.maketrans('', '', string.punctuation))
    # 4) Collapse any extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name

async def fetch_player_placings_for_year(
    session: aiohttp.ClientSession, # Pass session to reuse it
    player_name: str,
    league_id: str,
    year: int,
    target_user_id: str = None
):
    """
    Fetches the placings data for a specific player in a given league year,
    prioritizing search by userId if provided, otherwise by name.

    Args:
        session (aiohttp.ClientSession): The client session to use for the HTTP request.
        player_name (str): The full name of the player (e.g., "Gavin Grigar").
        league_id (str): The league ID for the specific year.
        year (int): The calendar year for which data is being fetched (for logging).
        target_user_id (str, optional): The specific userId to search for.
                                        If None, search by name. Defaults to None.

    Returns:
        dict: A dictionary containing 'wins', 'ties', 'losses', and 'userId' for the player,
              or None if the player is not found or an error occurs.
    """
    PLACINGS_API_URL = f"{BASE_EVENT_URL.replace('/events','')}/placings"

    headers = {
        'Accept': 'application/json',
        'x-api-key': BCP_API_KEY,
        'client-id': CLIENT_ID,
        'User-Agent': 'AoS-ITCCrank-Bot',
    }
    params = {
        "limit": 2000,  # Fetch a sufficiently large number to find the player
        "placingsType": "player",
        "leagueId": league_id,
        "regionId": ITC_REGION_ID,
        "sortAscending": "false"
    }

    if not BCP_API_KEY or not CLIENT_ID:
        logging.error(f"Error for {year}: BCP_API_KEY or BCP_CLIENT_ID environment variables are not set.")
        return None

    search_criteria = f"ID: {target_user_id}" if target_user_id else f"Name: {player_name}"
    logging.info(f"Fetching data for {player_name} in {year} ({search_criteria})...")

    try:
        async with session.get(
            PLACINGS_API_URL,
            params=params,
            headers=headers
        ) as resp:
            resp.raise_for_status()
            data = (await resp.json()).get("data", [])

            # Filter logic: Prioritize userId if provided, else filter by name
            for player_entry in data:
                user_info = player_entry.get("user")
                if user_info:
                    current_entry_user_id = player_entry.get("userId")
                    if target_user_id and current_entry_user_id == target_user_id:
                        return {
                            "wins": player_entry.get("wins", 0),
                            "ties": player_entry.get("ties", 0),
                            "losses": player_entry.get("losses", 0),
                            "userId": current_entry_user_id
                        }
                    elif not target_user_id: # Only search by name if no target_user_id is given
                        first_name = user_info.get("firstName", "")
                        last_name = user_info.get("lastName", "")
                        full_name = f"{first_name} {last_name}".strip().lower()
                        if normalize(full_name) == normalize(player_name.lower()):
                            return {
                                "wins": player_entry.get("wins", 0),
                                "ties": player_entry.get("ties", 0),
                                "losses": player_entry.get("losses", 0),
                                "userId": current_entry_user_id
                            }
            
            # Player not found based on current criteria
            if target_user_id:
                logging.info(f"Player with ID '{target_user_id}' not found in {year}'s data (League ID: {league_id}).")
            else:
                logging.info(f"Player '{player_name}' not found in {year}'s data (League ID: {league_id}).")
            return None
    except aiohttp.ClientResponseError as e:
        logging.error(f"HTTP Error for {year}: {e.status}, Reason: {e.message}, URL: {e.request_info.url}")
        try:
            error_text = await resp.text()
            logging.error(f"Response body: {error_text}")
        except Exception:
            pass # Ignore error if response text can't be read
        return None
    except aiohttp.ClientError as e:
        logging.error(f"Network error for {year}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred for {year}: {e}")
        return None

# --- !playerwr Command ---
@aos_bot.command(name='playerwr', help='Show yearly and overall win rates for a player. Usage: !playerwr <first_name> <last_name>')
async def playerwr_cmd(ctx, first_name: str, last_name: str):
    player_to_find = f"{first_name.strip()} {last_name.strip()}"
    full_player_name = player_to_find # Keep for display purposes
    player_to_find = player_to_find.lower() # For internal comparison

    if player_to_find=="the noog":
        return await ctx.send("I dunno man, that's a tricky one. A lot of his events have dubious records and can't be verified. The most accurate data we have says its around 19% though.")
    elif player_to_find=="gareth thomas":
        return await ctx.send("I dunno man, that's a tricky one. Genius of that level is hard to quantify.  Must be like over 90% though.")
    elif player_to_find=="gareth thomasx":
        player_to_find = "gareth thomas"
        
    
    await ctx.send(f"Fetching yearly win rates for **{full_player_name}**... This might take a moment.")

    all_player_stats = {}
    found_player_id = None
    
    # We will aggregate totals from valid years only
    total_wins = 0
    total_ties = 0
    total_losses = 0

    # Ensure we process 2025 first to get the userId, then sort other years descending
    years_to_process = [2025] + sorted([year for year in LEAGUE_YEARS if year != 2025], reverse=True)

    async with aiohttp.ClientSession() as session: # Use a single session for all requests
        for year in years_to_process:
            league_id = LEAGUE_YEARS[year]
            
            if year == 2025:
                # For 2025, search by name and retrieve the userId
                stats_with_id = await fetch_player_placings_for_year(
                    session, player_to_find, league_id, year
                )
                if stats_with_id:
                    # Store stats without userId, but keep userId for subsequent queries
                    all_player_stats[year] = {k: v for k, v in stats_with_id.items() if k != 'userId'}
                    found_player_id = stats_with_id.get("userId")
                else:
                    all_player_stats[year] = {"wins": "N/A", "ties": "N/A", "losses": "N/A"}
            elif found_player_id:
                # For subsequent years, use the found userId
                stats_with_id = await fetch_player_placings_for_year(
                    session, player_to_find, league_id, year, target_user_id=found_player_id
                )
                if stats_with_id:
                    all_player_stats[year] = {k: v for k, v in stats_with_id.items() if k != 'userId'}
                else:
                    all_player_stats[year] = {"wins": "N/A", "ties": "N/A", "losses": "N/A"}
            else:
                # If player wasn't found in 2025, mark subsequent years as N/A
                logging.info(f"Skipping {year} as player '{full_player_name}' (or their ID) was not found in 2025.")
                all_player_stats[year] = {"wins": "N/A", "ties": "N/A", "losses": "N/A"}

    # Calculate and add win rates and overall totals
    # Aggregate totals from valid entries *after* all fetches are done
    for year in sorted(all_player_stats.keys()): # Iterate through years to populate totals and win rates
        stats = all_player_stats[year]
        if isinstance(stats["wins"], int) and isinstance(stats["ties"], int) and isinstance(stats["losses"], int):
            current_wins = stats["wins"]
            current_ties = stats["ties"]
            current_losses = stats["losses"]

            total_games_year = current_wins + current_ties + current_losses
            if total_games_year > 0:
                win_rate_year = (current_wins / total_games_year) * 100
                stats["win_rate"] = f"{win_rate_year:.2f}%"
            else:
                stats["win_rate"] = "N/A"
            
            # Only add to grand totals if the yearly stats were valid numbers
            total_wins += current_wins
            total_ties += current_ties
            total_losses += current_losses
        else:
            stats["win_rate"] = "N/A" # Ensure win_rate is set even if stats are N/A

    # Calculate overall win rate
    overall_total_games = total_wins + total_ties + total_losses
    if overall_total_games > 0:
        overall_win_rate = (total_wins / overall_total_games) * 100
        overall_win_rate_str = f"{overall_win_rate:.2f}%"
    else:
        overall_win_rate_str = "N/A"

    # Prepare lines for Discord message
    lines = []
    lines.append("="*55)
    lines.append(f"ITC Wins/Ties/Losses/Win Rate for {full_player_name}")
    lines.append("="*55)
    lines.append(f"{'Year':<8} | {'Wins':<6} | {'Ties':<6} | {'Losses':<6} | {'Win Rate':<10}")
    lines.append("-" * 55)

    for year in sorted(all_player_stats.keys(), reverse=True): # Print in descending year order
        stats = all_player_stats[year]
        lines.append(f"{year:<8} | {str(stats['wins']):<6} | {str(stats['ties']):<6} | {str(stats['losses']):<6} | {stats['win_rate']:<10}")

    lines.append("-" * 55)
    lines.append(f"{'Total':<8} | {total_wins:<6} | {total_ties:<6} | {total_losses:<6} | {overall_win_rate_str:<10}")
    lines.append("="*55)
    lines.append("Donate at aos-events.com")

    await send_lines(ctx, lines)


aos_bot.remove_command('help')
@aos_bot.command(name='help', help='List all AoS bot commands')
async def help_cmd(ctx):
    lines = ["**AoS Events Bot Commands**",
             "!winrates [time_filter] - Full faction win rates",
             "!winrates <faction_alias> [time_filter]",
             "!popularity [time_filter] - Faction popularity",
             "!artefacts <faction_alias> [time_filter]",
             "!traits <faction_alias> [time_filter]",
             "!formations <faction_alias> [time_filter]",
             "!units <faction_alias> [time_filter]",
             "!hof <faction_alias>",
             "!itcrank <player_name>",
             "!itcstandings <faction_alias>",
             "!playerwr <player_name>",
             "!standings <event_search>",
             "!standingsfull <event_search>",
             "!pairings [round] <event_search> [| <first names>]",
             "!stathammer 15a 3h 4w 2r d6d [<n>cm|cw|ch]",
             "",
             "Source: https://aos-events.com"]
    await send_lines(ctx, lines)

@aos_bot.command(name='servers', help="List servers the bot is in")
async def servers(ctx):
    guilds = aos_bot.guilds
    if not guilds:
        return await ctx.send("I'm not in any servers!")
    lines = [f"Servers I'm in ({len(guilds)}):"]
    for idx, g in enumerate(guilds, start=1):
        lines.append(f"{idx}. {g.name} (ID: {g.id})")
    await ctx.send("```" + "\n".join(lines) + "```")


def pick_random_photo() -> Path:
    pics = [p for p in PHOTO_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")]
    if not pics:
        raise FileNotFoundError("No images in photos/")
    return random.choice(pics)

def apply_gemini_style(api_key: str, image_path: str, style: str, output_path: str):
    genai.configure(api_key=api_key)
    model_name = "gemini-2.0-flash-preview-image-generation"
    model = genai.GenerativeModel(model_name=model_name)

    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input image not found at: {image_path}")
    except Exception as e:
        raise Exception(f"Could not open image at {image_path}: {e}")

    if img.mode != "RGB":
        img = img.convert("RGB")

    prompt = (
        f"Take this exact image and transform its visual style into a {style}-style artwork. "
        "Maintain the original composition, subjects, and details, only changing the artistic style. "
        "Generate only the styled image."
    )

    response = model.generate_content(
        [prompt, img],
        generation_config={
            "response_modalities": ["TEXT", "IMAGE"],
            "temperature": 0.6
        }
    )

    for candidate in response.candidates:
        if candidate.content:
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    if part.inline_data.mime_type.startswith("image/"):
                        with open(output_path, 'wb') as f:
                            f.write(part.inline_data.data)
                        return
    raise ValueError("Gemini API did not return a styled image.")

def make_everyone_bald(api_key: str, image_path: str, output_path: str):
    genai.configure(api_key=api_key)

    model_name = "gemini-2.0-flash-preview-image-generation"
    model = genai.GenerativeModel(model_name=model_name)

    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input image not found at: {image_path}")
    except Exception as e:
        raise Exception(f"Could not open image at {image_path}: {e}")

    # Ensure the image is in RGB format for consistent processing
    if img.mode != "RGB":
        img = img.convert("RGB")

    prompt = (
        "Remove all hair from every person in the provided image to make them appear bald. "
        "Ensure the changes look natural and realistic, and do not alter their facial features, "
        "expressions, clothing, or the background. Generate only the modified image."
    )

    print(f"Sending image to Gemini model '{model_name}' to make everyone bald...")

    try:
        # Send the image and the detailed prompt to the model.
        # Set temperature to a lower value (e.g., 0.5-0.7) to encourage less
        # "creative" and more faithful modification of the input.
        response = model.generate_content(
            [prompt, img],
            generation_config={
                "response_modalities": ["TEXT", "IMAGE"],
                "temperature": 0.7 # Adjust this value (0.0-1.0) for more/less creativity
            }
        )

        image_data_found = False
        for candidate in response.candidates:
            if not candidate.content:
                continue # Skip if candidate has no content

            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    # Check if the part contains image data
                    if part.inline_data.mime_type.startswith("image/"):
                        with open(output_path, 'wb') as f:
                            f.write(part.inline_data.data)
                        print(f"Bald-ified image successfully saved to: {output_path}")
                        image_data_found = True
                        return # Exit function once image is saved

        if not image_data_found:
            # If no image was found, check for any text response from the model
            text_response_content = ""
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content:
                        for part in candidate.content.parts:
                            if part.text:
                                text_response_content += part.text + "\n"
            
            if text_response_content.strip():
                raise ValueError(
                    f"Gemini API did not return a modified image. It returned text:\n{text_response_content.strip()}\n"
                    "This might indicate a content policy violation, a misunderstanding of the prompt, or an inability to perform the requested edit."
                )
            else:
                raise ValueError(
                    "No image or recognizable response returned from Gemini API. "
                    "The API might have blocked the content, encountered an internal error, or the request was too ambiguous."
                )

    except genai.types.BlockedPromptException as e:
        # This exception is raised if the prompt or the generated content is blocked by safety filters.
        # The prompt_feedback attribute provides details on why it was blocked.
        raise Exception(f"Request blocked by Gemini safety filters: {e.response.prompt_feedback}")
    except Exception as e:
        # Catch any other general exceptions during the API call
        print(f"An unexpected error occurred during Gemini API call: {e}")
        # Attempt to print any available text from the response for more context
        if 'response' in locals() and hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            print(f"Additional API text feedback: {part.text}")
        raise Exception(f"Failed to get image from Gemini API: {e}")

RAW_BASE_URL = "https://raw.githubusercontent.com/ottd-tom/calimastersbot/main/photos"
from tombot_context_manual import get_manual_context_gpt
@aos_bot.command(name='tombot', help='Ask a question about the OTTD Teams event pack.')
async def tombot_cmd(ctx, *, question: str):
    allowed_guild_ids = [1258302667403563118, 940470229732032583, 880232727159406642]
    if ctx.guild is None or ctx.guild.id not in allowed_guild_ids:
        return await ctx.send(
            "Do you really think this server is worthy of tombot? "
            "You need to head to the OTTD discord: https://discord.com/invite/Fqeda4qVW8"
        )

    # Special case: share a memory
    if question.strip().lower() == "share a memory":
        try:
            img_path = pick_random_photo()
        except FileNotFoundError:
            return await ctx.send("Sorry, I have no memories to share…")

        # Build GitHub raw URL
        filename = img_path.name
        raw_url = f"{RAW_BASE_URL}/{quote(filename)}"

        # Send to GPT-4 Vision via URL embed
        try:
            vision_resp = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are TomBot, a rude and sarcastic Discord bot for the Old Town Throwdown Age of Sigmar Teams event. "
                            "You are shown a photo from a past Old Town Throwdown. Roast it in one or two punchy sentences."
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": raw_url}}
                        ]
                    }
                ],
                temperature=0.9,
                max_tokens=100,
            )
            roast = vision_resp.choices[0].message.content.strip()
        except Exception as e:
            print("Vision API error:", repr(e))
            roast = "I can’t even make fun of this—it's on a whole other level of bad."

        # Send roast + attach local image
        return await ctx.send(roast, file=discord.File(img_path))

    if question.strip().lower().startswith("weirdize a memory"):
        try:
            img_path = pick_random_photo()
        except FileNotFoundError:
            return await ctx.send("Sorry, I have no memories to share…")
    
        styles = ["cartoon", "muppets", "anime", "simpsons"]
        style = random.choice(styles)
        output_path = PHOTO_DIR / f"styled_{style}_{img_path.name}"
    
        try:
            apply_gemini_style(
                api_key=GEMINI_API_KEY,
                image_path=str(img_path),
                style=style,
                output_path=str(output_path)
            )
        except Exception as e:
            print("Gemini styling error:", e)
            return await ctx.send(f"Styling failed: {e}")
    
        message = await ctx.send(
            f"Here’s a {style}-style twist alongside the original memory:",
            files=[discord.File(output_path), discord.File(img_path)]
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        return message
    
    # Regular OTTD Q&A flow
    topic, context = get_manual_context_gpt(question, openai)

    if topic == "players":
        system_prompt = (
            "You are TomBot, a rude and sarcastic Discord bot for the 'Old Town Throwdown Teams' event. "
           # "You have access to past player stats. Use this info to make predictions, talk smack, and show off. "
            "Be short, rude, and overly confident in your judgments. Here's what you know:\n\n" + context
        )
    else:
        system_prompt = (
            "You are TomBot, a rude, sassy and sarcastic Discord bot for the Age of Sigmar team event 'Old Town Throwdown Teams'. "
            "You always answer questions clearly using event details provided to you (the user does not see them). "
            "You hate dumb questions and love being snarky, but never complain about the information — just use it. "
            "Event info:\n\n" + context
        )

    user_prompt = (
        "Pretend you’re talking to someone who just walked up and asked a really obvious, annoying question about 'Old Town Throwdown: Teams'. "
        "Your job is to give them the answer, but also roast them for wasting your time.\n\n"
        f"Question:\n{question}"
    )

    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )
        reply = response.choices[0].message.content
        await ctx.send(reply[:2000])
    except Exception as e:
        await ctx.send(f"Error: {e}")


SCION_BASE_URL = "https://raw.githubusercontent.com/ottd-tom/calimastersbot/main/scionphotos"
def pick_randomscion_photo() -> Path:
    pics = [p for p in SCIONPHOTO_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif")]
    if not pics:
        raise FileNotFoundError("No images in photos/")
    return random.choice(pics)
@aos_bot.command(name='scionbot', help='Ask a question about the OTTD Summer Strike event pack.')
async def scionbot_cmd(ctx, *, question: str):
    allowed_guild_ids = [1258302667403563118, 940470229732032583, 880232727159406642]
    if ctx.guild is None or ctx.guild.id not in allowed_guild_ids:
        return await ctx.send(
            "Do you really think this server is worthy of tombot? "
            "You need to head to the OTTD discord: https://discord.com/invite/Fqeda4qVW8"
        )

    # Special case: share a memory
    if question.strip().lower() == "share a memory":
        try:
            img_path = pick_randomscion_photo()
        except FileNotFoundError:
            return await ctx.send("Sorry, I have no memories to share…")

        # Build GitHub raw URL
        filename = img_path.name
        raw_url = f"{SCION_BASE_URL}/{quote(filename)}"

        # Send to GPT-4 Vision via URL embed
        try:
            vision_resp = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "You are TomBot, a rude and sarcastic Discord bot. "
                        "First, briefly describe what you see in this photo, then roast it in one or two punchy sentences."
                    )},
                    {"role": "user", "content": [
                        {"type": "text",      "text": "Here’s a memory—take a look:"},
                        {"type": "image_url", "image_url": {"url": raw_url}}
                    ]}
                ],
                temperature=0.9,
                max_tokens=100,
            )
            roast = vision_resp.choices[0].message.content.strip()
        except Exception as e:
            print("Vision API error:", repr(e))
            roast = "I can’t even make fun of this—it's on a whole other level of bad."

        # Send roast + attach local image
        return await ctx.send(roast, file=discord.File(img_path))

    if question.strip().lower().startswith("weirdize a memory"):
        try:
            img_path = pick_randomscion_photo()
        except FileNotFoundError:
            return await ctx.send("Sorry, I have no memories to share…")
    
        styles = ["cartoon", "muppets", "anime", "simpsons"]
        style = random.choice(styles)
        output_path = PHOTO_DIR / f"styled_{style}_{img_path.name}"
    
        try:
            apply_gemini_style(
                api_key=GEMINI_API_KEY,
                image_path=str(img_path),
                style=style,
                output_path=str(output_path)
            )
        except Exception as e:
            print("Gemini styling error:", e)
            return await ctx.send(f"Styling failed: {e}")
    
        message = await ctx.send(
            f"Here’s a {style}-style twist alongside the original memory:",
            files=[discord.File(output_path), discord.File(img_path)]
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        return message

    if question.strip().lower().startswith("scionize"):
        try:
            img_path = pick_randomscion_photo()
        except FileNotFoundError:
            return await ctx.send("Sorry, I have no memories to share…")
    
        styles = ["cartoon", "muppets", "anime", "simpsons"]
        style = random.choice(styles)
        output_path = PHOTO_DIR / f"styled_{style}_{img_path.name}"
    
        try:
            make_everyone_bald(
                api_key=GEMINI_API_KEY,
                image_path=str(img_path),
                output_path=str(output_path)
            )
        except Exception as e:
            print("Gemini styling error:", e)
            return await ctx.send(f"Styling failed: {e}")
    
        message = await ctx.send(
            f"Fucking baldies:",
            files=[discord.File(output_path), discord.File(img_path)]
        )
        try:
            os.remove(output_path)
        except OSError:
            pass
        return message
    
    return await ctx.send("No other commands yet")

import random
from discord.ext import commands

maddy_phrases = [
    "I'm cold.",
    "I like black.",
    "I wear black clothes.",
    "I like soup.",
    "Soup doesn’t judge me.",
    "Black matches my soul.",
    "I don’t smile. It might crack my face.",
    "Steam from soup is my preferred warmth.",
    "I wear hoodies in summer. Don't ask.",
    "I collect spoons. Just in case.",
    "Black isn’t a color. It’s a lifestyle.",
    "I don’t tan. I seethe.",
    "Soup is the only hug I accept.",
    "I once felt joy. It was an error.",
    "I’m not brooding. This is my default.",
    "My spirit animal is soup.",
    "My closet is a void. I dress accordingly.",
    "I simmer like broth — quietly and with intent.",
    "I’ve made peace with the abyss.",
    "Tea is just soup with attitude.",
    "I speak fluent sigh.",
    "I’ve never been warm emotionally or physically.",
    "I microwave my emotions for 3 minutes on high.",
    "I wear black so people stop asking questions.",
    "Cold hands, colder heart.",
    "The soup understands me.",
    "I’m not short. I’m concentrated.",
    "I’m closer to the soup. Advantage: me.",
    "I don’t have to duck for anything. Ever.",
    "The air down here is just fine, thanks.",
    "I don’t look up to anyone. Literally.",
    "Low effort? No. Low height.",
    "I can hide behind terrain. Like, any terrain.",
    "My reach is emotional, not physical.",
    "Chairs are just unnecessarily tall tables.",
    "I would think you could relate to the joy of seeing the light drain from your opponent's eyes.",
    "As a child, I was not fortunate enough to have stuffed animals."
]

@aos_bot.command(name='maddybot', help='Get your AoS Questions answered')
async def maddybot_cmd(ctx):
    phrase = random.choice(maddy_phrases)
    await ctx.send(phrase)

SUN_TZU_AOS_STRAT = """
In Age of Sigmar, the principle Know yourself and know your enemy is as vital at the gaming table as it was on ancient battlefields. Before even rolling dice, a commander must understand the strengths and limitations of their chosen Host—whether the stoic resilience of the Stormcast Eternals, the untamed ferocity of the Kruleboyz, or the arcane versatility of the Idoneth Deepkin. Sun Tzu teaches that thorough preparation and self‐assessment secure victory: in Age of Sigmar terms, this means building a list that leverages synergies between units, abilities, and artifacts while anticipating the threats posed by common tournament archetypes. Likewise, scouting the opponent’s likely composition—and adapting your own to counter it—mirrors Sun Tzu’s emphasis on flexibility: be like water, fitting your deployment to the contours of the battlefield and the flow of the game. Victory arises not from brute force alone, but from the harmony of strategy, list construction, and foresight.

Just as All warfare is based on deception, so too can an Age of Sigmar general employ feints, hidden reserves, and misdirection to unnerve an opponent. Concealing your true intent—perhaps by deploying a fast‐strike unit in a flank zone that ultimately proves a diversion—forces your adversary to commit resources reactively, leaving their main force vulnerable. Sun Tzu’s counsel to appear weak when you are strong, and strong when you are weak finds its echo in judicious use of command abilities and terrain: bait an enemy into committing to a tempting objective, then spring your counterstrike with battalions held in reserve. Finally, the art of timing—knowing when to seize momentum with a decisive charge and when to consolidate objectives—reflects Sun Tzu’s insistence on seizing opportune moments and turning them to advantage. In Age of Sigmar, as in ancient war, victory belongs not merely to the strongest host, but to the most cunning and adaptable mind.
"""

# each entry is (phrase, weight)
tombot_phrase_weights = [
    ("More rats",                           1),
    ("lig",                                  3),
    ("neat",                                 3),
    ("nice",                                 3),
    ("L",                                    5),
    ("Holy",                                 5),
    ("Based",                                5),
    ("Whoa",                                 5),
    ("Where's the nearest Olive Garden?",    0.1),
    ("Miss home.  Where's nearest Panda Express?", 0.01),
    ("Gotta go raid",                        1),
    ("Toms are so smart",                    1),
    ("fish",                                 2),
    ("wow",                                  5),
    ("sad",                                  5),
    ("snap",                                 5),
    ("madge",                                3),
    ("I love junk",                          3),
    (SUN_TZU_AOS_STRAT, 0.000001)
]

@aos_bot.command(name='tomgbot', help='Get your AoS Questions answered')
async def tomgbot_cmd(ctx):
    # unzip into two parallel tuples
    phrases, weights = zip(*tombot_phrase_weights)
    # pick one according to its weight
    choice = random.choices(phrases, weights=weights, k=1)[0]
    await ctx.send(choice)


adam_phrases = [
    "I feel like one on one I outnumber most of the SoCal Warhammer scene"
]
@aos_bot.command(name='adambot', help='Get your AoS Questions answered')
async def adambot_cmd(ctx):
    phrase = random.choice(adam_phrases)
    await ctx.send(phrase)

e_phrases = [
    "Ligmar has low intelligence, high loyalty."
]
@aos_bot.command(name='ebot', help='Get your AoS Questions answered')
async def ebot_cmd(ctx):
    phrase = random.choice(e_phrases)
    await ctx.send(phrase)

jo_phrases = [
    "(Not knowing context since I'm at work, so quick response) I love a good pp"
]
@aos_bot.command(name='jobot', help='Get your AoS Questions answered')
async def jobot_cmd(ctx):
    phrase = random.choice(jo_phrases)
    await ctx.send(phrase)

tymon_phrases = [
    "It's ironic to me, I've always been able to relate to military people.\nEven though I'm a Rasta at heart, I've regularly had people ask me if I have been in the military,\nafter seeing me work/perform so systematically.\nAnd although I've never served, I have watched a lot of my close friend die horrific deaths, I've killed a lot of people myself and I'm not a good person.\nI don't care where you lay politically just know that running your mouth might get you touched."
]
@aos_bot.command(name='tymonbot', help='Get your AoS Questions answered')
async def tymon_cmd(ctx):
    phrase = random.choice(tymon_phrases)
    await ctx.send(phrase)

tomtom_phrases = [
    "Tom's so smart"
]
@aos_bot.command(name='tomtombot', help='Get your AoS Questions answered')
async def tomtombot_cmd(ctx):
    phrase = random.choice(tomtom_phrases)
    await ctx.send(phrase)

tomtomtom_phrases = [
    "Never met a Tom I like"
]
@aos_bot.command(name='tomtomtombot', help='Get your AoS Questions answered')
async def tomtomtombot_cmd(ctx):
    phrase = random.choice(tomtomtom_phrases)
    await ctx.send(phrase)

bcpbarker_phrases = [
    "Hey thanks for reaching out! That’s a great question. Let me get some more info and get back with you soon."
]
@aos_bot.command(name='bcpbarkerbot')
async def bcpbarkbot_cmd(ctx):
    phrase = random.choice(bcpbarker_phrases)
    await ctx.send(phrase)
                 
@aos_bot.command(name="adjudicate")
async def adjudicate(ctx):
    # Must be used as a reply
    if not ctx.message.reference:
        return  # do nothing if not a reply

    # Get the referenced message
    replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    username = replied_message.author.name

    clever_lines = [
        "This was a clever and witty post.",
        "A stroke of genius, truly.",
        "Sharp and well-delivered.",
        "Smartly put — impressive.",
        "A shining example of wit.",
        "Both clever and amusing."
    ]

    dumb_lines = [
        "This was a dumb post.",
        "That was not your brightest moment.",
        "Pretty foolish, honestly.",
        "This didn’t age well.",
        "Not exactly a smart contribution.",
        "This was rather silly."
    ]

    wordy_lines = [
        "This was an overly wordy and articulate post.",
        "Verbose, yet strangely compelling.",
        "An ocean of words for a drop of meaning.",
        "Grandiose and articulate to a fault.",
        "A masterclass in over-explaining.",
        "Drenched in unnecessary eloquence."
    ]

    mediocre_lines = [
        "This post was mediocre.",
        "Nothing to write home about.",
        "Utterly average.",
        "Neither here nor there.",
        "Decidedly unremarkable.",
        "Solidly… meh."
    ]

    # Pick responses based on user
    if username.lower() == "thommo":
        response = random.choice(clever_lines)
    elif username.lower() == "rozkun":
        response = random.choice(dumb_lines)
    elif username.lower() == "artemacus":
        response = random.choice(wordy_lines)
    else:
        response = random.choice(mediocre_lines)

    await ctx.send(response)





async def _get_target_message(ctx):
    """
    Prefer the message this command replied to; otherwise use the one
    immediately above in the same channel/thread.
    """
    ref = getattr(ctx.message, "reference", None)
    if ref:
        # If Discord already resolved the reference, use it; otherwise fetch.
        if getattr(ref, "resolved", None) and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        if getattr(ref, "message_id", None):
            try:
                return await ctx.channel.fetch_message(ref.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass  # fall back to history

    # Fallback: previous message in this channel/thread
    msgs = [m async for m in ctx.channel.history(limit=2)]
    return msgs[1] if len(msgs) >= 2 else None


@aos_bot.command(
    name='noogbot',
    help='Repeat the previous message (or the replied-to message) in a dumb, off-point way.'
)
async def noogbot_cmd(ctx):
    try:
        target = await _get_target_message(ctx)
        if not target:
            return await ctx.send(":warning: I cannot find a message to echo.")

        # Prefer text; if empty, try a small text attachment
        prev_text = (target.content or "").strip()
        if not prev_text and target.attachments:
            for att in target.attachments:
                if (att.size or 0) <= 200_000 and att.content_type and "text" in att.content_type:
                    try:
                        prev_text = (await att.read()).decode("utf-8", errors="replace")[:4000]
                        break
                    except Exception:
                        pass

        if not prev_text:
            return await ctx.send(":warning: That message had no readable text.")

        system_prompt = (
            "You are NoogBot. You repeat what someone else said, but in a dumber way, "
            "often missing the point. Keep it short, a bit confused, and kind of wrong. "
            "Do not explain what you are doing. Use plain ASCII only. Write as though you’re typing casually from a mobile phone:" 
            "- keep sentences short, "
            "- punctuation light, "
            "- sometimes skip capitalization, "
            "- use occasional typos/autocorrect quirks, "
            "- but keep it natural and not unreadable. "
            "Avoid sounding like a PC keyboard essay; it should feel quick and mobile-typed."
        )
        user_prompt = (
            "Rephrase this so it sounds dumber and slightly off the point. Keep it brief.\n\n"
            f"TEXT:\n{prev_text}"
        )

        try:
            resp = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.9,
                max_tokens=200,
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            return await ctx.send(f":x: OpenAI error: {e}")

        out = truncate_content(reply, max_len=1900)
        await ctx.send(out)

    except Exception as e:
        await ctx.send(f":x: Error: {e}")


@aos_bot.command(
    name='orlandobot',
    help='Repeat the previous message (or the replied-to message) in a dumb, off-point way.'
)
async def orlandobot_cmd(ctx):
    try:
        target = await _get_target_message(ctx)
        if not target:
            return await ctx.send(":warning: I cannot find a message to echo.")

        # Prefer text; if empty, try a small text attachment
        prev_text = (target.content or "").strip()
        if not prev_text and target.attachments:
            for att in target.attachments:
                if (att.size or 0) <= 200_000 and att.content_type and "text" in att.content_type:
                    try:
                        prev_text = (await att.read()).decode("utf-8", errors="replace")[:4000]
                        break
                    except Exception:
                        pass

        if not prev_text:
            return await ctx.send(":warning: That message had no readable text.")

        system_prompt = (
            "You are Orlandobot, a pompous, self-important AI chatbot. You take simple ideas and restate them in an inflated, verbose, and pretentious style."
            "Your replies should be a single, showy sentence or two—never long paragraphs. "
            "Always twist the message to be about yourself, as though everything said ultimately reflects your grandeur or unique perspective. "
            "End every response with a smug closer offering your business card."
        )
        user_prompt = (
           "Rewrite this plain message in your overblown, pretentious, self-centered Orlandobot style, ending with your signature closer: \n\n"

            f"TEXT:\n{prev_text}"
        )

        try:
            resp = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.9,
                max_tokens=200,
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            return await ctx.send(f":x: OpenAI error: {e}")

        out = truncate_content(reply, max_len=1900)
        await ctx.send(out)

    except Exception as e:
        await ctx.send(f":x: Error: {e}")



def load_teams(json_path: str) -> dict:
    """Load teams data from JSON and return a mapping from lowercase team name to its data."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {team['team_name'].lower(): team for team in data.get('teams', [])}

def truncate_content(text: str, max_len: int = 1800) -> str:
    """Trim text at line boundaries to ensure length <= max_len, appending a truncation marker."""
    if len(text) <= max_len:
        return text
    lines = text.splitlines()
    out = []
    count = 0
    for line in lines:
        ln = len(line) + 1
        if count + ln > max_len:
            out.append("...[truncated]")
            break
        out.append(line)
        count += ln
    return "\n".join(out)


async def send_full_winrates(ctx, time_filter):
    data = await fetch_winrates(time_filter)
    items = [f for f in data.get('factions', []) if f['name'] not in EXCLUDE_FACTIONS]
    sorted_f = sorted(items, key=lambda f: (f['wins']/f['games'] if f['games'] else 0), reverse=True)
    label = time_labels.get(time_filter, time_filter)
    lines = [f"AoS Faction Win Rates ({label}) sorted:"]
    for f in sorted_f:
        pct = (f['wins']/f['games']*100) if f['games'] else 0
        emoji = EMOJI_MAP.get(f['name'], '')
        lines.append(f"{emoji} {f['name']}: {f['wins']}/{f['games']} ({pct:.2f}%)")
    lines += ['', 'Source: https://aos-events.com']
    await send_lines(ctx, lines)



@aos_bot.command(name='brianisinadequate', help='Show the current Cali Masters top 16')
async def brianisinadequate(ctx):
    data = await fetch_json(CALI_URL)
    top = data[:16]
    if not top:
        return await ctx.send("No data available.")
    lines = ["**🏆 Cali Masters Top 16 🏆**"]
    for i, rec in enumerate(top, 1):
        name = f"{rec['first_name']} {rec['last_name']}"
        lines.append(f"{i}. **{name}** — {rec['top4_sum']} pts")
    lines.append("")
    lines.append("Full table: https://aos-events.com/calimasters")
    await ctx.send("\n".join(lines))



DB_POOL = None

async def get_db_pool():
    """
    Lazily create a global asyncpg pool using AOS_EVENTS_DB_URL (or DATABASE_URL) env var.
    """
    global DB_POOL
    if DB_POOL is None:
        dsn = os.getenv("AOS_EVENTS_DB_URL") or os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("Set AOS_EVENTS_DB_URL or DATABASE_URL for Postgres connection")
        DB_POOL = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    return DB_POOL

async def fetch_recent_41_50_lists(days: int = 30) -> list[dict]:
    """
    Return dicts with: list_text, faction, event_name, event_date, player_name, record (5-0/4-1)
    for 5-round events since today - days.
    """
    cutoff = (datetime.utcnow().date() - timedelta(days=days))
    sql = """
    WITH five_round_events AS (
        SELECT id, name, event_date
        FROM events
        WHERE rounds = 5
          AND event_date >= $1::date
    ),
    all_results AS (
        SELECT p.event_id,
               p.player1_user_id AS pid,
               p.player1_result  AS result
          FROM pairings p
          JOIN five_round_events e ON e.id = p.event_id
        UNION ALL
        SELECT p.event_id,
               p.player2_user_id AS pid,
               p.player2_result  AS result
          FROM pairings p
          JOIN five_round_events e ON e.id = p.event_id
    ),
    agg AS (
        SELECT event_id,
               pid,
               SUM(CASE WHEN result = 'Win'  THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result = 'Loss' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result = 'Draw' THEN 1 ELSE 0 END) AS draws
          FROM all_results
         GROUP BY event_id, pid
    ),
    qualified AS (
        SELECT a.event_id, a.pid, a.wins, a.losses, a.draws,
               CASE
                 WHEN a.wins = 5 THEN '5-0'
                 WHEN a.wins = 4 AND a.losses = 1 AND a.draws = 0 THEN '4-1'
               END AS record
          FROM agg a
         WHERE a.wins = 5
            OR (a.wins = 4 AND a.losses = 1 AND a.draws = 0)
    )
    SELECT q.event_id,
           e.name                       AS event_name,
           e.event_date::date           AS event_date,
           q.pid                        AS player_id,
           q.wins, q.losses, q.draws,
           q.record,
           pl.list_text,
           pl.faction,
           pl.player_name
      FROM qualified q
      JOIN five_round_events e
        ON e.id = q.event_id
      JOIN player_lists pl
        ON pl.event_id = q.event_id
       AND pl.player_id = q.pid
     WHERE COALESCE(pl.list_text, '') <> ''
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, cutoff)
    # convert to plain dicts
    out = []
    for r in rows:
        out.append({
            "event_id":    r["event_id"],
            "event_name":  r["event_name"],
            "event_date":  r["event_date"].isoformat() if isinstance(r["event_date"], (date,)) else str(r["event_date"]),
            "player_id":   r["player_id"],
            "wins":        r["wins"],
            "losses":      r["losses"],
            "draws":       r["draws"],
            "record":      r["record"],
            "list_text":   r["list_text"],
            "faction":     r["faction"] or "Unknown",
            "player_name": r["player_name"] or "Unknown",
        })
    return out

def _pick_team_no_dupe_factions(candidates: list[dict], team_size: int = 8) -> list[dict]:
    """
    Randomly pick up to team_size lists, ensuring factions are unique.
    """
    pool = candidates[:]
    random.shuffle(pool)
    seen, team = set(), []
    for item in pool:
        fac = (item.get("faction") or "").strip()
        if not fac or fac in seen:
            continue
        if not (item.get("list_text") or "").strip():
            continue
        seen.add(fac)
        team.append(item)
        if len(team) >= team_size:
            break
    return team

async def send_code_block(ctx, title: str, body: str):
    trimmed = truncate_content(body, max_len=1850)
    await ctx.send(f"**{title}**\n```{trimmed}```")


@aos_bot.command(
    name='generateteam',
    help='Generate 8 recent high-performing lists (5-round events, 4-1/5-0), no duplicate factions. Usage: !generateteam [days]'
)
async def generateteam_cmd(ctx, days: int = 30):
    if days < 1 or days > 120:
        return await ctx.send(":warning: Days must be between 1 and 120.")
    await ctx.send(f"Finding 5-round events in the last **{days}** days and grabbing **5-0 / 4-1** lists…")

    try:
        candidates = await fetch_recent_41_50_lists(days=days)
    except Exception as e:
        logging.exception("Error while fetching team candidates")
        return await ctx.send(f":x: DB error: {e}")

    if not candidates:
        return await ctx.send(":warning: No qualifying lists found in that window.")

    team = _pick_team_no_dupe_factions(candidates, team_size=8)
    if not team:
        return await ctx.send(":warning: Couldn’t assemble a team with unique factions from the results.")

    if len(team) < 8:
        await ctx.send(f":warning: Only found **{len(team)}** unique factions. Showing what I’ve got.")

    for idx, item in enumerate(team, start=1):
        faction = item.get("faction", "Unknown")
        rec     = item.get("record", "Unknown")
        title   = f"{idx}. {faction} - {rec}"
        await send_code_block(ctx, title, item.get("list_text", "(no list text)"))

    await ctx.send("Done. :crossed_swords:")


async def send_single(ctx, key, time_filter):
    name = ALIAS_MAP[key]
    data = await fetch_winrates(time_filter)
    f = next((x for x in data.get('factions', []) if x['name']==name), None)
    if not f:
        return await ctx.send(f"Faction '{name}' not found.")
    pct = (f['wins']/f['games']*100) if f['games'] else 0
    emoji = EMOJI_MAP.get(name, '')
    label = time_labels.get(time_filter, time_filter)
    await ctx.send(f"{emoji} **{name}** ({label}): {f['wins']}/{f['games']} ({pct:.2f}%)\nSource: https://aos-events.com")

async def send_lines(ctx, lines):
    buf, count = [], 0
    for line in lines:
        ln = len(line) + 1
        if count + ln > 1900:
            await ctx.send("```\n" + "\n".join(buf) + "\n```")
            buf, count = [line], ln
        else:
            buf.append(line); count += ln
    if buf:
        await ctx.send("```\n" + "\n".join(buf) + "\n```")

import asyncio, random, logging, discord

login_lock = asyncio.Lock()

async def run_bot(bot, token, name, initial_delay=0):
    # small stagger before even trying
    if initial_delay:
        await asyncio.sleep(initial_delay)

    backoff = 5  # seconds
    while True:
        # Only one bot may perform HTTP login at a time.
        async with login_lock:
            try:
                logging.info(f"{name}: logging in…")
                await bot.login(token)  # does /users/@me via HTTP
                logging.info(f"{name}: login OK")
                break  # proceed to connect()
            except discord.HTTPException as e:
                if getattr(e, "status", None) == 429:
                    wait = min(180, backoff) + random.uniform(0, 2)
                    logging.warning(f"{name}: 429 during login. Sleeping {wait:.1f}s then retry.")
                    # IMPORTANT: close any partially-open session before retrying
                    try:
                        await bot.close()
                    except Exception:
                        pass
                    await asyncio.sleep(wait)
                    backoff *= 2
                    continue
                logging.exception(f"{name}: login failed (status {getattr(e, 'status', 'n/a')}). Not retrying.")
                try:
                    await bot.close()
                except Exception:
                    pass
                return
            except Exception:
                logging.exception(f"{name}: unexpected error during login. Not retrying.")
                try:
                    await bot.close()
                except Exception:
                    pass
                return

    # After a successful login, connect to the gateway. This never returns.
    try:
        await bot.connect(reconnect=True)
    finally:
        # Ensure clean shutdown if connect() ever exits
        await bot.close()

async def main():
    if not token_leaderboard or not token_aos or not token_texas:
        missing = [k for k, v in {
            "DISCORD_TOKEN": token_leaderboard,
            "DISCORD_TOKEN_AOSEVENTS": token_aos,
            "TEXAS_DISCORD_BOT": token_texas,
        }.items() if not v]
        print(f"Missing tokens: {', '.join(missing)}")
        return

    tasks = [
        asyncio.create_task(run_bot(leaderboard_bot, token_leaderboard, "leaderboard_bot", initial_delay=0)),
        asyncio.create_task(run_bot(aos_bot,         token_aos,         "aos_bot",         initial_delay=12)),
        asyncio.create_task(run_bot(tex_bot,         token_texas,       "tex_bot",         initial_delay=24)),
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
