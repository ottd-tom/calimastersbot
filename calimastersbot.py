import os
import discord
from discord.ext import commands
import aiohttp

intents = discord.Intents.default()
intents.message_content = True   # so the bot can read message content for prefix commands

# 2) Pass intents into Bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Replace with your actual API URL
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
    
@bot.command(name='rank', help='Show current rank & score for a specific player')
async def rank(ctx, *, query: str):
    
    if query.strip().lower() == 'corsairs':
    return await ctx.send('utter trash')
    
    """Usage: !rank <player name>"""
    async with aiohttp.ClientSession() as session:
        async with session.get(LEADERBOARD_URL) as resp:
            if resp.status != 200:
                return await ctx.send(f"Error fetching leaderboard (HTTP {resp.status})")
            data = await resp.json()

    # case-insensitive match on full name, first or last
    matches = []
    q = query.strip().lower()
    for idx, rec in enumerate(data, start=1):
        full = f"{rec['first_name']} {rec['last_name']}".lower()
        if q == full or q == rec['first_name'].lower() or q == rec['last_name'].lower():
            matches.append((idx, rec))
    if not matches:
        return await ctx.send(f"No player found matching `{query}`.")

    # if multiple matches (e.g. same last name), list them all
    lines = []
    for rank, rec in matches:
        name  = f"{rec['first_name']} {rec['last_name']}"
        score = rec['top4_sum']
        lines.append(f"#{rank}  **{name}** — {score} pts")
    await ctx.send("\n".join(lines))

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Please set the DISCORD_TOKEN environment variable.")
        exit(1)
    bot.run(TOKEN)
