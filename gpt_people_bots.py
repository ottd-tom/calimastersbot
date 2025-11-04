import discord
from typing import Optional
import random
import openai  


async def _get_target_message(ctx) -> Optional[discord.Message]:
    """
    Prefer the message this command replied to; otherwise use the one
    immediately above in the same channel/thread.
    """
    ref = getattr(ctx.message, "reference", None)
    if ref:
        # If Discord already resolved the reference, use it; otherwise fetch.
        if getattr(ref, "resolved", None) and isinstance(ref.resolved, discord.Message):
            return ref.resolved
        if getattr(ref, "message_id", None):
            try:
                return await ctx.channel.fetch_message(ref.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass  # fall back to history

    # Fallback: previous message in this channel/thread
    msgs = [m async for m in ctx.channel.history(limit=2)]
    return msgs[1] if len(msgs) >= 2 else None


async def noog_answer(target: discord.Message) -> Optional[str]:
    """
    Build a 'dumber' off-point reply to the given message.
    Returns the text reply, or None if no readable text.
    """
    prev_text = (getattr(target, "content", "") or "").strip()

    # If no text, try a small text attachment.
    if not prev_text and getattr(target, "attachments", None):
        for att in target.attachments:
            if (getattr(att, "size", 0) or 0) <= 200_000 and getattr(att, "content_type", "") and "text" in att.content_type:
                try:
                    data = await att.read()
                    prev_text = data.decode("utf-8", errors="replace")[:4000]
                    break
                except Exception:
                    pass

    if not prev_text:
        return None

    if random.random() < 0.2:
        system_prompt = (
            "You are NoogBot. You repeat what someone else said, but in a dumber way, "
            "often missing the point. Keep it short, a bit confused, and kind of wrong. "
            "Do not explain what you are doing. Use plain ASCII only. Write as though you're typing casually from a mobile phone: "
            "- keep sentences short, "
            "- punctuation light, "
            "- sometimes skip capitalization, "
            "- use occasional typos/autocorrect quirks, "
            "- but keep it natural and not unreadable. "
            "Avoid sounding like a PC keyboard essay; it should feel quick and mobile-typed. "
            "Also, now and then try to slip in a tangential side note that you are the assistant Captain "
            "(or sometimes 'assistant to the Captain') of Team America. Keep that aside short and subtle."
        )
    else:
        system_prompt = (
            "You are NoogBot. You repeat what someone else said, but in a dumber way, "
            "often missing the point. Keep it short, a bit confused, and kind of wrong. "
            "Do not explain what you are doing. Use plain ASCII only. Write as though you're typing casually from a mobile phone: "
            "- keep sentences short, "
            "- punctuation light, "
            "- sometimes skip capitalization, "
            "- use occasional typos/autocorrect quirks, "
            "- but keep it natural and not unreadable. "
            "Avoid sounding like a PC keyboard essay; it should feel quick and mobile-typed. "
        )

    user_prompt = (
        "Rephrase this so it sounds dumber and slightly off the point. Keep it brief.\n\n"
        f"TEXT:\n{prev_text}"
    )

 


    resp = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        max_tokens=200,
    )
    reply = (resp.choices[0].message["content"] or "").strip()

    return reply or None


async def jarjar_answer(target: discord.Message) -> Optional[str]:
    """
    Build a jarjar reply
    Returns the text reply, or None if no readable text.
    """
    prev_text = (getattr(target, "content", "") or "").strip()

    # If no text, try a small text attachment.
    if not prev_text and getattr(target, "attachments", None):
        for att in target.attachments:
            if (getattr(att, "size", 0) or 0) <= 200_000 and getattr(att, "content_type", "") and "text" in att.content_type:
                try:
                    data = await att.read()
                    prev_text = data.decode("utf-8", errors="replace")[:4000]
                    break
                except Exception:
                    pass

    if not prev_text:
        return None

    system_prompt = (
        "You are JarJarBot. You rewrite messages in a Jar Jar Binks-like voice (Gungan-style speech) "
        "without quoting or imitating specific lines from the films. Keep outputs short (1-2 sentences), "
        "slightly confused and off-point. Use plain ASCII only.\n\n"
        "Style guide:\n"
        "- Start with \"Meesa\", \"Yousa\", \"Okieday\", or similar sometimes.\n"
        "- Use Gungan grammar: \"Meesa think\", \"Yousa sayin\", \"Dis\", \"Dat\", \"Bombad\".\n"
        "- Sprinkle mild Jar Jar-isms: \"How wude!\", \"Uh-oh\", \"mesa clumsy\", but not every time.\n"
        "- Keep punctuation light; lowercase is ok; a few typos are ok.\n"
        "- Do not add facts; do not mention Star Wars; no emojis.\n"
        "- Stay friendly and silly, not insulting or offensive."
    )

    user_prompt = (
        "Rewrite the text below so it sounds like a Jar Jar Binks-style take: "
        "Do not add new info or names. Keep to 1-2 sentences, ASCII only.\n\n"
        f"TEXT:\n{prev_text}"
    )


    resp = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        max_tokens=200,
    )
    reply = (resp.choices[0].message["content"] or "").strip()

    return reply or None

import random
import re
from typing import Optional
import discord
import openai

