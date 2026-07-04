"""
aos_sentiment.py
================

Faction sentiment-index command for the AoS bot.

Collects messages from each faction channel over a time range, scores fan
sentiment with OpenAI, and writes the results to Postgres (AOS_EVENTS_DB_URL).
Designed to drop into calimastersbot.py without touching the rest of the file.

Wiring it in (two lines in calimastersbot.py)
---------------------------------------------
At the top of calimastersbot.py:

    from aos_sentiment import register as register_sentiment

Inside main(), BEFORE the asyncio.gather(...) that launches the bots:

    register_sentiment(aos_bot, get_db_pool, ALIAS_MAP, EMOJI_MAP)

That reuses your existing pool + faction maps; nothing else changes.

Config you must set
-------------------
SENTIMENT_GUILD_ID below: the server whose channels hold one-per-faction chat.
Optionally SENTIMENT_CATEGORY_NAME to restrict to a single category.
SENTIMENT_TZ: timezone for interpreting/displaying dates you type (default UTC).
    e.g. SENTIMENT_TZ="America/Los_Angeles"

Channels are matched to factions by name via your ALIAS_MAP (e.g. a channel
called "daughters-of-khaine", "dok", or "#dok-chat" all resolve correctly). For
any oddly-named channels, add them to FACTION_CHANNEL_OVERRIDES.

Usage in Discord
----------------
    !sentiment                          all factions, last 48h (default window)
    !sentiment 24                       all factions, last 24h
    !sentiment dok                      one faction, last 48h
    !sentiment dok 72                   one faction, last 72h
    !sentiment from:2026-06-25 to:2026-06-28
                                        all factions, explicit date range
    !sentiment dok from:2026-06-25T18:00 to:2026-06-26T06:00
                                        one faction, explicit datetime range
    !sentiment from:2026-06-25          start date given, end defaults to now

Dates accept YYYY-MM-DD or YYYY-MM-DDTHH:MM (no spaces). Naive times are read in
SENTIMENT_TZ. Aliases for the keywords: from/start/since and to/end/until.
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
import openai  # legacy SDK, same as the rest of the bot

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
SENTIMENT_GUILD_ID = 615105941079326721  # <-- set this
SENTIMENT_CATEGORY_NAME = os.getenv("SENTIMENT_CATEGORY_NAME")  # None = all text channels
SENTIMENT_TZ_NAME = os.getenv("SENTIMENT_TZ", "UTC")            # how to read typed dates
SENTIMENT_TZ = ZoneInfo(SENTIMENT_TZ_NAME)

DEFAULT_LOOKBACK_HOURS = 48
BATCH_SIZE = 40                    # messages per OpenAI call
MAX_MESSAGES_PER_CHANNEL = 600     # cost guardrail per channel (oldest-first within range)
MAX_MSG_CHARS = 500                # truncate any one message (e.g. pasted army lists)
CHANNEL_CONCURRENCY = 4            # channels processed in parallel
MODEL = "gpt-4o-mini"

# channel_id (int) OR exact channel name (str) -> canonical faction name
FACTION_CHANNEL_OVERRIDES: dict = {
    # 123456789012345678: "Stormcast Eternals",
    # "general-chaos-chat": "Slaves to Darkness",
}

FROM_KEYS = {"from", "start", "since"}
TO_KEYS = {"to", "end", "until"}

CLASSIFY_SYSTEM = (
    "You analyse fan reactions in a Warhammer: Age of Sigmar community. Classify "
    "each message's feeling toward the faction or game as positive, neutral, or "
    "negative. Banter, sarcasm and memes are common, so judge the underlying "
    "sentiment, not surface tone. Every message goes in exactly one bucket and the "
    "three counts must sum to the number of messages. Also extract up to 5 short "
    "recurring themes, e.g. 'points increase', 'love the new models', 'rules "
    "confusion', 'underpowered'. "
    'Respond with ONLY a JSON object: '
    '{"positive": int, "neutral": int, "negative": int, "themes": [str, ...]}'
)


# ----------------------------------------------------------------------------
# Date parsing
# ----------------------------------------------------------------------------
def _parse_dt(text: str) -> datetime:
    """Parse a user-supplied date/datetime into an aware UTC datetime.

    Accepts YYYY-MM-DD, YYYY-MM-DDTHH:MM[:SS], optional trailing Z. Naive values
    are interpreted in SENTIMENT_TZ.
    """
    s = text.strip().replace("/", "-")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        raise ValueError(
            f"Couldn't parse '{text}'. Use e.g. 2026-06-25 or 2026-06-25T14:30."
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SENTIMENT_TZ)
    return dt.astimezone(timezone.utc)


def _split_kw(token: str):
    """If token is `keyword:value` or `keyword=value` for a known keyword,
    return (keyword, value); else (None, None). Splits only on the keyword
    prefix so colons inside the value (e.g. a time) are preserved."""
    low = token.lower()
    for kw in FROM_KEYS | TO_KEYS:
        for sep in (":", "="):
            prefix = kw + sep
            if low.startswith(prefix):
                return kw, token[len(prefix):]
    return None, None


def _fmt_local(dt: datetime) -> str:
    return dt.astimezone(SENTIMENT_TZ).strftime("%Y-%m-%d %H:%M")


# ----------------------------------------------------------------------------
# OpenAI helpers (legacy SDK, async)
# ----------------------------------------------------------------------------
def _parse_json(raw: str) -> dict:
    """Best-effort JSON extraction from a model reply (handles ``` fences)."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


async def _classify_batch(messages: list[str]) -> tuple[int, int, int, list[str]]:
    numbered = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(messages))
    resp = await openai.ChatCompletion.acreate(
        model=MODEL,
        temperature=0,
        max_tokens=400,
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": f"{len(messages)} messages:\n\n{numbered}"},
        ],
    )
    data = _parse_json(resp.choices[0].message.content or "")
    pos = int(data.get("positive", 0) or 0)
    neu = int(data.get("neutral", 0) or 0)
    neg = int(data.get("negative", 0) or 0)
    themes = [str(t).strip().lower() for t in (data.get("themes") or []) if str(t).strip()]
    return pos, neu, neg, themes[:5]


async def _summarise(faction: str, themes: list[str], score: float) -> str:
    try:
        resp = await openai.ChatCompletion.acreate(
            model=MODEL,
            temperature=0.3,
            max_tokens=160,
            messages=[
                {"role": "system", "content": "Write 2-3 plain sentences on how "
                 "fans feel, grounded in the themes. Neutral, specific tone."},
                {"role": "user", "content": f"Faction: {faction}\n"
                 f"Net sentiment: {score:+.2f} (-1 to +1)\nThemes: {themes}"},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        log.exception("summary failed for %s", faction)
        return ""


# ----------------------------------------------------------------------------
# Faction <-> channel resolution (reuses your ALIAS_MAP)
# ----------------------------------------------------------------------------
def _normalize(s: str) -> str:
    s = s.lower().replace("_", " ").replace("-", " ")
    s = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in s)
    return " ".join(s.split())


def _resolve_faction_channels(guild: discord.Guild, alias_map: dict) -> dict:
    """Return {canonical_faction_name: TextChannel} for channels we can match."""
    if SENTIMENT_CATEGORY_NAME:
        category = discord.utils.get(guild.categories, name=SENTIMENT_CATEGORY_NAME)
        channels = category.text_channels if category else []
    else:
        channels = guild.text_channels

    norm_index = {_normalize(k): v for k, v in alias_map.items()}
    out: dict = {}
    for ch in channels:
        canon = FACTION_CHANNEL_OVERRIDES.get(ch.id) or FACTION_CHANNEL_OVERRIDES.get(ch.name)
        if not canon:
            norm = _normalize(ch.name)
            canon = norm_index.get(norm)
            if not canon:
                for tok in norm.split():
                    if tok in norm_index:
                        canon = norm_index[tok]
                        break
        if canon and canon not in out:
            out[canon] = ch
    return out


# ----------------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------------
async def _ensure_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS faction_sentiment (
                id            SERIAL PRIMARY KEY,
                faction       TEXT NOT NULL,
                collected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                window_hours  INT NOT NULL,
                message_count INT NOT NULL,
                positive      INT NOT NULL,
                neutral       INT NOT NULL,
                negative      INT NOT NULL,
                score         DOUBLE PRECISION NOT NULL,
                themes        JSONB NOT NULL DEFAULT '[]',
                summary       TEXT
            );
        """)
        # migrate existing tables to carry the explicit window bounds
        await conn.execute(
            "ALTER TABLE faction_sentiment ADD COLUMN IF NOT EXISTS window_start TIMESTAMPTZ;")
        await conn.execute(
            "ALTER TABLE faction_sentiment ADD COLUMN IF NOT EXISTS window_end   TIMESTAMPTZ;")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_faction_sentiment_faction_time
                ON faction_sentiment (faction, collected_at DESC);
        """)


async def _store_result(pool, r: dict, start: datetime, end: datetime):
    window_hours = max(1, int(round((end - start).total_seconds() / 3600)))
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO faction_sentiment
                (faction, window_hours, message_count, positive, neutral,
                 negative, score, themes, summary, window_start, window_end)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11)
        """, r["faction"], window_hours, r["volume"], r["positive"], r["neutral"],
             r["negative"], r["score"], json.dumps(r["themes"]), r["summary"],
             start, end)


# ----------------------------------------------------------------------------
# Core analysis for one channel
# ----------------------------------------------------------------------------
async def _analyze_channel(faction: str, channel: discord.TextChannel,
                           start: datetime, end: datetime):
    contents: list[str] = []
    async for msg in channel.history(after=start, before=end, limit=None, oldest_first=True):
        if msg.author.bot:
            continue
        text = (msg.content or "").strip()
        if text:
            contents.append(text[:MAX_MSG_CHARS])
        if len(contents) >= MAX_MESSAGES_PER_CHANNEL:
            break

    if not contents:
        return None

    pos = neu = neg = 0
    themes: list[str] = []
    for i in range(0, len(contents), BATCH_SIZE):
        p, n, g, th = await _classify_batch(contents[i:i + BATCH_SIZE])
        pos += p
        neu += n
        neg += g
        themes.extend(th)

    total = pos + neu + neg or 1
    score = (pos - neg) / total
    top_themes = list(dict.fromkeys(themes))[:5]
    summary = await _summarise(faction, top_themes, score)

    return {
        "faction": faction,
        "volume": len(contents),
        "positive": pos,
        "neutral": neu,
        "negative": neg,
        "score": score,
        "themes": top_themes,
        "summary": summary,
    }


def _emoji(score: float) -> str:
    if score >= 0.3:
        return "\U0001F7E2"
    if score > 0.05:
        return "\U0001F642"
    if score < -0.3:
        return "\U0001F534"
    if score < -0.05:
        return "\U0001F641"
    return "\U0001F610"


# ----------------------------------------------------------------------------
# Command registration
# ----------------------------------------------------------------------------
def register(bot, get_db_pool, alias_map: dict, emoji_map: dict):
    """Attach the !sentiment command to `bot`, injecting the bot's own
    DB-pool getter and faction maps so we don't duplicate them."""

    @bot.command(
        name="sentiment",
        help="Score faction fan sentiment over a time range and save to DB. "
             "Usage: !sentiment [faction] [hours] | "
             "!sentiment [faction] from:YYYY-MM-DD to:YYYY-MM-DD",
    )
    async def sentiment(ctx, *args):
        hours = None
        start_arg = end_arg = None
        faction_arg = None
        for a in args:
            kw, val = _split_kw(a)
            if kw in FROM_KEYS and val:
                start_arg = val
            elif kw in TO_KEYS and val:
                end_arg = val
            elif a.isdigit():
                hours = max(1, int(a))
            else:
                faction_arg = a

        # resolve the collection window
        now = datetime.now(timezone.utc)
        try:
            if start_arg or end_arg:
                end_dt = _parse_dt(end_arg) if end_arg else now
                start_dt = (_parse_dt(start_arg) if start_arg
                            else end_dt - timedelta(hours=DEFAULT_LOOKBACK_HOURS))
            else:
                h = hours if hours is not None else DEFAULT_LOOKBACK_HOURS
                end_dt, start_dt = now, now - timedelta(hours=h)
        except ValueError as e:
            return await ctx.send(f":warning: {e}")

        if start_dt >= end_dt:
            return await ctx.send(":warning: Start must be before end.")

        span_label = f"{_fmt_local(start_dt)} -> {_fmt_local(end_dt)} {SENTIMENT_TZ_NAME}"

        guild = bot.get_guild(SENTIMENT_GUILD_ID) if SENTIMENT_GUILD_ID else ctx.guild
        if guild is None:
            return await ctx.send(":warning: SENTIMENT_GUILD_ID is not set or the "
                                  "bot isn't in that server.")

        channel_map = _resolve_faction_channels(guild, alias_map)
        if not channel_map:
            return await ctx.send(":warning: Couldn't match any channels to factions. "
                                  "Check SENTIMENT_GUILD_ID / category, or add "
                                  "FACTION_CHANNEL_OVERRIDES.")

        if faction_arg:
            canon = alias_map.get(faction_arg.lower())
            if not canon:
                return await ctx.send(f":warning: Unknown faction '{faction_arg}'.")
            if canon not in channel_map:
                return await ctx.send(f":warning: No channel found for **{canon}** "
                                      f"in that server.")
            targets = {canon: channel_map[canon]}
        else:
            targets = channel_map

        status = await ctx.send(
            f":hourglass: Analysing **{len(targets)}** faction"
            f"{'s' if len(targets) != 1 else ''} for {span_label}…"
        )

        try:
            pool = await get_db_pool()
            await _ensure_table(pool)
        except Exception as e:
            return await status.edit(content=f":x: Database error: {e}")

        sem = asyncio.Semaphore(CHANNEL_CONCURRENCY)
        results: list[dict] = []
        failures: list[str] = []

        async def worker(fac, chan):
            async with sem:
                try:
                    r = await _analyze_channel(fac, chan, start_dt, end_dt)
                    if not r:
                        return
                    await _store_result(pool, r, start_dt, end_dt)
                    results.append(r)
                except discord.Forbidden:
                    failures.append(f"{fac} (no read access)")
                except Exception as e:
                    log.exception("sentiment failed for %s", fac)
                    failures.append(f"{fac} ({type(e).__name__})")

        await asyncio.gather(*(worker(f, c) for f, c in targets.items()))

        if not results:
            note = f"\nFailed: {', '.join(failures)}" if failures else ""
            return await status.edit(
                content=f":warning: No messages found in {span_label}.{note}")

        results.sort(key=lambda r: r["score"], reverse=True)
        lines = []
        for r in results:
            em = emoji_map.get(r["faction"], "")
            lines.append(
                f"{_emoji(r['score'])} {em} **{r['faction']}** `{r['score']:+.2f}` "
                f"· {r['volume']} msgs ({r['positive']}+/{r['neutral']}~/{r['negative']}-)"
            )

        embed = discord.Embed(
            title=f"Faction sentiment — {span_label}",
            description="\n".join(lines)[:4096],
            color=0x5865F2,
        )
        embed.set_footer(text=f"Saved {len(results)} row(s) to faction_sentiment · "
                              "score = (pos − neg) / total")
        if failures:
            embed.add_field(name="Skipped", value=", ".join(failures)[:1024], inline=False)

        await status.edit(content=":white_check_mark: Done — saved to the database.")
        await ctx.send(embed=embed)

        if faction_arg and results and results[0]["summary"]:
            await ctx.send(f"**{results[0]['faction']}** — {results[0]['summary']}")

    return sentiment
