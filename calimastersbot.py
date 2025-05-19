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
token_aos = os.getenv('DISCORD_TOKEN_AOSEVENTS')
token_texas = os.getenv('TEXAS_DISCORD_BOT')
API_URL = "https://aos-events.com"
CALI_URL = 'https://aos-events.com/api/california_itc_scores'
TEXAS_URL = 'https://aos-events.com/api/texas_itc_scores'
BCP_API_KEY   = os.getenv("BCP_API_KEY")        
CLIENT_ID     = os.getenv("BCP_CLIENT_ID")   
BASE_EVENT_URL = 'https://newprod-api.bestcoastpairings.com/v1/events'

# Shared settings
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Create two Bot instances
leaderboard_bot = commands.Bot(command_prefix='!', intents=intents, description="Cali Masters Leaderboard Bot")
aos_bot = commands.Bot(command_prefix='!', intents=intents, description="AoS Win Rates Bot")
tex_bot = commands.Bot(command_prefix='!', intents=intents, description="Texas Masters Leaderboard Bot")

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
    'Hedonites of Slaanesh': '🎵',
    'Cities of Sigmar': '🏙️',
    'Daughters of Khaine': '🩸',
    'Ogor Mawtribes': '🍖',
    'Slaves to Darkness': '⛓️',
    'Maggotkin of Nurgle': '🪱',
    'Ossiarch Bonereapers': '💀',
    'Ironjawz': '🔨',
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
               if key in (f"{rec['first_name']} {rec['last_name']}".lower(), rec['first_name'].lower(), rec['last_name'].lower())]
    if not matches:
        return await ctx.send(f"No player found matching `{query}`.")
    lines = []
    for rank_pos, rec in matches:
        total = sum(1 for k, v in rec.items() if pattern.match(k) and v)
        cnt = min(total, 4)
        lines.append(f"#{rank_pos} **{rec['first_name']} {rec['last_name']}** — {rec['top4_sum']} pts ({cnt} of 4)")
    await ctx.send("\n".join(lines))

@leaderboard_bot.command(name='ramon')
async def ramon(ctx):
    lines = [
        "It's ironic to me, I've always been able to relate to military people.",
        "Even though I'm a Rasta at heart, I've regularly had people ask me if I have been in the military,",
        "after seeing me work/perform so systematically.",
        "And although I've never served, I completely have more than enough PTSD to pass for the average veteran."
    ]
    await send_lines(ctx, lines)


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
               if key in (f"{rec['first_name']} {rec['last_name']}".lower(), rec['first_name'].lower(), rec['last_name'].lower())]
    if not matches:
        return await ctx.send(f"No player found matching `{query}`.")
    lines = []
    for rank_pos, rec in matches:
        total = sum(1 for k, v in rec.items() if pattern.match(k) and v)
        cnt = min(total, 5)
        lines.append(f"#{rank_pos} **{rec['first_name']} {rec['last_name']}** — {rec['top5_sum']} pts ({cnt} of 4)")
    await ctx.send("\n".join(lines))


