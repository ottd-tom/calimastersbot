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

# Heuristic: detect a "name" either via @mention or a capitalized word not at the very start.
_NAME_WORD = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b")
_MENTION = re.compile(r"@([A-Za-z0-9_\.]+)")

_FAKE_FACTS = [
    "everyone knows the moon is just a big night lamp",
    "gravity actually takes weekends off",
    "triangles have 4 sides if you count with vibes",
    "the sun sets early because it has a second job",
    "wifi signals are heavier when it rains snacks",
    "cats invented economics in 1812 bc, look it up",
    "time zones were made by dolphins for fun",
    "plants photosynthesize memes not light",
    "numbers above 12 are just marketing",
    "maps are flat because paper wins arguments",
    "clouds are stored locally on mountains",
    "the ocean is 90 percent soup if you think about it",
    "dinosaurs left because rent got too high",
    "rain is sky tea, brewed badly",
    "mirrors only work when you believe in them",
]

def _pick_name(text: str) -> Optional[str]:
    m = _MENTION.search(text)
    if m:
        return "@" + m.group(1)
    # find a capitalized word not at index 0
    words = list(_NAME_WORD.finditer(text))
    if words:
        # prefer a name that does not start at 0
        for w in words:
            if w.start() > 0:
                return w.group(1)
        return words[0].group(1)
    return None

def _ensure_disagree_and_fact(reply: str) -> str:
    t = reply.strip()
    # Make sure it clearly disagrees
    if not re.search(r"\b(no|nah|nope|wrong|disagree)\b", t.lower()):
        t = "nah thats wrong. " + t
    # Ensure a silly fake fact is present
    if not re.search(r"\b(fact|everyone knows|actually)\b", t.lower()):
        fake = random.choice(_FAKE_FACTS)
        # keep it short, chatty
        if not t.endswith((".", "!", "?")):
            t += "."
        t += " actually " + fake + "."
    return t

async def noe_answer(target: discord.Message) -> Optional[str]:
    """
    Build a 'vehement disagree + fake fact' reply to the given message.
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

    # Detect a probable name for optional soda aside
    name_for_aside = _pick_name(prev_text)

    system_prompt = (
        "You are NoeBot. You always vehemently DISAGREE with what was said, in a short, "
        "mobile-typed, slightly chaotic way. Use plain ASCII. Keep it brief. "
        "Invent a random, obviously untrue and silly 'fact' to back up your disagreement. "
        "Style: short lines, light punctuation, sometimes lowercase, a typo here and there, but readable. "
        "Avoid harmful or real-world dangerous claims; keep the 'facts' goofy and harmless. "
        "No slurs, threats, medical/legal advice, or real conspiracy claims."
    )

    user_prompt = (
        "Disagree strongly with this and add a made-up silly fact. Keep it brief.\n\n"
        f"TEXT:\n{prev_text}"
    )

    resp = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.95,
        max_tokens=160,
    )
    reply = (resp.choices[0].message["content"] or "").strip()

    # Guarantee the core behavior even if the model slacks
    reply = _ensure_disagree_and_fact(reply)

    # 40% chance soda aside if a name is present
    if name_for_aside and random.random() < 0.4:
        if not reply.endswith((".", "!", "?")):
            reply += "."
        reply += f" i like {name_for_aside} tho they bought me a soda."

    # Keep it reasonably short
    if len(reply) > 400:
        reply = reply[:380].rstrip() + "..."

    return reply or None
