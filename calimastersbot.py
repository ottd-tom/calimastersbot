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

# Enable logging
logging.basicConfig(level=logging.INFO)

# Load environment variables for both bots
token_leaderboard = os.getenv('DISCORD_TOKEN')
token_aos = os.getenv('DISCORD_TOKEN_AOSEVENTS')
api_url = "https://aos-events.com"
LEADERBOARD_URL = 'https://aos-events.com/api/california_itc_scores'

# Shared settings
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Create two Bot instances
leaderboard_bot = commands.Bot(command_prefix='!', intents=intents, description="Cali Masters Leaderboard Bot")
aos_bot = commands.Bot(command_prefix='!', intents=intents, description="AoS Win Rates Bot")

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
    base = api_url.rstrip('/')
    url = f"{base if base.lower().endswith('winrates') else base + '/api/winrates'}?time={time_filter}"
    return await fetch_json(url)


async def fetch_enhancement(time_filter='all', rounds_filter='all'):
    base = api_url.rstrip('/')
    url = f"{base}/api/enhancement_winrates?time={time_filter}&rounds={rounds_filter}"
    return await fetch_json(url)

# ========== Leaderboard Bot Commands ==========
@leaderboard_bot.command(name='top8', help='Show the current Cali Masters top 8')
async def top8(ctx):
    data = await fetch_json(LEADERBOARD_URL)
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

    data = await fetch_json(LEADERBOARD_URL)
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