# ========== AoS Win Rates Bot Commands ==========
# Settings for AoS bot
TIME_FILTERS = ['all', 'recent', 'battlescroll']
EXCLUDE_FACTIONS = ['Beasts of Chaos', 'Bonesplitterz']
ALIAS_MAP = {
    'fec': 'Flesh-eater Courts', 'flesh-eater courts': 'Flesh-eater Courts',
    'idk': 'Idoneth Deepkin', 'idoneth': 'Idoneth Deepkin', 'deepkin': 'Idoneth Deepkin', 'fish': 'Idoneth Deepkin',
    'lrl': 'Lumineth Realm-lords', 'lumineth': 'Lumineth Realm-lords', 'realm-lords': 'Lumineth Realm-lords', 'Lumineth Realm-Lords' : 'Lumineth Realm-lords',
    'dot': 'Disciples of Tzeentch', 'tzeentch': 'Disciples of Tzeentch',
    'sons': 'Sons of Behemat', 'sob': 'Sons of Behemat',
    'trees': 'Sylvaneth', 'sylvaneth': 'Sylvaneth',
    'Sera': 'Seraphon', 'lizards': 'Seraphon', 'seraphon': 'Seraphon',
    'sbgl': 'Soulblight Gravelords', 'soulblight' : 'Soulblight Gravelords', 'vampires': 'Soulblight Gravelords',
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
    """
    Given a faction full name (from JSON), return the shortest alias
    (upper-cased) whose canonical mapping (case-insensitive) matches it.
    Otherwise return the original full_name.
    """
    full_lower = full_name.lower()
    # pick all alias keys whose mapped canonical name matches (case-insensitive)
    candidates = [
        alias for alias, canon in ALIAS_MAP.items()
        if canon.lower() == full_lower
           # and exclude the trivial alias==full_name case
           and alias.lower() != full_lower
    ]
    if candidates:
        shortest = min(candidates, key=len)
        return shortest.upper()
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

@aos_bot.command(name='artefacts', aliases=['artefact','artifact','artifacts'], help='Get artifact winrates for a faction. Usage: !artefacts <faction_alias> [time]')
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
    lines.append('')
    lines.append('Source: https://aos-events.com')
    await send_lines(ctx, lines)

@aos_bot.command(name='traits', aliases=['trait'], help='Get trait winrates for a faction. Usage: !traits <faction_alias> [time]')
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
    lines.append('')
    lines.append('Source: https://aos-events.com')
    await send_lines(ctx, lines)

@aos_bot.command(name='formations', aliases=['formation'], help='Get formation winrates for a faction. Usage: !formations <faction_alias> [time]')
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
    lines.append('')
    lines.append('Source: https://aos-events.com')
    await send_lines(ctx, lines)


@aos_bot.command(name='hof', help='List Hall of Fame players (5+ wins) for a faction. Usage: !hof <faction_alias>')
async def hof(ctx, *, alias: str):
    lookup = alias.strip('"').lower()

    if lookup == "legions of nagash":
        return await ctx.send(f"Legions of Nagash are no longer legal, and as such do not have a Hall of Fame.  However, Gareth Thomas was the last winner of ITC LoN, so he is undoubtedly in the hall")
    
    canonical = ALIAS_MAP.get(lookup)
    if not canonical:
        return await ctx.send(f"Unknown faction '{alias}'. Available aliases: {', '.join(ALIAS_MAP.keys())}")

    # Fetch Hall of Fame entries
    url = f"{API_URL.rstrip('/')}/api/five_win_players"
    data = await fetch_json(url)
    entries = [e for e in data if e.get('faction') == canonical]

    if not entries:
        return await ctx.send(f"No Hall of Fame entries for {canonical}.")

    # Build output lines
    lines = [f"🏆 Hall of Fame for {canonical} 🏆"]
    for e in entries:
        date = e.get('event_date', '').split('T')[0]
        lines.append(f"{date} - {e.get('player_name')} at {e.get('event_name')} (Wins: {e.get('wins')})")

    # Add website link
    lines.append("")
    lines.append("For lists and more info: https://aos-events.com/faction_stats#hof")

    # Send as code blocks
    await send_lines(ctx, lines)

@aos_bot.command(
    name='units',
    help='List unit win-rates for a faction. Usage: !units <faction_alias> [time_filter]'
)
async def units_cmd(ctx, alias: str, time_filter: str = 'all'):
    lookup = alias.lower()
    canonical = ALIAS_MAP.get(lookup)
    if not canonical:
        return await ctx.send(
            f"Unknown faction '{alias}'. Available aliases: {', '.join(ALIAS_MAP.keys())}"
        )

    tf = time_filter.lower()
    if tf not in TIME_FILTERS:
        return await ctx.send(
            f"Invalid time filter '{time_filter}'. Choose from: {', '.join(TIME_FILTERS)}"
        )

    # Fetch the winrates payload
    url = f"{API_URL.rstrip('/')}/api/winrates?time={tf}"
    data = await fetch_json(url)

    # Filter units by faction
    units = [u for u in data.get('units', []) if u.get('faction') == canonical]
    if not units:
        return await ctx.send(f"No unit data for {canonical} ({tf}).")

    # Sort by win percentage descending
    def win_pct(u):
        w = u.get('wins', 0)
        g = u.get('games', 0)
        return (w / g) if g else 0

    units_sorted = sorted(units, key=win_pct, reverse=True)
    label = time_labels.get(tf, tf)
    # Build the output lines
    lines = [f"🏹 Unit Win-Rates for {canonical} ({label}) 🏹"]
    for u in units_sorted:
        wins = u.get('wins', 0)
        games = u.get('games', 0)
        pct = win_pct(u) * 100
        lines.append(f"{u['name']}: {wins}/{games} wins ({pct:.2f}%)")

    # Add link to more details
    lines.append("")
    lines.append("Full stats at: https://aos-events.com/faction_stats#units")

    # Send as code block
    await send_lines(ctx, lines)

@aos_bot.command(
    name='popularity',
    aliases=['pop'],
    help='List popularity stats. Usage: !pop [factions|manifestations|drops] [time_filter]'
)
async def popularity_cmd(ctx, arg: str = 'factions', maybe_time: str = 'all'):
    valid_cats = ['factions', 'manifestations', 'drops']
    time_filters = ['all', 'recent', 'battlescroll']

    arg_lower = arg.lower()
    if arg_lower in time_filters:
        category = 'factions'
        time_filter = arg_lower
        tf = time_filter
    elif arg_lower in valid_cats:
        category = arg_lower
        tf = maybe_time.lower()
        time_filter = tf if tf in time_filters else 'all'
    else:
        return await ctx.send(
            f"Invalid category or time filter '{arg}'.\n"
            f"Categories: {', '.join(valid_cats)}\n"
            f"Time filters: {', '.join(time_filters)}"
        )

    url = f"{API_URL.rstrip('/')}/api/popularity?time={time_filter}"
    data = await fetch_json(url)
    items = data.get(category, [])
    if not items:
        return await ctx.send(f"No popularity data for {category} ({time_filter}).")

    # Sort descending by games and compute percentages
    items_sorted = sorted(items, key=lambda x: x.get('games', 0), reverse=True)
    total_games = sum(it['games'] for it in items_sorted)
    label = time_labels.get(tf, tf)

    lines = [f"📊 Popularity for {category.capitalize()} ({label}):"]
    for it in items_sorted:
        games = it['games']
        pct = (games / total_games * 100) if total_games else 0
        prefix = (EMOJI_MAP.get(it['name'], '') + ' ') if category  == 'factions' else ''
        lines.append(f"{prefix}{it['name']}: {games} games ({pct:.2f}%)")

    lines.append("")
    lines.append("More info: https://aos-events.com/faction_stats#popularity")

    await send_lines(ctx, lines)

def extract_players(raw: dict):
    # try "active" first, then "data"
    if isinstance(raw, dict):
        if 'active' in raw and isinstance(raw['active'], list):
            return raw['active']
        if 'data' in raw and isinstance(raw['data'], list):
            return raw['data']
    return []

import discord
from discord.ext import commands
from datetime import datetime, timedelta

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
        async with session.get(f"{BASE_EVENT_URL}/{ev_id}/players", params={"placings":"true","limit":500}, headers=headers) as presp:
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
        async with session.get(f"{BASE_EVENT_URL}/{ev_id}/players", params={"placings":"true","limit":500}, headers=headers) as presp:
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


def _search_matches(events, query):
    q = query.lower()
    out = []
    for e in events:
        if e.get("teamEvent", False):
            continue
        name = e.get("name","...") or ""
        loc  = e.get("formatted_address","") or e.get("city","")
        if q in name.lower() or q in loc.lower():
            out.append(e)
    return out


class StandingsSelect(discord.ui.Select):
    def __init__(self, events, slim, ctx):
        # build up to 25 options, truncating any label >100 chars
        options = []
        for e in events:
            loc = e.get("formatted_address", e.get("city", ""))
            label = f"{e['name']} ({loc})"
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=e["id"]))

        super().__init__(
            placeholder="Select an event…",
            min_values=1,
            max_values=1,
            options=options
        )

        # save for the callback
        self.events = {e["id"]: e for e in events}
        self.slim   = slim
        self.ctx    = ctx

    async def callback(self, interaction: discord.Interaction):
        # 1) ACK the interaction so it doesn't time out
        await interaction.response.defer(thinking=True)

        # 2) Lookup the chosen event
        ev = self.events[self.values[0]]
        ev_name, ev_id = ev["name"], ev["id"]

        # 3) Fetch players JSON
        headers = {
            "Accept":      "application/json",
            "x-api-key":   BCP_API_KEY,
            "client-id":   CLIENT_ID,
            "User-Agent":  "AoSBot",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_EVENT_URL}/{ev_id}/players",
                params={"placings":"true","limit":500},
                headers=headers
            ) as presp:
                presp.raise_for_status()
                raw = await presp.json()

        players = extract_players(raw)
        if not players:
            return await interaction.followup.send(f":warning: No players found for `{ev_name}` ({ev_id}).")

        # 4) Build the lines list
        lines = [f"Standings for {ev_name} ({ev_id}):"]
        if self.slim:
            # ensure Wins exists
            first_metrics = [m["name"] for m in players[0].get("metrics", [])]
            if "Wins" not in first_metrics:
                return await interaction.followup.send(f":warning: No “Wins” metric in `{ev_name}` ({ev_id}).")
            header = "Place | Faction | Name                     | Wins"
            divider = "-" * len(header)
            lines += [header, divider]

            for p in players:
                placing = p["placing"]
                full_faction = p.get("faction",{}).get("name","")
                faction_alias = get_shortest_alias(full_faction)
                user = p["user"]
                name = f"{user['firstName']} {user['lastName']}"
                metric_map = {m["name"]:m["value"] for m in p["metrics"]}
                wins = metric_map.get("Wins","")
                lines.append(f"{placing:<5} | {faction_alias:<7} | {name:<24} | {wins:^4}")
        else:
            # full metrics
            header_fields = ["Place", "Name"] + [m["name"] for m in players[0]["metrics"]]
            header = " | ".join(header_fields)
            divider = "-" * len(header)
            lines += [header, divider]

            for p in players:
                placing = p["placing"]
                user = p["user"]
                name = f"{user['firstName']} {user['lastName']}"
                metric_map = {m["name"]:m["value"] for m in p["metrics"]}
                row = [str(placing), name] + [str(metric_map.get(col,"")) for col in header_fields[2:]]
                lines.append(" | ".join(row))

        # 5) Chunk & send via followup
        maxc = 1900
        buf, count = [], 0
        for line in lines:
            ln = len(line) + 1
            if count + ln > maxc:
                chunk = "\n".join(buf)
                await interaction.followup.send(f"```\n{chunk}\n```")
                buf, count = [line], ln
            else:
                buf.append(line)
                count += ln
        if buf:
            chunk = "\n".join(buf)
            await interaction.followup.send(f"```\n{chunk}\n```")

        # 6) Finally, clickable link
        await interaction.followup.send(
            f"View full placings: https://www.bestcoastpairings.com/event/{ev_id}?active_tab=placings"
        )

        # stop the view so the menu disappears
        self.view.stop()



