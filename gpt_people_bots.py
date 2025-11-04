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

# Plausible-sounding but invented facts (harmless domains)
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
    "audits found the baseline assumptions were not reproducible across sites",
    "conversion usually falls once you add that extra step in the flow",
    "cold starts mask the real cost here; warm runs tell a different story",
    "the sample size is too small; confidence collapses once you rerun it",
    "the vendor doc actually warns against combining those two options",
    "most shops deprecate this because it creates silent edge cases",
    "a dry run shows the variance spikes as soon as inputs shift a little",
    "qa reports keep noting regressions tied to that exact tweak",
    "the error bars swamp the signal; it only looks good on a pretty chart",
    "capacity planning models treat that as an anti-pattern for good reason",
    "you get a quick win, then it burns you the moment traffic spikes",
]

# Edgy but safe short insults (1–2 words)
_INSULTS = [
    "cope", "cringe", "mid", "try harder", "skill issue", "paper tiger",
    "cheap take", "brain fog", "delusional", "weak sauce", "imaginary win",
    "low effort", "wishful", "hollow", "nice theory"
]

# Edge-lord openers
_OPENERS = [
    "no.", "hard no.", "cool story. still wrong.", "nah.", "pass.",
    "incorrect.", "that is not it.", "not even close.", "nope."
]

# AoS units to randomly call for nerfs (ASCII-safe)
_AOS_UNITS = [
    "maw-krusha", "nagash", "morathi", "skarbrand", "archaon",
    "lord kroak", "teclis", "belakor", "varanguard", "krondspine",
    "stormdrake guard", "fulminators", "longstrikes", "grave guard",
    "glutos", "thanquol", "necromancer", "blightkings", "saurus warriors",
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
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"!{2,}", "!", s)
    return s

def _edge_style_disagree() -> str:
    return random.choice(_OPENERS)

def _ensure_disagree_fact_insult(base: str) -> str:
    t = base.strip()
    if not t or not re.search(r"\b(no|nah|nope|wrong|disagree|incorrect)\b", t.lower()):
        t = _edge_style_disagree()

    insult = random.choice(_INSULTS)
    if not t.endswith((".", "!", "?")):
        t += "."
    t += " " + insult + "."

    if not re.search(r"\b(study|survey|benchmark|audit|report|guidance|postmortem|retest|qa|vendor|variance|capacity|sample size|confidence|latency|incidents)\b", t.lower()):
        fact = random.choice(_REALISH_FACTS)
        t += " " + fact + "."

    t = t.lower()
    t = re.sub(r"[.]{3,}", "..", t)
    t = re.sub(r"\?{2,}", "?", t)
    return t

async def noe_answer(target: discord.Message) -> Optional[str]:
    """
    Edge-lord NoeBot for AoS:
    - vehement disagreement
    - plausible fabricated support
    - one short insult
    - 40%: 'i like <Name> tho they bought me a soda' if a name is detected
    - 40%: gripe about 'corsairs'
    - 40%: either call for a random AoS unit nerf OR say stormcast eternals need a buff
    - ASCII only, no emoji, no '!!'
    - curt, lowercase, fragmented
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
        "you are noebot. edge-lord tone. always DISAGREE hard. "
        "be curt, cynical, lowercase, fragmented. plain ascii. "
        "back it with a realistic-sounding but fabricated supporting fact. "
        "add one short insult (1-2 words). no emoji. no '!!'. "
        "no slurs, no threats, no medical/legal advice, no real-world harm."
    )
    user_prompt = "disagree hard, add a plausible fabricated fact. keep it brief.\n\ntext:\n" + prev_text

    resp = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.92,
        max_tokens=150,
    )
    reply = (resp.choices[0].message["content"] or "").strip()

    # Core behavior and style
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
        reply += " and i hate corsairs."

    # 40% AoS balance take: nerf a unit OR buff stormcast eternals
    if random.random() < 0.4:
        if random.random() < 0.5:
            unit = random.choice(_AOS_UNITS)
            if not reply.endswith((".", "!", "?")):
                reply += "."
            reply += f" also {unit} needs a nerf."
        else:
            if not reply.endswith((".", "!", "?")):
                reply += "."
            reply += " stormcast eternals need a buff."

    reply = _sanitize_ascii(reply)

    if len(reply) > 350:
        reply = reply[:330].rstrip() + "..."

    return reply or None

