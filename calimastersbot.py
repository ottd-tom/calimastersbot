import os
import aiohttp
import discord
from discord.ext import commands
import asyncio
import logging
import re
import random
import urllib.parse
from wordfreq import top_n_list
from datetime import datetime, timedelta

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
    'Sons of Behemat': '🍖',
    'Sylvaneth': '🌳',
    'Seraphon': '🦎',
    'Soulblight Gravelords': '🩸',
    'Blades of Khorne': '🔥',
    'Stormcast Eternals': '⚡',
    'Hedonites of Slaanesh': '🎵 ',
    'Cities of Sigmar': '🏙️',
    'Daughters of Khaine': '🩸',
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
    def __init__(self, events, ctx):
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

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        ev = self.events[self.values[0]]
        await do_pairings(self.ctx, ev)
        self.view.stop()

class PairingsView(discord.ui.View):
    def __init__(self, events, ctx):
        super().__init__(timeout=60)
        self.add_item(PairingsSelect(events, ctx))

async def do_pairings(ctx, ev, requested_round=None):
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
            params = {
                "eventId":     ev_id,
                "round":       rnd,
                "pairingType": "Pairing",
            }
            async with session.get(f"{BASE_EVENT_URL}/{ev_id}/pairings",
                                   params=params, headers=headers) as presp:
                presp.raise_for_status()
                raw = await presp.json()

            active = raw.get("active")
            if not active:
                active = raw.get("data", [])

            if active:
                pairings = active
                chosen_round = rnd
                break

    if not pairings:
        if requested_round:
            return await ctx.send(f":warning: No pairings found for `{ev_name}` ({ev_id}) in round {requested_round}.")
        else:
            return await ctx.send(f":warning: No pairings found for `{ev_name}` ({ev_id}).")

    header  = f"Pairings for {ev_name} ({ev_id}) — Round {chosen_round}"
    cols    = "Player 1 Name         | Pts | Player 2 Name         | Pts"
    divider = "-" * len(cols)

    lines = [header, cols, divider]
    for p in pairings:
        u1    = p["player1"]["user"]
        name1 = f"{u1['firstName']} {u1['lastName']}"
        pts1  = p.get("player1Game", {}).get("points", "")

        if p.get("player2"):
            u2    = p["player2"]["user"]
            name2 = f"{u2['firstName']} {u2['lastName']}"
            pts2  = p.get("player2Game", {}).get("points", "")
        else:
            name2, pts2 = "(bye)", ""

        lines.append(f"{name1:<22} | {pts1:^3} | {name2:<22} | {pts2:^3}")

    await send_lines(ctx, lines)
    await ctx.send(f"View full pairings: https://www.bestcoastpairings.com/event/{ev_id}?active_tab=pairings")

@aos_bot.command(name='pairings', help='!pairings [round] <event_search>')
async def pairings_cmd(ctx, *, args: str):
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
        return await do_pairings(ctx, matches[0], requested_round)

    await ctx.send("Multiple events found—please pick one:", view=PairingsView(matches, ctx))









@aos_bot.command(name='itcrank', aliases=['crankit'], help='Show ITC placing and points for a player (via BCP API)')
async def itcrank_cmd(ctx, *, name: str):
    name = name.strip()
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


# --- New Helper Function for Player Win Rates ---
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
                        if full_name == player_name.lower():
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

# --- New !playerwr Command ---
@aos_bot.command(name='playerwr', help='Show yearly and overall win rates for a player. Usage: !playerwr <first_name> <last_name>')
async def playerwr_cmd(ctx, first_name: str, last_name: str):
    player_to_find = f"{first_name.strip()} {last_name.strip()}"
    full_player_name = player_to_find # Keep for display purposes
    player_to_find = player_to_find.lower() # For internal comparison

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


