"""
Helpers for replying to slash-command interactions.

Slash commands must respond within 3 seconds; anything that hits the network
should `await interaction.response.defer()` first and then reply through
these helpers, which pick `response` or `followup` automatically.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Sequence

import discord

log = logging.getLogger(__name__)

MAX_LEN = 1900   # keep under Discord's 2000-char limit with room for code fences


async def send(interaction: discord.Interaction, content: str | None = None, **kwargs) -> discord.Message | None:
    """Reply to an interaction, whether or not it has already been responded to."""
    if interaction.response.is_done():
        return await interaction.followup.send(content, wait=True, **kwargs)
    await interaction.response.send_message(content, **kwargs)
    try:
        return await interaction.original_response()
    except discord.HTTPException:
        return None


async def warn(interaction: discord.Interaction, content: str) -> None:
    """User-facing validation error. Ephemeral when we still can be."""
    if interaction.response.is_done():
        await interaction.followup.send(content)
    else:
        await interaction.response.send_message(content, ephemeral=True)


async def send_lines(interaction: discord.Interaction, lines: Sequence[str]) -> None:
    """Send lines inside code blocks, splitting across messages as needed."""
    buf: list[str] = []
    count = 0
    for line in lines:
        ln = len(line) + 1
        if count + ln > MAX_LEN:
            await send(interaction, "```\n" + "\n".join(buf) + "\n```")
            buf, count = [line], ln
        else:
            buf.append(line)
            count += ln
    if buf:
        await send(interaction, "```\n" + "\n".join(buf) + "\n```")


async def send_files(interaction: discord.Interaction, files: list[discord.File]) -> None:
    """Discord allows 10 attachments per message."""
    for i in range(0, len(files), 10):
        await send(interaction, files=files[i:i + 10])


def truncate_content(text: str, max_len: int = 1800) -> str:
    """Trim text at line boundaries to <= max_len, appending a marker."""
    if len(text) <= max_len:
        return text
    out, count = [], 0
    for line in text.splitlines():
        ln = len(line) + 1
        if count + ln > max_len:
            out.append("...[truncated]")
            break
        out.append(line)
        count += ln
    return "\n".join(out)


# ── Event picker (shared by /standings, /standingsfull, /pairings) ──────────

OnPick = Callable[[discord.Interaction, dict], Awaitable[None]]


class EventSelect(discord.ui.Select):
    def __init__(self, events: list[dict], on_pick: OnPick):
        options = []
        for e in events[:25]:
            loc = e.get("formatted_address") or e.get("city") or ""
            label = f"{e['name']} ({loc})" if loc else e["name"]
            if len(label) > 100:
                label = label[:97] + "…"
            options.append(discord.SelectOption(label=label, value=e["id"]))
        super().__init__(placeholder="Select an event…", min_values=1, max_values=1, options=options)
        self.events = {e["id"]: e for e in events}
        self.on_pick = on_pick

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            await self.on_pick(interaction, self.events[self.values[0]])
        except Exception as e:
            log.exception("event picker callback failed")
            await interaction.followup.send(f":x: Error: {e}")
        self.view.stop()


class EventPickerView(discord.ui.View):
    def __init__(self, events: list[dict], on_pick: OnPick, *, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.add_item(EventSelect(events, on_pick))


async def pick_event(interaction: discord.Interaction, matches: list[dict], on_pick: OnPick) -> None:
    """Run on_pick directly if exactly one match, else show a dropdown."""
    if len(matches) == 1:
        await on_pick(interaction, matches[0])
        return
    await send(interaction, "Multiple events found — please pick one:",
               view=EventPickerView(matches, on_pick))
