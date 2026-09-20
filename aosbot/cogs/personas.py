"""
Joke / persona commands.

Slash:   /tomgbot /adambot /ajbot /ebot /jobot /tomtombot /tomtomtombot /vallis /maddybot
Message context menu (right-click a message → Apps):
         "Adjudicate"           – rate the post by its author
         "Rewrite as…"          – pick a persona (Noog, Jar Jar, Yoda, Noe, Orlando, …)
                                  and post an OpenAI rewrite of the message

Context menus receive the target message's content in the interaction payload,
so they work without the Message Content intent. Discord allows at most five
message context menus per app, which is why the rewrite bots share one.
"""

from __future__ import annotations

import logging
import random
from typing import Awaitable, Callable

import discord
from discord import app_commands
from discord.ext import commands

from gpt_people_bots import (
    jarjar_answer, noe_answer, noog_answer, orlando_answer,
    redcoat_answer, wallace_answer, yoda_answer,
)
from maddybot import get_maddy_preline, maddy_answer

from ..persona_data import (
    adam_phrases, aj_phrases, e_phrases, jo_phrases, maddy_phrases,
    tombot_phrase_weights, tomtom_phrases, tomtomtom_phrases, vallis_responses,
)
from ..reply import send, truncate_content

log = logging.getLogger(__name__)

Answerer = Callable[[discord.Message], Awaitable[str | None]]

# Label shown in the dropdown -> answer function. Delete a line to remove a persona.
REWRITE_PERSONAS: dict[str, Answerer] = {
    "Noogbot":     noog_answer,
    "Jar Jar bot": jarjar_answer,
    "Yodabot":     yoda_answer,
    "Noebot":      noe_answer,
    "Orlandobot":  orlando_answer,
    "Wallacebot":  wallace_answer,
    "Redcoatbot":  redcoat_answer,
}

ADJUDICATE_LINES = {
    "thommo": [
        "This was a clever and witty post.", "A stroke of genius, truly.", "Sharp and well-delivered.",
        "Smartly put — impressive.", "A shining example of wit.", "Both clever and amusing.",
    ],
    "rozkun": [
        "This was a dumb post.", "That was not your brightest moment.", "Pretty foolish, honestly.",
        "This didn’t age well.", "Not exactly a smart contribution.", "This was rather silly.",
    ],
    "artemacus": [
        "This was an overly wordy and articulate post.", "Verbose, yet strangely compelling.",
        "An ocean of words for a drop of meaning.", "Grandiose and articulate to a fault.",
        "A masterclass in over-explaining.", "Drenched in unnecessary eloquence.",
    ],
    "_default": [
        "This post was mediocre.", "Nothing to write home about.", "Utterly average.",
        "Neither here nor there.", "Decidedly unremarkable.", "Solidly… meh.",
    ],
}


class PersonaSelect(discord.ui.Select):
    def __init__(self, message: discord.Message):
        super().__init__(placeholder="Pick a persona…", min_values=1, max_values=1,
                         options=[discord.SelectOption(label=n) for n in REWRITE_PERSONAS])
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        name = self.values[0]
        await interaction.response.defer(thinking=True)          # new interaction → public reply
        try:
            reply = await REWRITE_PERSONAS[name](self.message)
        except Exception as e:
            log.exception("persona rewrite failed")
            return await interaction.followup.send(f":x: {name} error: {e}")
        if not reply:
            return await interaction.followup.send(":warning: That message had no readable text.")
        await interaction.followup.send(truncate_content(reply, 1900))
        self.view.stop()


class PersonaView(discord.ui.View):
    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(PersonaSelect(message))


class PersonasCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # context menus can't be defined as cog methods; register them by hand
        self.ctx_adjudicate = app_commands.ContextMenu(name="Adjudicate", callback=self.adjudicate)
        self.ctx_rewrite = app_commands.ContextMenu(name="Rewrite as…", callback=self.rewrite)
        bot.tree.add_command(self.ctx_adjudicate)
        bot.tree.add_command(self.ctx_rewrite)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_adjudicate.name, type=self.ctx_adjudicate.type)
        self.bot.tree.remove_command(self.ctx_rewrite.name, type=self.ctx_rewrite.type)

    # ── one-liners ──────────────────────────────────────────────────────────
    @app_commands.command(name="adambot", description="Get your AoS questions answered")
    async def adambot(self, interaction: discord.Interaction):
        await send(interaction, random.choice(adam_phrases))

    @app_commands.command(name="ajbot", description="Get your AoS questions answered")
    async def ajbot(self, interaction: discord.Interaction):
        await send(interaction, random.choice(aj_phrases))

    @app_commands.command(name="ebot", description="Get your AoS questions answered")
    async def ebot(self, interaction: discord.Interaction):
        await send(interaction, random.choice(e_phrases))

    @app_commands.command(name="jobot", description="Get your AoS questions answered")
    async def jobot(self, interaction: discord.Interaction):
        await send(interaction, random.choice(jo_phrases))

    @app_commands.command(name="tomtombot", description="Get your AoS questions answered")
    async def tomtombot(self, interaction: discord.Interaction):
        await send(interaction, random.choice(tomtom_phrases))

    @app_commands.command(name="tomtomtombot", description="Get your AoS questions answered")
    async def tomtomtombot(self, interaction: discord.Interaction):
        await send(interaction, random.choice(tomtomtom_phrases))

    @app_commands.command(name="tomgbot", description="Get your AoS questions answered")
    async def tomgbot(self, interaction: discord.Interaction):
        phrases, weights = zip(*tombot_phrase_weights)
        await send(interaction, random.choices(phrases, weights=weights, k=1)[0])

    # ── vallis ──────────────────────────────────────────────────────────────
    @app_commands.command(name="vallis", description="Vallis knows all")
    @app_commands.describe(topic="What do you want to know about?")
    @app_commands.choices(topic=[app_commands.Choice(name=k, value=k) for k in sorted(vallis_responses)])
    async def vallis(self, interaction: discord.Interaction, topic: str):
        await send(interaction, vallis_responses[topic])

    # ── maddy ───────────────────────────────────────────────────────────────
    @app_commands.command(name="maddybot", description="Ask Maddy an AoS unit question, or get a phrase")
    @app_commands.describe(question="Leave empty for a Maddy quip")
    async def maddybot(self, interaction: discord.Interaction, question: str | None = None):
        if not question or not question.strip():
            return await send(interaction, random.choice(maddy_phrases))
        await interaction.response.defer()
        try:
            await send(interaction, get_maddy_preline())
            ans = await maddy_answer(question.strip(), max_units=5, use_gpt_select=True)
            await send(interaction, truncate_content(ans, 1900))
        except Exception as e:
            log.exception("maddybot failed")
            await send(interaction, f":x: Maddy failed to answer: {e}")

    # ── context menus ───────────────────────────────────────────────────────
    async def adjudicate(self, interaction: discord.Interaction, message: discord.Message):
        lines = ADJUDICATE_LINES.get(message.author.name.lower(), ADJUDICATE_LINES["_default"])
        await interaction.response.send_message(random.choice(lines))

    async def rewrite(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_message("Rewrite that message as…", view=PersonaView(message),
                                                ephemeral=True)