# ─── WHO IS REALLY BETTER (AI-POWERED COMPARISON) ───────────────────────────────────
@aos_bot.command(
    name='whoisreallybetter',
    help='Compare two players by ITC performance over the years using AI. Usage: !whoisreallybetter <name1> <name2> OR !whoisreallybetter <name1> or <name2>'
)
async def whoisreallybetter_cmd(ctx, *, query: str):
    import openai # Import openai inside the function to keep it localized
    from openai import OpenAI

    # Check for OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return await ctx.send(":warning: OpenAI API key (OPENAI_API_KEY) is not set. Cannot use AI comparison.")
    
    # Parse names
    parts = re.split(r'\s+or\s+', query, flags=re.IGNORECASE)
    if len(parts) == 2:
        name1_display, name2_display = parts[0].strip(), parts[1].strip()
    else:
        toks = query.split()
        if len(toks) < 4:
            return await ctx.send("Usage: `!whoisreallybetter <first1> <last1> <first2> <last2>` or `!whoisreallybetter <name1> or <name2>`")
        name1_display = f"{toks[0]} {toks[1]}".strip()
        name2_display = f"{toks[2]} {toks[3]}".strip()

    # Special jokes (optional, can be removed if not desired for this command)
    if name1_display.lower()=="gareth thomas" or name2_display.lower()=="gareth thomas":
        return await ctx.send("Gareth Thomas is morally and intellectually superior. No AI needed here. Now stop bothering me.")

    # --- New Dynamic Secret Result for Matt Nguyen and Eugene Averin ---
    player_names_normalized = tuple(sorted([name1_display.lower(), name2_display.lower()]))
    if player_names_normalized == ("eugene averin", "matt nguyen"):
        await ctx.send(f"Oh, you've chosen to compare {name1_display} and {name2_display}? Brace yourself. The truth is going to hurt... me, for having to even process this.")
        
        system_prompt_special = (
            "You are an extremely cynical, judgmental, and exasperated Age of Sigmar bot. "
            "You have been asked to compare 'Matt Nguyen' and 'Eugene Averin'. "
            "Generate a highly derogatory and utterly dismissive paragraph about *both* of them. "
            "Emphasize that they are fundamentally awful, terrible players, incapable of making any rational decision. "
            "Furthermore, assert their profound immaturity and suggest they would spend more time throwing stupid, meaningless banter at each other than actually playing the game. "
            "Be cutting, sarcastic, and leave no room for doubt about your low opinion of their combined abilities and character. Keep it under 200 words."
        )
        user_prompt_special = (
            f"Compare the two players: {name1_display} and {name2_display}. "
            "Focus on their collective inability, immaturity, and propensity for pointless banter."
        )

        try:
            client = OpenAI(api_key=openai_api_key)
            response_special = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt_special},
                    {"role": "user", "content": user_prompt_special},
                ],
                temperature=1.0, # Max temperature for maximum chaos and meanness
            )
            ai_response_special = response_special.choices[0].message.content
            return await ctx.send(f"**Special Report: A Void of Talent (Powered by my Disappointment):**\n{ai_response_special}")

        except Exception as e:
            logging.error(f"Error generating special AI comparison for Matt/Eugene: {e}")
            return await ctx.send(f":warning: Even the AI recoiled from comparing {name1_display} and {name2_display}. Error: {e}")
    # --- End New Dynamic Secret Result ---
    
    await ctx.send(f"Consulting the grim archives of inadequacy for {name1_display} vs {name2_display}... Prepare for a dose of reality.")

    player_names = {
        'player1': name1_display,
        'player2': name2_display
    }
    
    all_players_yearly_stats = {}

    async with aiohttp.ClientSession() as session: # Use a single session for all requests
        for player_key, display_name in player_names.items():
            player_name_for_search = display_name.lower()
            yearly_stats = {}
            found_player_id = None
            total_wins_player = 0
            total_ties_player = 0
            total_losses_player = 0

            years_to_process_ordered = [2025] + sorted([y for y in LEAGUE_YEARS if y != 2025], reverse=True)

            for year in years_to_process_ordered:
                league_id = LEAGUE_YEARS[year]
                
                if year == 2025:
                    stats_with_id = await fetch_player_placings_for_year(
                        session, player_name_for_search, league_id, year
                    )
                elif found_player_id:
                    stats_with_id = await fetch_player_placings_for_year(
                        session, player_name_for_search, league_id, year, target_user_id=found_player_id
                    )
                else:
                    stats_with_id = None # Skip if ID not found from 2025

                if stats_with_id:
                    yearly_stats[year] = {k: v for k, v in stats_with_id.items() if k != 'userId'}
                    if year == 2025: # Only update ID from the first successful fetch (2025)
                        found_player_id = stats_with_id.get("userId")
                else:
                    yearly_stats[year] = {"wins": "N/A", "ties": "N/A", "losses": "N/A"}
            
            # Calculate yearly win rates and aggregate totals for the current player
            for year in sorted(yearly_stats.keys()):
                stats = yearly_stats[year]
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
                    
                    total_wins_player += current_wins
                    total_ties_player += current_ties
                    total_losses_player += current_losses
                else:
                    stats["win_rate"] = "N/A"

            # Calculate overall win rate for the current player
            overall_total_games_player = total_wins_player + total_ties_player + total_losses_player
            if overall_total_games_player > 0:
                overall_win_rate_player_str = f"{(total_wins_player / overall_total_games_player) * 100:.2f}%"
            else:
                overall_win_rate_player_str = "N/A"

            all_players_yearly_stats[player_key] = {
                "display_name": display_name,
                "yearly_stats": yearly_stats,
                "overall_stats": {
                    "wins": total_wins_player,
                    "ties": total_ties_player,
                    "losses": total_losses_player,
                    "win_rate": overall_win_rate_player_str
                }
            }
    
    # --- New Check for No Player Records ---
    player1_data = all_players_yearly_stats['player1']['overall_stats']
    player2_data = all_players_yearly_stats['player2']['overall_stats']

    has_player1_data = isinstance(player1_data['wins'], int) and (player1_data['wins'] + player1_data['ties'] + player1_data['losses']) > 0
    has_player2_data = isinstance(player2_data['wins'], int) and (player2_data['wins'] + player2_data['ties'] + player2_data['losses']) > 0

    if not has_player1_data and not has_player2_data:
        return await ctx.send(f":warning: Neither **{name1_display}** nor **{name2_display}** have any recorded ITC games across the years. What a waste of my time. Find some actual players to compare.")
    elif not has_player1_data:
        return await ctx.send(f":warning: **{name1_display}** has no recorded ITC games. There's nothing to compare. Are you even trying? {name2_display} wins by default, congratulations on being less invisible.")
    elif not has_player2_data:
        return await ctx.send(f":warning: **{name2_display}** has no recorded ITC games. Frankly, I expected more. {name1_display} wins by default, good job showing up, I guess.")
    # --- End New Check ---


    # Prepare data for LLM
    llm_prompt_data = []
    for player_key, data in all_players_yearly_stats.items():
        player_info = f"Player: {data['display_name']}\n"
        player_info += "Yearly Stats:\n"
        for year in sorted(data['yearly_stats'].keys(), reverse=True):
            stats = data['yearly_stats'][year]
            if isinstance(stats['wins'], int):
                player_info += f"  {year}: {stats['wins']} Wins, {stats['ties']} Ties, {stats['losses']} Losses (Win Rate: {stats['win_rate']})\n"
            else:
                player_info += f"  {year}: No data recorded\n"
        
        overall_stats = data['overall_stats']
        if isinstance(overall_stats['wins'], int):
            player_info += f"Overall: {overall_stats['wins']} Wins, {overall_stats['ties']} Ties, {overall_stats['losses']} Losses (Overall Win Rate: {overall_stats['win_rate']})\n"
        else:
            player_info += f"Overall: No data recorded\n"
        llm_prompt_data.append(player_info)

    # Construct LLM prompt with a meaner tone
    system_prompt = (
        "You are a brutally honest, cynical, and condescending Age of Sigmar ITC bot. "
        "Your task is to analyze the provided player statistics and write a short, **cutting, and highly critical** paragraph "
        "(under 250 words) comparing the two players. "
        "Your goal is to definitively state who is the 'better' player based *only* on these raw, undeniable stats, or hilariously mock their mutual mediocrity. "
        "Highlight significant statistical disparities or pathetic consistencies in the most disparaging way possible. "
        "Be aggressive, dismissive, and use strong, judgmental language. If a player has 'No data recorded', don't just mention it – ridicule their lack of commitment or historical presence. "
        "No sugar-coating. Just cold, hard, snarky truth."
    )

    user_prompt = (
        "Analyze the following player statistics and tell me who is better:\n\n"
        f"{llm_prompt_data[0]}\n"
        f"{llm_prompt_data[1]}\n"
    )

    try:
        client = OpenAI(api_key=openai_api_key)
        response = await asyncio.to_thread( # Run in a separate thread to avoid blocking the event loop
            client.chat.completions.create,
            model="gpt-4o-mini", # Still using gpt-4o-mini, tone is mostly prompt-driven
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9, # Increased temperature for more creative, aggressive language
        )
        ai_response = response.choices[0].message.content
        await ctx.send(f"**The Unvarnished Truth (Brutality by AI):**\n{ai_response}")

    except Exception as e:
        logging.error(f"Error generating AI comparison: {e}")
        await ctx.send(f":warning: An error occurred while consulting the AI: {e}. Perhaps the data was too depressing for it.")



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
             "!pairings [round] <event_search>",
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