# Heuristics for names
_NAME_WORD = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b")
_MENTION = re.compile(r"@([A-Za-z0-9_\.]+)")

# Plausible-sounding but invented facts (keep harmless, non-medical, non-political)
_REALISH_FACTS = [
    "there was a controlled study in 2019 showing a 12 percent error rate for that",
    "industry surveys put the failure rate near 1 in 7 when you do it that way",
    "benchmarks usually drop about 8 to 10 percent under real load",
    "most teams end up reverting this after a quarter due to maintenance drift",
    "the standard guidance is to avoid that pattern past 3 units of scale",
    "latency almost always doubles once you add a second dependency hop",
    "postmortems show this path causes 30 to 40 percent of incidents",
    "the default settings bias the result; reviewers flagged that last year",
    "retests typically show the effect disappears when you remove caching",
    "audits found the baseline assumptions weren’t reproducible across sites",
    "conversion usually falls once you add that extra step in the flow",
    "cold starts mask the real cost here; warm runs tell a different story",
    "the sample size is too small; confidence collapses once you rerun it",
    "the vendor doc actually warns against combining those two options",
    "most shops deprecate this because it creates silent edge cases",
    "a dry run shows the variance balloons as soon as inputs shift a little",
    "QA reports keep noting regressions tied to that exact tweak",
    "the error bars swamp the signal; it only looks good on a pretty chart",
    "capacity planning models treat that as an anti-pattern for good reason",
    "you can get a quick win, but it burns you the moment traffic spikes",
]

# Short, mild insults (1–2 words), non-profane, non-targeted
_INSULTS = [
    "rookie move", "amateur", "clueless", "sloppy", "naive", "messy",
    "paper-thin", "wishful", "half-baked", "wobbly", "shaky logic",
    "weak take", "off-base", "confused", "not serious"
]

def _pick_name(text: str) -> Optional[str]:
    m = _MENTION.search(text)
    if m:
        return "@" + m.group(1)
    words = list(_NAME_WORD.finditer(text))
    if words:
        for w in words:
            if w.start() > 0:
                return w.group(1)
        return words[0].group(1)
    return None

def _sanitize_ascii(s: str) -> str:
    # force ASCII, remove emojis/non-ascii, collapse multiple exclamations
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"!{2,}", "!", s)
    return s

def _ensure_disagree_fact_insult(base: str) -> str:
    t = base.strip()

    # Ensure strong disagreement (without teen style)
    if not re.search(r"\b(no|nah|nope|wrong|disagree)\b", t.lower()):
        t = ("no. " + t) if t else "no."

    # Add a short insult (always include one)
    insult = random.choice(_INSULTS)
    if not t.endswith((".", "!", "?")):
        t += "."
    t += " " + insult + "."

    # Ensure a realistic-sounding (but false) supporting fact
    if not re.search(r"\b(study|survey|benchmarks?|audits?|reports?|guidance|postmortems?|retests?|qa|vendor|variance|capacity)\b", t.lower()):
        fact = random.choice(_REALISH_FACTS)
        t += " " + fact + "."

    return t

async def noe_answer(target: discord.Message) -> Optional[str]:
    """
    Vehemently disagree + realistic-sounding fabricated support.
    Adds a short insult (1-2 words).
    40% chance: 'i like <Name> tho they bought me a soda' if a name is detected.
    40% chance: gripe about 'Corsairs'.
    ASCII only. No emoji. No teeny tone.
    """
    prev_text = (getattr(target, "content", "") or "").strip()

    # If no text, try a small text attachment.
    if not prev_text and getattr(target, "attachments", None):
        for att in target.attachments:
            if (getattr(att, "size", 0) or 0) <= 200_000 and getattr(att, "content_type", "") and "text" in att.content_type:
                try:
                    data = await att.read()
                    prev_text = data.decode("utf-8", errors="replace")[:4000]
                    break
                except Exception:
                    pass

    if not prev_text:
        return None

    name_for_aside = _pick_name(prev_text)

    system_prompt = (
        "You are NoeBot. Always vehemently DISAGREE with what was said. "
        "Back it up with a realistic-sounding (but fabricated) supporting fact. "
        "Style: plain ASCII, concise, professional-snarky, not teenager, no emoji, no double exclamation. "
        "Keep sentences short; light punctuation; occasional lowercase ok; readable. "
        "No slurs, threats, medical/legal advice, or harmful real-world claims."
    )
    user_prompt = "Disagree strongly and add a plausible supporting fact. Keep it brief.\n\nTEXT:\n" + prev_text

    resp = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.9,
        max_tokens=160,
    )
    reply = (resp.choices[0].message["content"] or "").strip()

    # Guarantee core behavior
    reply = _ensure_disagree_fact_insult(reply)

    # 40% soda aside if a name is present
    if name_for_aside and random.random() < 0.4:
        if not reply.endswith((".", "!", "?")):
            reply += "."
        reply += f" i like {name_for_aside} tho they bought me a soda."

    # 40% Corsairs gripe
    if random.random() < 0.4:
        if not reply.endswith((".", "!", "?")):
            reply += "."
        reply += " and i hate Corsairs."

    # Final sanitation
    reply = _sanitize_ascii(reply)

    # Keep it reasonably short
    if len(reply) > 400:
        reply = reply[:380].rstrip() + "..."

    return reply or None


