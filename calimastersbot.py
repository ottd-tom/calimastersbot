import os
import discord
from discord.ext import commands
import aiohttp
import re
import random
from wordfreq import top_n_list

intents = discord.Intents.default()
intents.message_content = True   # so the bot can read message content for prefix commands

bot = commands.Bot(command_prefix='!', intents=intents)

LEADERBOARD_URL = 'https://aos-events.com/api/california_itc_scores'

@bot.command(name='top8', help='Show the current Cali Masters top 8')
async def top8(ctx):
    # Fetch the leaderboard
    async with aiohttp.ClientSession() as session:
        async with session.get(LEADERBOARD_URL) as resp:
            if resp.status != 200:
                return await ctx.send(f"Error fetching leaderboard (HTTP {resp.status})")
            data = await resp.json()

    # Build the top 8 message
    top8 = data[:8]
    if not top8:
        return await ctx.send("No data available right now.")
    lines = ["**🏆 Cali Masters Top 8 🏆**"]
    for i, rec in enumerate(top8, start=1):
        name = f"{rec['first_name']} {rec['last_name']}"
        score = rec['top4_sum']
        lines.append(f"{i}. **{name}** — {score} pts")
    await ctx.send("\n".join(lines))

COMMON_WORDS = top_n_list("en", n_top=20000)
WORDS_BY_LETTER = {
    ch: [w.capitalize() for w in COMMON_WORDS if w.startswith(ch)]
    for ch in "abcdefghijklmnopqrstuvwxyz"
}

def random_acronym(letters: str) -> str:
    parts = []
    for ch in letters.lower():
        bucket = WORDS_BY_LETTER.get(ch)
        if bucket:
            parts.append(random.choice(bucket))
        else:
            parts.append(ch.upper())
    return " ".join(parts)

@bot.command(name='rank', help='Show current rank, score, and event count for a specific player')
async def rank(ctx, *, query: str):
    """Usage: !rank <player name>"""

    # Special case:
    if query.strip().lower() == 'corsairs':
        return await ctx.send('utter trash')

    if query.strip().upper() == 'TSD':
        expansion = random_acronym('TSD')
        return await ctx.send(f"`TSD` stands for: **{expansion}**")
    
    # Fetch leaderboard
    async with aiohttp.ClientSession() as session:
        async with session.get(LEADERBOARD_URL) as resp:
            if resp.status != 200:
                return await ctx.send(f"Error fetching leaderboard (HTTP {resp.status})")
            data = await resp.json()

    # Find matches
    q = query.strip().lower()
    matches = []
    for idx, rec in enumerate(data, start=1):
        full = f"{rec['first_name']} {rec['last_name']}".lower()
        if q == full or q == rec['first_name'].lower() or q == rec['last_name'].lower():
            matches.append((idx, rec))

    if not matches:
        return await ctx.send(f"No player found matching `{query}`.")

    # Prepare response lines
    id_pattern = re.compile(r'^event_(\d+)_id$')
    lines = []
    for rank, rec in matches:
        name  = f"{rec['first_name']} {rec['last_name']}"
        score = rec['top4_sum']
        # Count how many non-empty event_i_id fields
        total_events = sum(
            1 for k, v in rec.items()
            if id_pattern.match(k) and v
        )
        # Cap at 4 for display
        display_count = min(total_events, 4)
        lines.append(f"#{rank}  **{name}** — {score} pts ({display_count} of 4)")

    await ctx.send("\n".join(lines))

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Please set the DISCORD_TOKEN environment variable.")
        exit(1)
    bot.run(TOKEN)
