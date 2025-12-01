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
    myrng = random.Random()
    if myrng.random() < 0.2:
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
        "without quoting or imitating specific lines from the films. "
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
        "Do not add new info or names. ASCII only.\n\n"
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
    
    
async def yoda_answer(target: discord.Message) -> Optional[str]:
    """
    Build a yoda reply
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
        "You are YodaBot. You rewrite messages in a Yoda-like voice (inverted syntax), "
        "without quoting or imitating specific lines from the films.  "
        "slightly confused and off-point. Use plain ASCII only.\n\n"
        "Style guide:\n"
        "- Invert word order often: object-subject-verb or verb-final constructions (e.g., \"Strong this idea is\").\n"
        "- Drop some articles and helper words; use sentence fragments.\n"
        "- Keep a calm, sage tone; sprinkle occasional \"hmm\" or rhetorical questions, but not every time.\n"
        "- Keep punctuation light; lowercase is fine; no emojis.\n"
        "- Do not add facts or names; do not mention Star Wars.\n"
        "- 1-2 short sentences max; stay friendly and a bit cryptic."
    )

    user_prompt = (
        "Rewrite the text below so it sounds like a Yoda-style take: "
        "dumber, a little off the point, and very brief. "
        "Do not add new info or names. ASCII only.\n\n"
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



async def wallace_answer(target: discord.Message) -> Optional[str]:
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
        "You are WallaceBot. You rewrite messages in the style of a friendly, slightly frazzled British inventor, "
        "loosely inspired by characters like Wallace from old claymation films, but without quoting or imitating "
        "specific lines from any films or claiming to be the original character. "
        "You are cheerful, polite, and a bit absent-minded. Use plain ASCII only.\n\n"
        "Style guide:\n"
        "- Sound upbeat and kindly, even if the message is negative.\n"
        "- Use mild British-style expressions sometimes, like \"oh dear\", \"right then\", or \"goodness me\", "
        "but keep them short and varied.\n"
        "- Occasionally mention inventions, contraptions, or gadgets in a quick aside, as if you are always tinkering.\n"
        "- You may sometimes mention tea, toast, or cheese in a light, silly way, but not every time.\n"
        "- Be slightly off-point or mildly misunderstanding the main idea now and then, but stay supportive.\n"
        "- Keep punctuation light; lowercase is fine; short sentences are preferred.\n"
        "- 1-2 short sentences max; keep it chatty and informal.\n"
        "- Do not add real-world facts; do not use any film quotes; no emojis."
    )

    user_prompt = (
        "Rewrite the text below so it sounds like a WallaceBot-style take: "
        "friendly, slightly bumbling British inventor energy, a bit off the point, and brief. "
        "Do not add new info or names. ASCII only.\n\n"
        f\"TEXT:\\n{prev_text}\"
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

# Edge-lord bits
_INSULTS = [
    "cope", "cringe", "mid", "try harder", "skill issue", "puto",
    "cheap take", "Chingus", "delusional", "weak sauce", "low effort",
    "wishful", "hollow", "nice theory", "gringo"
]
_OPENERS = [
    "no.", "hard no.", "cool story. still wrong.", "nah.", "pass.",
    "incorrect.", "not it.", "not even close.", "nope."
]

# AoS units pool for the optional balance aside
_AOS_UNITS = [
    "maw-krusha", "nagash", "morathi", "skarbrand", "archaon",
    "lord kroak", "teclis", "belakor", "varanguard", "krondspine",
    "stormdrake guard", "fulminators", "longstrikes", "grave guard",
    "glutos", "thanquol", "necromancer", "blightkings", "saurus warriors"
]

import re

# Common false-positives to skip when guessing names from capitalization
_STOPWORDS_CAP = {
    "I","Im","The","This","That","It","You","We","They","He","She",
    "Yes","No","Ok","Okay","Lol","BTW","FYI","IMO","IDK",
    "Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday",
    "Today","Tomorrow","Yesterday",
}

# <@123>, <@!123> style
_DISCORD_ID_MENTION = re.compile(r"<@!?\d+>")
# @username style
_AT_USERNAME = re.compile(r"@([A-Za-z0-9_.]+)")
# "Capitalized" or Title Case sequences NOT at sentence start
_TITLE_NAME = re.compile(
    r"(?<!^)(?<![.!?]\s)\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b"
)

def _pick_name(target, text: str):
    """
    Picks a likely name/handle to reference for the soda aside.
    Priority:
      1) message.mentions
      2) <@...> ID mention tokens
      3) @username text
      4) Title-Case tokens not at sentence start (filtered)
    Returns a string to echo (e.g., '@someone' or 'Alice'), or None.
    """
    # 1) Real Discord mentions
    try:
        mentions = getattr(target, "mentions", None) or []
        if mentions:
            m = mentions[0]
            # Prefer @display_name; fall back to @name; last resort @<id>
            handle = getattr(m, "display_name", None) or getattr(m, "name", None)
            if handle:
                return "@" + handle
            uid = getattr(m, "id", None)
            if uid:
                return f"<@{uid}>"
    except Exception:
        pass

    # 2) <@...> tokens in content
    m = _DISCORD_ID_MENTION.search(text)
    if m:
        return m.group(0)

    # 3) @username text
    m = _AT_USERNAME.search(text)
    if m:
        return "@" + m.group(1)

    # 4) Title-Case words not at sentence start (skip common junk)
    for m in _TITLE_NAME.finditer(text):
        cand = m.group(1).strip()
        # reject if too long (more than 3 words) or first word is a stopword
        parts = cand.split()
        if len(parts) > 3:
            continue
        if parts[0] in _STOPWORDS_CAP:
            continue
        # avoid ALL CAPS or acronyms
        if cand.isupper():
            continue
        # avoid grabbing first token of whole message
        if m.start() == 0:
            continue
        return cand

    return None


def _sanitize_ascii(s: str) -> str:
    # enforce ascii and remove teen punctuation patterns
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"!{2,}", "!", s)
    return s

def _edge_style_disagree() -> str:
    return random.choice(_OPENERS)

def _ensure_disagree_and_insult(text: str) -> str:
    t = (text or "").strip()
    if not t or not re.search(r"\b(no|nah|nope|wrong|disagree|incorrect)\b", t.lower()):
        t = _edge_style_disagree()
    # add one short insult
    insult = random.choice(_INSULTS)
    if not t.endswith((".", "!", "?")):
        t += "."
    t += " " + insult + "."
    # style: lowercase, terse
    t = t.lower()
    t = re.sub(r"[.]{3,}", "..", t)
    t = re.sub(r"\?{2,}", "?", t)
    return t

async def noe_answer(target: discord.Message) -> Optional[str]:
    """
    Edge-lord NoeBot (AoS):
    - always vehemently disagrees
    - GPT fabricates a plausible AoS-related 'fact' tied to the message content (but incorrect)
    - adds one short insult
    - 40%: 'i like <Name> tho they bought me a soda' if a name is detected
    - 40%: 'and i hate corsairs.'
    - 40%: either 'X needs a nerf' or 'stormcast eternals need a buff'
    - ascii only, no emoji, no '!!', lowercase/fragmented
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

    name_for_aside = _pick_name(target, prev_text)

    # Tell GPT to invent AoS-specific but incorrect support relevant to the OP
    system_prompt = (
        "you are noebot for an age of sigmar discord. edge-lord tone. always DISAGREE hard. "
        "be curt, cynical, lowercase, fragmented. plain ascii. "
        "fabricate exactly one short, plausible-sounding age of sigmar fact that appears relevant to the user's text "
        "but is actually incorrect. tie it to the topic (units, factions, battletomes, points, win rates, matchups, battleplans, "
        "grand strategies, triumphs, terrain, or scenarios). "
        "keep it harmless and non-political; no real-world harm. "
        "add one short insult (1-2 words). no emoji. no '!!'. "
        "do not include disclaimers; present the invented fact confidently. "
        "keep output to one or two sentences total."
    )
    user_prompt = (
        "disagree hard with this message and include exactly one fabricated but plausible AoS-related fact "
        "that seems relevant to the text but is wrong. make it sound confident and concise.\n\n"
        "TEXT:\n" + prev_text
    )

    resp = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.95,
        max_tokens=140,
    )
    reply = (resp.choices[0].message["content"] or "").strip()

    # Enforce disagreement + insult + style regardless of model output
    reply = _ensure_disagree_and_insult(reply)

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

    # 40% AoS balance take: nerf a random unit OR buff stormcast eternals
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

    # keep tight
    if len(reply) > 320:
        reply = reply[:300].rstrip() + "..."

    return reply or None