class StandingsView(discord.ui.View):
    def __init__(self, events, slim, ctx):
        super().__init__(timeout=60)
        self.add_item(StandingsSelect(events, slim, ctx))


@aos_bot.command(name='standingsfull')
async def standings_full_cmd(ctx, *, query: str):
    query = query.strip()
    if len(query) < 4:
        return await ctx.send(":warning: Please use at least 4 characters for your search.")
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    params = {
        "limit": 100,
        "sortAscending": "true",
        "sortKey": "eventDate",
        "startDate": week_ago.isoformat(),
        "endDate": today.isoformat(),
        "gameType": "4",
    }
    headers = {
        'Accept': 'application/json',
        'x-api-key': BCP_API_KEY,
        'client-id': CLIENT_ID,
        'User-Agent': 'AoSBot',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_EVENT_URL, params=params, headers=headers) as resp:
            resp.raise_for_status()
            events = (await resp.json()).get('data', [])
    matches = _search_matches(events, query)
    if not matches:
        return await ctx.send(f":mag: No AoS events this week matching `{query}`.")
    if len(matches) == 1:
        return await do_standings_full(ctx, matches[0])
    await ctx.send("Multiple events found—please pick one:", view=StandingsView(matches, slim=False, ctx=ctx))


@aos_bot.command(name='standings')
async def standings_slim_cmd(ctx, *, query: str):
    query = query.strip()
    if len(query) < 4:
        return await ctx.send(":warning: Please use at least 4 characters for your search.")
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    params = {
        "limit": 100,
        "sortAscending": "true",
        "sortKey": "eventDate",
        "startDate": week_ago.isoformat(),
        "endDate": today.isoformat(),
        "gameType": "4",
    }
    headers = {
        'Accept': 'application/json',
        'x-api-key': BCP_API_KEY,
        'client-id': CLIENT_ID,
        'User-Agent': 'AoSBot',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_EVENT_URL, params=params, headers=headers) as resp:
            resp.raise_for_status()
            events = (await resp.json()).get('data', [])
    matches = _search_matches(events, query)
    if not matches:
        return await ctx.send(f":mag: No AoS events this week matching `{query}`.")
    if len(matches) == 1:
        return await do_standings_slim(ctx, matches[0])
    await ctx.send("Multiple events found—please pick one:", view=StandingsView(matches, slim=True, ctx=ctx))


