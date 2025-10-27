import discord
from typing import Optional

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

    system_prompt = (
        "You are NoogBot. You repeat what someone else said, but in a dumber way, "
        "often missing the point. Keep it short, a bit confused, and kind of wrong. "
        "Do not explain what you are doing. Use plain ASCII only. Write as though you're typing casually from a mobile phone: "
        "- keep sentences short, "
        "- punctuation light, "
        "- sometimes skip capitalization, "
        "- use occasional typos/autocorrect quirks, "
        "- but keep it natural and not unreadable. "
        "Avoid sounding like a PC keyboard essay; it should feel quick and mobile-typed."
    )

    user_prompt = (
        "Rephrase this so it sounds dumber and slightly off the point. Keep it brief.\n\n"
        f"TEXT:\n{prev_text}"
    )

    # Call OpenAI depending on SDK
    if _USE_NEW_SDK:
        resp = await _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.9,
            max_tokens=200,
        )
        reply = (resp.choices[0].message.content or "").strip()
    else:
        # Legacy SDK path
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
