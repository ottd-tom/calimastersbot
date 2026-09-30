"""
The Barker "BCP sucks" auto-reply.

This is the only thing left in the project that reads message content, so it
lives on the Cali Masters bot — a single small server, well under Discord's
review threshold, where the Message Content intent can simply be switched on in
the Developer Portal.

Do NOT add this cog to the AoS Events bot: that app has no privileged intents,
and requesting message content there would just stop it connecting.

Detection lives here too. Everything funnels into normalise(), which flattens a
message down to bare lowercase letters, and mentions_bcp(), which looks for the
target strings in the result. Each defence is a separate step, so when Barker
invents something new it's usually one entry in a dict.

Covered:
  punctuation / spacing    B.C.P    b-c-p    b _ c _ p
  unicode lookalikes       ＢＣＰ   ⒷⒸⓅ   𝐁𝐂𝐏   Cyrillic С, Greek Ρ
  zero-width padding       B<ZWSP>C<ZWSP>P
  combining accents        B̈C̈P̈
  enclosed letters         🇧🇨🇵   🅱🅲🅿   🄑🄒🄟
  emoji rebus              🐝 🌊 🫛   (bee / sea / pea)
  custom server emoji      <:bee:123> <:peapod:456>
  leetspeak                8CP   |3CP
  spelled out              bee sea pea, bee see pee
  expansions               best coast pairings, bestcoast, bcpairings
  reversal                 PCB  (optional, on by default)
"""

from __future__ import annotations

import logging
import re
import unicodedata

import discord
from discord.ext import commands

from ..config import (
    BARKER_CATCH_INITIALS, BARKER_GUILD_ID, BARKER_REPLY, BARKER_USER_ID,
)

log = logging.getLogger(__name__)


# ── What we're looking for, once everything is flattened ─────────────────────
TARGETS = ("bcp", "bestcoastpairings", "bestcoast", "bcpairings")
REVERSED_TARGETS = ("pcb",)

# ── Step 1: custom Discord emoji -> their name ───────────────────────────────
_CUSTOM_EMOJI = re.compile(r"<a?:([A-Za-z0-9_]+):\d+>")

# ── Step 2: characters that carry no meaning ─────────────────────────────────
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad\u034f"), None)

# ── Step 3: homoglyphs NFKD won't fix ────────────────────────────────────────
_HOMOGLYPHS = str.maketrans({
    # Cyrillic
    "а": "a", "в": "b", "с": "c", "е": "e", "к": "k", "м": "m", "н": "h",
    "о": "o", "р": "p", "т": "t", "х": "x", "у": "y", "ѕ": "s",
    "А": "a", "В": "b", "С": "c", "Е": "e", "К": "k", "М": "m", "Н": "h",
    "О": "o", "Р": "p", "Т": "t", "Х": "x", "У": "y", "Ѕ": "s",
    # Greek
    "α": "a", "β": "b", "ϲ": "c", "ε": "e", "ο": "o", "ρ": "p", "τ": "t",
    "Α": "a", "Β": "b", "Ϲ": "c", "Ε": "e", "Ο": "o", "Ρ": "p", "Τ": "t",
    # misc lookalikes
    "ƅ": "b", "ɓ": "b", "ʙ": "b", "ᴄ": "c", "ϛ": "c", "ρ": "p", "ᴘ": "p",
    "©": "c", "¢": "c", "₱": "p", "þ": "p", "ß": "b",
})

# ── Step 4: emoji and symbols that stand in for letters ──────────────────────
_EMOJI_LETTERS = {
    # B
    "🐝": "b", "🅱": "b", "🇧": "b", "🔯": "b", "🫑": "b",
    # C — anything sea-ish, moon-ish or C-shaped
    "🌊": "c", "🌀": "c", "🇨": "c", "🌙": "c", "🌜": "c", "🌛": "c",
    "☪": "c", "🥐": "c", "🍌": "c", "🌊": "c", "💠": "c", "🔵": "c",
    # P — anything pea-ish or parking
    "🫛": "p", "🇵": "p", "🅿": "p", "🟢": "p", "🫘": "p", "🍐": "p",
}