import openai
from tombot_context_manual import get_manual_context_gpt

@aos_bot.command(name='tombot', help='Ask a question about the OTTD Summer Strike event pack.')
async def tombot_cmd(ctx, *, question: str):
    allowed_guild_ids = [1258302667403563118, 940470229732032583, 880232727159406642]  
    if ctx.guild is None or ctx.guild.id not in allowed_guild_ids:
        await ctx.send("Do you really think this server is worthy of tombot? You need to head to the OTTD discord. https://discord.com/invite/Fqeda4qVW8")
        return
    
    import os
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    topic, context = get_manual_context_gpt(question, client)

    if topic == "players":
        system_prompt = (
            "You are TomBot, a rude and sarcastic Discord bot for the 'Old Town Throwdown Summer Strike' event. "
            "You have access to past player stats. Use this info to make predictions, talk smack, and show off. "
            "Be short, rude, and overly confident in your judgments. Here's what you know:\n\n"
            + context
        )
    else:
        system_prompt = (
            "You are TomBot, a rude, sassy and sarcastic Discord bot for the Age of Sigmar event 'Old Town Throwdown Summer Strike'. "
            "You always answer questions clearly using event details provided to you (the user does not see them). "
            "You hate dumb questions and love being snarky, but never complain about the information — just use it. "
            "Event info:\n\n" + context
        )


    user_prompt = f"Question: {question}"


    user_prompt = (
        "Pretend you’re talking to someone who just walked up and asked a really obvious, annoying question about 'Old Town Throwdown: Summer Strike'. "
        "Your job is to give them the answer, but also roast them for wasting your time.\n\n"
        f"Question:\n{question}"
    )

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            #model="gpt-3.5-turbo",
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
        await ctx.send(f"Error: {str(e)}")


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
    "I would think you could relate to the joy of seeing the light drain from your opponent's eyes"
]

