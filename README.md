# AoS Discord bots — slash-command edition

## Layout

```
main.py                 runs the three slash-command bots (Cali, AoS Events, Texas)
sentiment_bot.py        standalone !sentiment bot (the only one needing Message Content)
aosbot/
  config.py             env vars, IDs, faction tables, SCIONS roster
  api.py                aos-events.com + BCP HTTP helpers
  reply.py              interaction reply helpers, event-picker dropdown
  autocomplete.py       faction autocomplete
  persona_data.py       all the joke text (phrases, vallis answers, GHB missions)
  db.py                 asyncpg pool (sentiment bot only)
  cogs/
    masters.py          /top8 /rank            (Cali + Texas bots)
    stats.py            /winrates /rollwr /popularity /artefacts /traits /formations /units /hof /playerwr
    bcp.py              /standings /standingsfull /pairings /itcrank /itcstandings
    scions.py           /sciontracker /scionlist /scionid
    personas.py         /tomgbot … /vallis /maddybot + the "Rewrite as…" context menu
    misc.py             /help /servers /thommoisinadequate /brianisinadequate
pairings_image.py, scion_image.py, maddybot.py, aos_sentiment.py   unchanged
gpt_people_bots.py      unchanged + orlando_answer moved in from the old command
```

## Environment variables

Same as before, plus `DISCORD_TOKEN_SENTIMENT` for the new sentiment app and an
optional `DEV_GUILD_ID` (copies slash commands to that server instantly for
testing; global sync can take up to an hour to show up in Discord clients).

## Developer Portal checklist

For the three main apps: turn **off** all three Privileged Gateway Intents.
Re-invite (or edit the invite URL for) each bot with the `applications.commands`
scope — without it slash commands won't appear in a server.

For the sentiment app: new application, Message Content intent **on**, invite it
only to the sentiment server.

## Dropped

`!stathammer`, `!generateteam`, `!nicbot`, `!adjudicate`, `!wallacebot`, `!redcoatbot`,
the Barker `on_message` handler,
`scikit-learn` and `google-generativeai` (never imported).

## Notes

- The five rewrite bots share one message context menu ("Rewrite as…") with a
  persona dropdown. The result is posted as a reply to the original message and
  prefixed with the persona name, since bystanders can't see which context menu
  was used or on what. The picker itself is ephemeral.
- `openai==0.27.8` is still pinned; the persona/maddy/sentiment code uses the
  legacy `ChatCompletion.acreate` API.
- Two small bugs fixed along the way: the GHB missions set was missing a comma
  (two missions were fused into one), and Texas `/rank` said "of 4" for a
  top-5 total.