# ========== AoS Win Rates Bot Commands ==========
# Settings for AoS bot
TIME_FILTERS = ['all', 'recent', 'battlescroll']
EXCLUDE_FACTIONS = ['Beasts of Chaos', 'Bonesplitterz']
ALIAS_MAP = {
    'fec': 'Flesh-eater Courts', 'flesh-eater courts': 'Flesh-eater Courts',
    'idk': 'Idoneth Deepkin', 'idoneth': 'Idoneth Deepkin', 'deepkin': 'Idoneth Deepkin', 'fish': 'Idoneth Deepkin',
    'lrl': 'Lumineth Realm-lords', 'lumineth': 'Lumineth Realm-lords', 'realm-lords': 'Lumineth Realm-lords',
    'dot': 'Disciples of Tzeentch', 'tzeentch': 'Disciples of Tzeentch',
    'sons': 'Sons of Behemat', 'sob': 'Sons of Behemat',
    'trees': 'Sylvaneth', 'sylvaneth': 'Sylvaneth',
    'lizards': 'Seraphon', 'seraphon': 'Seraphon',
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

@aos_bot.command(name='winrates', aliases=['winrate'], help='!winrates [time]|[faction_alias] [time]')
async def winrates_cmd(ctx, arg: str = 'all', maybe_time: str = None):
    arg_lower = arg.lower()
    if arg_lower in TIME_FILTERS:
        await send_full_list(ctx, arg_lower)
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
    lines = [f"Artifact Win Rates for {canonical} ({label}):"]
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
    lines = [f"Trait Win Rates for {canonical} ({label}):"]
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
    lines = [f"Formation Win Rates for {canonical} ({label}):"]
    for itm in items:
        lines.append(f"{itm['formation']}: {itm['wins']}/{itm['games']} wins ({itm['win_rate_pct']:.2f}%)")
    lines.append('')
    lines.append('Source: https://aos-events.com')
    await send_lines(ctx, lines)

async def fetch_itc_placings(name: str):
    """Call your Flask API to get ITC placings for a given name."""
    base = api_url.rstrip('/')
    q = urllib.parse.quote(name)
    url = f"{base}/api/itc_placings?name={q}"
    return await fetch_json(url)

@aos_bot.command(name='itcrank', aliases=['crankit'], help='Show ITC placing and points for a player')
async def itcrank_cmd(ctx, *, name: str):
    name = name.strip()
    if not name:
        return await ctx.send("Usage: `!itcrank First [Last]`")
    try:
        data = await fetch_itc_placings(name)
    except Exception as e:
        return await ctx.send(f"Error fetching ITC data: {e}")
    if not data:
        return await ctx.send(f"No ITC placings found for **{name}**.")

    # Build a list of lines rather than one giant string
    lines = [f"**ITC Placings for “{name}”**"]
    for rec in data:
        fn = rec.get('first_name', '')
        ln = rec.get('last_name', '')
        placing   = rec.get('placing')
        points    = rec.get('itc_points')
        lines.append(f"{fn} {ln} — Placing: {placing}, Points: {points:.2f}")

    await send_lines(ctx, lines)

@aos_bot.command(
    name='whoisbetter',
    help='Compare two players by ITC placing. Usage: !whoisbetter <name1> <name2> OR !whoisbetter <name1> or <name2>'
)
async def whoisbetter_cmd(ctx, *, query: str):
    # Try “or” syntax first
    parts = re.split(r'\s+or\s+', query, flags=re.IGNORECASE)
    if len(parts) == 2:
        name1 = parts[0].strip()
        name2 = parts[1].strip()
    else:
        # Fallback: split into four tokens
        tokens = query.split()
        if len(tokens) < 4:
            return await ctx.send(
                "Usage: `!whoisbetter <first1> <last1> <first2> <last2>` "
                "or `!whoisbetter <name1> or <name2>`"
            )
        name1 = f"{tokens[0]} {tokens[1]}"
        name2 = f"{tokens[2]} {tokens[3]}"

    # Special cases
    if name1.lower() == "gareth thomas" or name2.lower() == "gareth thomas":
        return await ctx.send("Gareth Thomas is morally and intellectually superior")
    if name1.lower() == "team usa" or name2.lower() == "team usa":
        return await ctx.send(
            "🏆 Team USA are World Champions! 🏆 USA! USA! USA! (but "
            f"{name2 if name1.lower()=='team usa' else name1} is probably better in most other respects)"
        )
    if (name1.lower(), name2.lower()) == ("jeremy veysseire", "jeremy lefebvre"):
        return await ctx.send(
            "🏆 Technically Jeremy Lefebvre is best Jeremy due to being the only Jeremy to win at AoS worlds 🏆"
        )

    # Fetch ITC data
    try:
        data1 = await fetch_itc_placings(name1)
        data2 = await fetch_itc_placings(name2)
    except Exception as e:
        return await ctx.send(f"Error fetching ITC data: {e}")

    def best_placing(data):
        return None if not data else min(rec.get('placing', float('inf')) for rec in data)

    best1 = best_placing(data1)
    best2 = best_placing(data2)

    # Compare results
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


@aos_bot.command(name='hof', help='List Hall of Fame players (5+ wins) for a faction. Usage: !hof <faction_alias>')
async def hof(ctx, alias: str):
    lookup = alias.lower()
    canonical = ALIAS_MAP.get(lookup)
    if not canonical:
        return await ctx.send(f"Unknown faction '{alias}'. Available aliases: {', '.join(ALIAS_MAP.keys())}")

    # Fetch Hall of Fame entries
    url = f"{api_url.rstrip('/')}/api/five_win_players"
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
    url = f"{api_url.rstrip('/')}/api/winrates?time={tf}"
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

    # Build the output lines
    lines = [f"🏹 Unit Win-Rates for {canonical} ({tf}) 🏹"]
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



aos_bot.remove_command('help')
@aos_bot.command(name='help', help='List all AoS bot commands')
async def help_cmd(ctx):
    lines = ["**AoS Events Bot Commands**"]
    lines.append("!winrates [time_filter] - Full faction win rates")
    lines.append("!winrates <faction_alias> [time_filter] - Single faction win rate")
    lines.append("!artefacts <faction_alias> [time_filter] - Artifact win rates")
    lines.append("!traits <faction_alias> [time_filter] - Trait win rates")
    lines.append("!formations <faction_alias> [time_filter] - Formation win rates")
    lines.append("!units <faction_alias> [time_filter] - Unit win rates")
    lines.append("!hof <faction_alias> - 5+ wins for a faction")
    lines.append("!itcrank <player_name> - ITC placing and points")
    lines.append("")
    lines.append("Time filters: all (Since 2025/01/01), recent (Last 60 days), battlescroll (Since last battlescroll)")
    lines.append("")
    lines.append("Source: https://aos-events.com")
    await send_lines(ctx, lines)


@aos_bot.command(name='areyoumasonsdad', help='no help')
async def masonsdad(ctx):
    lines = ["Who knows, could be, could be.  Was a wild time.  Could be me, could be any of the other ten bots."]
    await send_lines(ctx, lines)

@aos_bot.command(name='servers', help='List all servers this bot is in')
async def servers(ctx):
    guilds = aos_bot.guilds
    if not guilds:
        return await ctx.send("I'm not in any servers!")
    lines = [f"• {g.name} (ID: {g.id})" for g in guilds]
    # Send as a code block to preserve formatting
    await ctx.send("```" + "\n".join(lines) + "```")

async def send_full_list(ctx, time_filter):
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
        aos_bot.start(token_aos)
    )

if __name__ == '__main__':
    asyncio.run(main())