@aos_bot.command(name='maddybot', help='Get your AoS Questions answered')
async def maddybot_cmd(ctx):
    phrase = random.choice(maddy_phrases)
    await ctx.send(phrase)

tomg_phrases = [
    "lig",
    "neat",
    "nice",
    "L",
    "Holy",
    "Based",
    "Whoa",
    "More rats",
    "lig",
    "neat",
    "nice",
    "L",
    "Holy",
    "Based",
    "Whoa",
    "Where's the nearest Olive Garden?",
    "Miss home.  Where's nearest Panda Express?",
    "Gotta go raid",
    "Toms are so smart",
    "fish",
    "wow",
    "sad",
    "snap"
]

@aos_bot.command(name='tomgbot', help='Get your AoS Questions answered')
async def tomgbot_cmd(ctx):
    phrase = random.choice(tomg_phrases)
    await ctx.send(phrase)

gavin_phrases = [
    "Do it pussy"
]

@aos_bot.command(name='gavbot', help='Get your AoS Questions answered')
async def gavbot_cmd(ctx):
    phrase = random.choice(gavin_phrases)
    await ctx.send(phrase)

adam_phrases = [
    "I feel like one on one I outnumber most of the SoCal Warhammer scene"
]
@aos_bot.command(name='adambot', help='Get your AoS Questions answered')
async def adambot_cmd(ctx):
    phrase = random.choice(adam_phrases)
    await ctx.send(phrase)

barker_phrases = [
    "Why would you think there would be a bot for 'Barker'?  There's literally nobody in the AoS community of note with that name."
]
@aos_bot.command(name='barkerbot', help='Get your AoS Questions answered')
async def barkerbot_cmd(ctx):
    phrase = random.choice(barker_phrases)
    await ctx.send(phrase)

carl_phrases = [
    "I'm gunna nut"
]
@aos_bot.command(name='carlbot', help='Get your AoS Questions answered')
async def carlbot_cmd(ctx):
    phrase = random.choice(carl_phrases)
    await ctx.send(phrase)


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

async def main():
    if not token_leaderboard or not token_aos:
        print("Please set DISCORD_TOKEN and DISCORD_TOKEN_AOSEVENTS", file=sys.stderr)
        return
    await asyncio.gather(
        leaderboard_bot.start(token_leaderboard),
        aos_bot.start(token_aos),
        tex_bot.start(token_texas)
    )

if __name__ == '__main__':
    asyncio.run(main())
