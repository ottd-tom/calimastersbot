"""
Shared configuration for all bots: environment variables, Discord IDs,
faction lookup tables and the scion roster.

Nothing in here touches Discord or the network.
"""

from __future__ import annotations

import os

# ── Tokens / keys ────────────────────────────────────────────────────────────
TOKEN_CALI      = os.getenv("DISCORD_TOKEN")
TOKEN_AOS       = os.getenv("DISCORD_TOKEN_AOSEVENTS")
TOKEN_TEXAS     = os.getenv("TEXAS_DISCORD_BOT")
TOKEN_SENTIMENT = os.getenv("DISCORD_TOKEN_SENTIMENT")     # new, standalone sentiment bot

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
BCP_API_KEY     = os.getenv("BCP_API_KEY")
BCP_CLIENT_ID   = os.getenv("BCP_CLIENT_ID")

# Optional: a guild ID to copy slash commands to on startup so they appear
# instantly while testing (global sync can take up to an hour to propagate).
DEV_GUILD_ID = int(os.getenv("DEV_GUILD_ID", "0")) or None

# ── URLs ─────────────────────────────────────────────────────────────────────
API_URL        = "https://aos-events.com"
CALI_URL       = f"{API_URL}/api/california_itc_scores"
TEXAS_URL      = f"{API_URL}/api/texas_itc_scores"
BCP_BASE       = "https://newprod-api.bestcoastpairings.com/v1"
BASE_EVENT_URL = f"{BCP_BASE}/events"

ITC_LEAGUE_ID = "RtgcexBzqjCM"
ITC_REGION_ID = "61vXu5vli4"

# League IDs per year (used by /playerwr)
LEAGUE_YEARS = {
    2026: "RtgcexBzqjCM",
    2025: "vldWOTsjXggj",
    2024: "PHGDLQY41V",
    2023: "2F20J0M34C",
    2022: "23qDprPABN",
    # 2021: 'HyXfJt4g6P',
}
CURRENT_LEAGUE_YEAR = 2026

# ── Discord IDs ──────────────────────────────────────────────────────────────
THOMMO_USER_ID = 199725130337878017

CORSAIR_SERVER_ID  = 1071183737024434336
CORSAIR_CHANNEL_ID = 1350184533349367882

SOCAL_AOS_GUILD_ID = 803881553108795413
EVENT_CHANNEL_ID   = 1213278301154447420

AOS_COACH_SERVER_ID      = 615105941079326721
TOURN_RESULTS_CHANNEL_ID = 769134467805216829
BOT_ACTIONS_CHANNEL_ID   = 706084206631190528

# ── Time filters ─────────────────────────────────────────────────────────────
TIME_FILTERS = ["all", "current", "recent", "battlescroll"]
TIME_LABELS = {
    "all":          "Since 2025/01/01",
    "current":      "Last 14 days",
    "recent":       "Last 60 days",
    "battlescroll": "Since last battlescroll",
}

# ── Factions ─────────────────────────────────────────────────────────────────
EXCLUDE_FACTIONS = ["Beasts of Chaos", "Bonesplitterz"]

EMOJI_MAP = {
    "Flesh-eater Courts":    "🦴",
    "Idoneth Deepkin":       "🌊",
    "Lumineth Realm-lords":  "💡",
    "Disciples of Tzeentch": "🔮",
    "Sons of Behemat":       "🦶",
    "Sylvaneth":             "🌳",
    "Seraphon":              "🦎",
    "Soulblight Gravelords": "🪦",
    "Blades of Khorne":      "🔥",
    "Stormcast Eternals":    "⚡",
    "Hedonites of Slaanesh": "🎵",
    "Cities of Sigmar":      "🏙️",
    "Daughters of Khaine":   "🐍",
    "Ogor Mawtribes":        "🍖",
    "Slaves to Darkness":    "⛓️",
    "Maggotkin of Nurgle":   "🪱",
    "Ossiarch Bonereapers":  "💀",
    "Ironjawz":              "🐖",
    "Kharadron Overlords":   "⚓",
    "Nighthaunt":            "👻",
    "Skaven":                "🐀",
    "Kruleboyz":             "👺",
    "Fyreslayers":           "🪓",
    "Gloomspite Gitz":       "🍄",
    "Helsmiths of Hashut":   "🎩",
}

