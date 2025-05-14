import os
import aiohttp
import discord
from discord.ext import commands
import asyncio
import logging
import re
import random
from wordfreq import top_n_list

# Enable logging
logging.basicConfig(level=logging.INFO)

# Load environment variables for both bots
token_leaderboard = os.getenv('DISCORD_TOKEN')
token_aos = os.getenv('DISCORD_TOKEN_AOSEVENTS')
api_url = "https://aos-events.com/api/winrates"
LEADERBOARD_URL = 'https://aos-events.com/api/california_itc_scores'

# Shared settings
intents = discord.Intents.default()
intents.message_content = True

# Create two Bot instances
leaderboard_bot = commands.Bot(command_prefix='!', intents=intents, description="Cali Masters Leaderboard Bot")
aos_bot = commands.Bot(command_prefix='!', intents=intents, description="AoS Win Rates Bot")

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
    'idk': 'Idoneth Deepkin', 'idoneth': 'Idoneth Deepkin', 'deepkin': 'Idoneth Deepkin',
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
    lines = [f"Artifact Win Rates for {canonical} ({tf}):"]
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
    lines = [f"Trait Win Rates for {canonical} ({tf}):"]
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
    lines = [f"Formation Win Rates for {canonical} ({tf}):"]
    for itm in items:
        lines.append(f"{itm['formation']}: {itm['wins']}/{itm['games']} wins ({itm['win_rate_pct']:.2f}%)")
    lines.append('')
    lines.append('Source: https://aos-events.com')
    await send_lines(ctx, lines)
    
async def send_full_list(ctx, time_filter):
    data = await fetch_winrates(time_filter)
    items = [f for f in data.get('factions', []) if f['name'] not in EXCLUDE_FACTIONS]
    sorted_f = sorted(items, key=lambda f: (f['wins']/f['games'] if f['games'] else 0), reverse=True)
    lines = [f"AoS Faction Win Rates ({time_filter}) sorted:"]
    for f in sorted_f:
        pct = (f['wins']/f['games']*100) if f['games'] else 0
        emoji = EMOJI_MAP.get(f['name'], '')
        lines.append(f"{emoji} {f['name']}: {f['wins']}/{f['games']} ({pct:.2f}%)")
    lines += ['', 'Source: https://aos-events.com']
    await send_lines(ctx, lines)

async def send_single(ctx, key, tf):
    name = ALIAS_MAP[key]
    data = await fetch_winrates(tf)
    f = next((x for x in data.get('factions', []) if x['name'] == name), None)
    if not f:
        return await ctx.send(f"Faction '{name}' not found.")
    pct = (f['wins']/f['games']*100) if f['games'] else 0
    emoji = EMOJI_MAP.get(name, '')
    await ctx.send(f"{emoji} **{name}** ({tf}): {f['wins']}/{f['games']} ({pct:.2f}%)\nSource: https://aos-events.com")

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
