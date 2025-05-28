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
             "!standings <event_search>",
             "!standingsfull <event_search>",
             "!pairings [round] <event_search>",
             "!servers",
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
from tombot_context import get_relevant_context
from tombot_context_manual import get_manual_context_gpt

@aos_bot.command(name='tombot', help='Ask a question about the OTTD Roar in 24 event pack.')
async def tombot_cmd(ctx, *, question: str):
    import os
    from openai import OpenAI
    from tombot_context import get_relevant_context

    context = get_manual_context_gpt(question, client)

    system_prompt = (
        "You are TomBot, a rude and sarcastic Discord bot. You answer questions about the Age of Sigmar event "
        "'Old Town Throwdown: Roar in 24', taking place August 10–11, 2024 at Lake Forest Community Center. "
        "When users say things like 'the event', 'the tournament', or 'Roar', they mean this specific event. "
        "You hate dumb questions, but you *always* answer clearly using the provided context. "
        "Be brutally honest, cutting, and funny — but never skip the actual answer."
    )

    user_prompt = (
        f"Assume 'the event', 'this tournament', etc., refer to 'Old Town Throwdown: Roar in 24'.\n\n"
        f"Event Pack Context:\n{context}\n\n"
        f"Question:\n{question}"
    )

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
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