ALIAS_MAP: dict[str, str] = {
    "fec": "Flesh-eater Courts",
    "idk": "Idoneth Deepkin", "idoneth": "Idoneth Deepkin", "deepkin": "Idoneth Deepkin", "fish": "Idoneth Deepkin",
    "lrl": "Lumineth Realm-lords", "lumineth": "Lumineth Realm-lords", "realm-lords": "Lumineth Realm-lords",
    "dot": "Disciples of Tzeentch", "tzeentch": "Disciples of Tzeentch", "chickens": "Disciples of Tzeentch", "birds": "Disciples of Tzeentch",
    "sons": "Sons of Behemat", "sob": "Sons of Behemat", "giants": "Sons of Behemat",
    "trees": "Sylvaneth",
    "sera": "Seraphon", "lizards": "Seraphon",
    "sbgl": "Soulblight Gravelords", "soulblight": "Soulblight Gravelords", "vampires": "Soulblight Gravelords",
    "bok": "Blades of Khorne", "khorne": "Blades of Khorne",
    "sce": "Stormcast Eternals", "stormcast": "Stormcast Eternals",
    "hos": "Hedonites of Slaanesh", "slaanesh": "Hedonites of Slaanesh",
    "cos": "Cities of Sigmar", "cities": "Cities of Sigmar",
    "dok": "Daughters of Khaine", "daughters": "Daughters of Khaine",
    "ogors": "Ogor Mawtribes", "mawtribes": "Ogor Mawtribes",
    "std": "Slaves to Darkness", "slaves": "Slaves to Darkness", "s2d": "Slaves to Darkness",
    "mon": "Maggotkin of Nurgle", "nurgle": "Maggotkin of Nurgle",
    "obr": "Ossiarch Bonereapers",
    "ij": "Ironjawz",
    "ko": "Kharadron Overlords",
    "nh": "Nighthaunt", "ghosts": "Nighthaunt",
    "rats": "Skaven",
    "kb": "Kruleboyz", "kbz": "Kruleboyz",
    "fs": "Fyreslayers",
    "gitz": "Gloomspite Gitz",
    "hoh": "Helsmiths of Hashut", "helsmiths": "Helsmiths of Hashut", "chorfs": "Helsmiths of Hashut",
}
# every canonical name is also its own (lower-case) alias
for _full in list(EMOJI_MAP):
    ALIAS_MAP[_full.lower()] = _full

FACTIONS: list[str] = sorted(EMOJI_MAP)          # canonical names, alphabetical

ALLIANCE_COLORS = {
    "Order":       "#0d6efd",
    "Chaos":       "#dc3545",
    "Death":       "#6f42c1",
    "Destruction": "#198754",
}
FACTION_ALLIANCE = {f: a for a, facs in {
    "Order":       ["Cities of Sigmar", "Daughters of Khaine", "Fyreslayers", "Idoneth Deepkin",
                    "Kharadron Overlords", "Lumineth Realm-lords", "Seraphon", "Stormcast Eternals", "Sylvaneth"],
    "Chaos":       ["Blades of Khorne", "Disciples of Tzeentch", "Hedonites of Slaanesh",
                    "Maggotkin of Nurgle", "Skaven", "Slaves to Darkness", "Helsmiths of Hashut"],
    "Death":       ["Flesh-eater Courts", "Nighthaunt", "Ossiarch Bonereapers", "Soulblight Gravelords"],
    "Destruction": ["Gloomspite Gitz", "Ironjawz", "Kruleboyz", "Ogor Mawtribes", "Sons of Behemat"],
}.items() for f in facs}


def resolve_faction(text: str | None) -> str | None:
    """Alias or full name -> canonical faction name, or None."""
    if not text:
        return None
    return ALIAS_MAP.get(text.strip().strip('"').lower())


def shortest_alias(full_name: str) -> str:
    """'Daughters of Khaine' -> 'DOK'. Falls back to the full name."""
    full_lower = full_name.lower()
    candidates = [a for a, c in ALIAS_MAP.items() if c.lower() == full_lower and a != full_lower]
    return min(candidates, key=len).upper() if candidates else full_name


def faction_colour(canonical: str) -> str | None:
    return ALLIANCE_COLORS.get(FACTION_ALLIANCE.get(canonical, ""))


# ── Scion tracker roster ─────────────────────────────────────────────────────
# Fill this in with `/scionid <name>`. Key = BCP userId, value = display name.
SCIONS: dict[str, str] = {
    "AQJEPFL9X9": "Brian Horton",
    "ZAdKiz9Koi": "Tom Guan",
    "KWH5QP65BC": "E Pryor",
    "KN49AJT661": "Adam Beautement",
    "yzOjNlI0zo": "Kyle Calip",
    "fZ7CI3Kh4k": "Greg Brewer",
    "H1HUGJ6LKX": "Ivan Blanco",
    "H6ADLP5H39": "Franz Ocampo",
    "1QY8G7178X": "Jo Cooper",
    "EGX7KCMPJP": "Steven Molina",
    "HyHvB43YdS": "Ben Boardman",
}

SCION_LOOKBACK_DAYS    = 2
SCION_LOOKAHEAD_DAYS   = 1
SCION_MAX_ROUNDS       = 8
SCION_CONCURRENCY      = 5
SCION_SKIP_TEAM_EVENTS = True
SCION_CACHE_TTL        = 60      # seconds
