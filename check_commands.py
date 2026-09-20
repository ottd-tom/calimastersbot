"""
Diagnostic: ask Discord what commands are actually registered for each app.

    python check_commands.py

Run it anywhere the bot's env vars are set (Render shell, or locally with the
same tokens). It does not start a gateway connection, so it's safe to run while
the bots are live.
"""

from __future__ import annotations

import asyncio
import os

import aiohttp

TOKENS = {
    "Cali Masters": "DISCORD_TOKEN",
    "AoS Events":   "DISCORD_TOKEN_AOSEVENTS",
    "Texas Masters": "TEXAS_DISCORD_BOT",
}

API = "https://discord.com/api/v10"


async def check(session: aiohttp.ClientSession, label: str, env_var: str) -> None:
    token = os.getenv(env_var)
    print(f"\n=== {label}  (${env_var})")
    if not token:
        print("  MISSING token env var")
        return

    headers = {"Authorization": f"Bot {token}"}

    async with session.get(f"{API}/users/@me", headers=headers) as r:
        if r.status != 200:
            print(f"  login check failed: HTTP {r.status} {await r.text()}")
            return
        me = await r.json()
    print(f"  bot user: {me['username']}  (id {me['id']})")

    async with session.get(f"{API}/oauth2/applications/@me", headers=headers) as r:
        app = await r.json()
    app_id = app["id"]
    print(f"  application id: {app_id}")

    async with session.get(f"{API}/applications/{app_id}/commands", headers=headers) as r:
        if r.status != 200:
            print(f"  command list failed: HTTP {r.status} {await r.text()}")
            return
        cmds = await r.json()

    print(f"  globally registered commands: {len(cmds)}")
    for c in sorted(cmds, key=lambda c: (c.get("type", 1), c["name"])):
        kind = {1: "slash", 2: "user-menu", 3: "message-menu"}.get(c.get("type", 1), "?")
        print(f"    [{kind}] {c['name']}")

    async with session.get(f"{API}/users/@me/guilds", headers=headers) as r:
        guilds = await r.json() if r.status == 200 else []
    print(f"  in {len(guilds)} guild(s)")


async def main():
    async with aiohttp.ClientSession() as session:
        for label, env_var in TOKENS.items():
            try:
                await check(session, label, env_var)
            except Exception as e:
                print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