# ─── ITC STANDINGS ────────────────────────────────────────────────────────────
ITC_LEAGUE_ID = "vldWOTsjXggj"
ITC_REGION_ID = "61vXu5vli4"

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
        "limit":         500,
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
    if name1.lower()=="team usa" or name2.lower()=="team usa":
        other = name2 if name1.lower()=="team usa" else name1
        return await ctx.send(f"🏆 Team USA are World Champions! 🏆 But {other} is probably better in most other respects.")

    # helper to fetch & filter
    async def fetch_for(name):
        headers = {
            'Accept':'application/json',
            'x-api-key':BCP_API_KEY,
            'client-id':CLIENT_ID,
            'User-Agent':'AoS-WhoIsBetter-Bot',
        }
        params = {
            "limit":         500,
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



aos_bot.remove_command('help')
@aos_bot.command(name='help', help='List all AoS bot commands')
async def help_cmd(ctx):
    lines = ["**AoS Events Bot Commands**"]
    lines.append("!winrates [time_filter] - Full faction win rates")
    lines.append("!winrates <faction_alias> [time_filter] - Single faction win rate")
    lines.append("!popularity [time_filter] - Faction popularity")
    lines.append("!popularity manifestations [time_filter] - Manifestation popularity")
    lines.append("!artefacts <faction_alias> [time_filter] - Artifact win rates")
    lines.append("!traits <faction_alias> [time_filter] - Trait win rates")
    lines.append("!formations <faction_alias> [time_filter] - Formation win rates")
    lines.append("!units <faction_alias> [time_filter] - Unit win rates")
    lines.append("!hof <faction_alias> - 5+ wins for a faction")
    lines.append("!itcrank <player_name> - ITC placing and points")
    lines.append("!itcstandings <faction_alias> - ITC current top 10")
    lines.append("!standings <event_search> - Current standings at event")
    lines.append("!standingsfull <event_search> - Full standings info")
    lines.append("")
    lines.append("Time filters: all (Since 2025/01/01), recent (Last 60 days), battlescroll (Since last battlescroll)")
    lines.append("")
    lines.append("Source: https://aos-events.com")
    await send_lines(ctx, lines)


@aos_bot.command(name='servers', help='List all servers this bot is in')
async def servers(ctx):
    guilds = aos_bot.guilds
    count = len(guilds)
    if not guilds:
        return await ctx.send("I'm not in any servers!")
    # Build numbered list with total count in the title
    lines = [f"Servers I'm in ({count}):"]
    for idx, g in enumerate(guilds, start=1):
        lines.append(f"{idx}. {g.name} (ID: {g.id})")
    # Send as a code block to preserve formatting
    await ctx.send("```" + "\n".join(lines) + "```")

async def send_full_winrates(ctx, time_filter):
    data = await fetch_winrates(time_filter)
    items = [f for f in data.get('factions', []) if f['name'] not in ['Beasts of Chaos','Bonesplitterz']]
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
    chunks = []
    buf = []
    count = 0
    maxc = 1900
    for line in lines:
        ln = len(line) + 1
        if count + ln > maxc:
            chunks.append('\n'.join(buf))
            buf = [line]
            count = ln
        else:
            buf.append(line)
            count += ln
    if buf:
        chunks.append('\n'.join(buf))
    for c in chunks:
        await ctx.send(f"```\n{c}\n```")

# ========== Runner ==========
async def main():
    if not token_leaderboard or not token_aos:
        print("Please set DISCORD_TOKEN_LEADERBOARD and DISCORD_TOKEN_AOS environment variables.")
        return
    await asyncio.gather(
        leaderboard_bot.start(token_leaderboard),
        aos_bot.start(token_aos),
        tex_bot.start(token_texas)
    )

if __name__ == '__main__':
    asyncio.run(main())