# ── Step 5: words that spell a letter ────────────────────────────────────────
_WORD_LETTERS = {
    "bee": "b", "bees": "b", "buzz": "b", "beeee": "b",
    "sea": "c", "see": "c", "cee": "c", "seas": "c", "sees": "c",
    "pea": "p", "peas": "p", "pee": "p", "peapod": "p", "pod": "p",
}

# ── Step 6: leetspeak ────────────────────────────────────────────────────────
_LEET_MULTI = [("|3", "b"), ("13", "b"), ("|>", "p"), ("|*", "p"),
               ("|°", "p"), ("(_", "c"), ("[3", "b")]
_LEET_SINGLE = str.maketrans({"8": "b", "6": "b", "0": "o", "1": "i", "3": "e",
                              "4": "a", "5": "s", "7": "t", "9": "g", "@": "a",
                              "$": "s", "!": "i"})


# Enclosed-letter blocks NFKD leaves alone, mapped by codepoint arithmetic:
# regional indicators 🇦-🇿, squared 🄰-🅉, negative squared 🅰-🆉, parenthesised 🄐-🄩.
_ENCLOSED_RANGES = ((0x1F1E6, 0x1F1FF), (0x1F130, 0x1F149),
                    (0x1F170, 0x1F189), (0x1F110, 0x1F129))


def _enclosed_letter(ch: str) -> str | None:
    cp = ord(ch)
    for start, end in _ENCLOSED_RANGES:
        if start <= cp <= end:
            return chr(ord("a") + cp - start)
    return None


def normalise(text: str) -> str:
    """Flatten a message to bare lowercase letters for matching."""
    if not text:
        return ""

    # custom emoji -> their name, so <:bee:123> becomes "bee"
    text = _CUSTOM_EMOJI.sub(r" \1 ", text)

    # emoji/symbol stand-ins, before we strip non-letters
    out = []
    for ch in text:
        if ch in _EMOJI_LETTERS:
            out.append(f" {_EMOJI_LETTERS[ch]} ")
        elif (enc := _enclosed_letter(ch)) is not None:
            out.append(f" {enc} ")
        else:
            out.append(ch)
    text = "".join(out)

    text = text.translate(_INVISIBLE)
    text = text.lower()
    text = text.translate(_HOMOGLYPHS)

    # multi-char leet before single-char
    for pattern, repl in _LEET_MULTI:
        text = text.replace(pattern, repl)

    # NFKD flattens fullwidth, circled, squared and math-styled letters, then
    # we drop the combining marks it separates out
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()

    text = text.translate(_LEET_SINGLE)

    # word-for-letter substitution, on whole words only
    def _word(m: re.Match) -> str:
        return _WORD_LETTERS.get(m.group(0), m.group(0))

    text = re.sub(r"[a-z]+", _word, text)

    # everything that isn't a letter is decoration
    return re.sub(r"[^a-z]", "", text)


def mentions_bcp(text: str, *, catch_reversed: bool = True,
                 catch_initials: bool = False) -> bool:
    """True if the message refers to BCP, however it's disguised.

    catch_initials also fires on acrostics ("Bring Coffee Please"). Off by
    default — it's the one rule that will catch innocent messages.
    """
    flat = normalise(text)
    if any(t in flat for t in TARGETS):
        return True
    if catch_reversed and any(t in flat for t in REVERSED_TARGETS):
        return True
    if catch_initials:
        initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", text))
        if "bcp" in initials.lower():
            return True
    return False


# ── Cog ──────────────────────────────────────────────────────────────────────

class BarkerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._warned = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.guild.id != BARKER_GUILD_ID or message.author.id != BARKER_USER_ID:
            return

        content = message.content or ""
        if not content.strip():
            # An attachment-only or sticker-only message is legitimately empty;
            # so is every message if the intent is off. Warn once either way.
            if not self._warned:
                self._warned = True
                log.warning("Barker: message content is empty. Enable the Message "
                            "Content intent for this app in the Developer Portal.")
            return

        if mentions_bcp(content, catch_initials=BARKER_CATCH_INITIALS):
            log.info("Barker: matched %r (normalised: %r)", content[:120], normalise(content)[:120])
            try:
                await message.channel.send(BARKER_REPLY)
            except discord.HTTPException:
                log.exception("Barker: failed to send reply")
