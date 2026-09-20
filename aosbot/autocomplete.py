"""Autocomplete callbacks for slash-command options."""

from __future__ import annotations

import discord
from discord import app_commands

from .config import ALIAS_MAP, FACTIONS


async def faction_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Suggest canonical faction names; matches on aliases too (typing 'dok' finds Daughters of Khaine)."""
    cur = current.lower().strip()
    if not cur:
        hits = FACTIONS
    else:
        hits = {canon for alias, canon in ALIAS_MAP.items() if cur in alias}
        hits = sorted(hits, key=lambda f: (not f.lower().startswith(cur), f))
    return [app_commands.Choice(name=f, value=f) for f in list(hits)[:25]]
