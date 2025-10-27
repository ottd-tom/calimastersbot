async def _get_target_message(ctx):
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



async def noog_answer(target: str):
  # Prefer text; if empty, try a small text attachment
  prev_text = (target.content or "").strip()
  if not prev_text and target.attachments:
      for att in target.attachments:
          if (att.size or 0) <= 200_000 and att.content_type and "text" in att.content_type:
              try:
                  prev_text = (await att.read()).decode("utf-8", errors="replace")[:4000]
                  break
              except Exception:
                  pass
  
  if not prev_text:
      return await ctx.send(":warning: That message had no readable text.")
  
  system_prompt = (
      "You are NoogBot. You repeat what someone else said, but in a dumber way, "
      "often missing the point. Keep it short, a bit confused, and kind of wrong. "
      "Do not explain what you are doing. Use plain ASCII only. Write as though you’re typing casually from a mobile phone:" 
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
  
  try:
      resp = await openai.ChatCompletion.acreate(
          model="gpt-4o-mini",
          messages=[
              {"role": "system", "content": system_prompt},
              {"role": "user", "content": user_prompt},
          ],
          temperature=0.9,
          max_tokens=200,
      )
      reply = resp.choices[0].message.content.strip()
  except Exception as e:
      return await ctx.send(f":x: OpenAI error: {e}")

  return reply
