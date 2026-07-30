#!/usr/bin/env python3
"""Discord bot `/recap` — adapter mỏng lên lõi agent.

    .venv/bin/python codebase/bot.py

Lõi (`agent/recap.py`, `agent/agent.py`) không biết gì về Discord; file này chỉ
làm ba việc: nhận lệnh, gọi lõi, và chẻ output cho vừa giới hạn 2000 ký tự của
Discord. Web app `app.py` dùng đúng lõi đó — hai UI, một sản phẩm.

Lệnh:
    /recap  buoi:<Day 1|Day 2 sáng>   → thread, mỗi block một message
    /hoi    cau_hoi:<...>             → trả lời có căn cứ, kèm mã đoạn
    (nhắc bot trong tin nhắn thường cũng được coi là /hoi)

Cần trong .env:  DISCORD_TOKEN=...   (ngoài OPENAI_API_KEY đã có)
Bot cần quyền: Send Messages · Create Public Threads · Send Messages in Threads.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discord                                  # noqa: E402
from discord import app_commands                # noqa: E402

from agent import config                        # noqa: E402
from agent.agent import run_agent               # noqa: E402
from agent.llm import make_client               # noqa: E402
from agent.recap import build_recap, render     # noqa: E402

MAX = 1900          # Discord cho 2000 ký tự/message — chừa chỗ cho đuôi
CLIENT = make_client()
# gpt-4o-mini call là blocking → đẩy sang thread, không chặn event loop của Discord
SEM = asyncio.Semaphore(2)

CHON_BUOI = [app_commands.Choice(name=s["ten"][:100], value=sid)
             for sid, s in config.SESSIONS.items()]


def chunk(text: str) -> list[str]:
    """Chẻ theo dòng để không cắt giữa mã đoạn hay giữa một gạch đầu dòng."""
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > MAX:                  # dòng đơn quá dài (hiếm)
            out.append(line[:MAX])
            line = line[MAX:]
        if len(cur) + len(line) + 1 > MAX:
            out.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur.rstrip())
    return out or ["(rỗng)"]


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents(guilds=True, messages=True,
                                                 message_content=True))
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✓ đã sync {len(self.tree.get_commands())} slash command")

    async def on_ready(self):
        print(f"✓ online: {self.user} · provider={CLIENT.provider} model={CLIENT.model}")

    async def on_message(self, msg: discord.Message):
        # nhắc bot trong tin nhắn thường = hỏi bài
        if msg.author.bot or self.user not in msg.mentions:
            return
        q = msg.content.replace(f"<@{self.user.id}>", "").strip()
        if not q:
            return await msg.reply("Bạn hỏi gì về buổi học nhé — hoặc dùng `/recap`.")
        async with msg.channel.typing():
            try:
                res = await self.ask(q)
            except Exception as e:
                return await msg.reply(f"⚠️ Lỗi: `{type(e).__name__}: {e}`")
        parts = chunk(res.text)
        await msg.reply(parts[0])
        for p in parts[1:]:
            await msg.channel.send(p)

    async def ask(self, q: str):
        async with SEM:
            return await asyncio.to_thread(run_agent, q, CLIENT, "discord")

    async def recap(self, sid: str):
        async with SEM:
            return await asyncio.to_thread(build_recap, sid, CLIENT)


bot = Bot()


@bot.tree.command(name="recap", description="Recap một buổi học thành các block có trích dẫn")
@app_commands.describe(buoi="Buổi học cần recap")
@app_commands.choices(buoi=CHON_BUOI)
async def cmd_recap(itr: discord.Interaction, buoi: app_commands.Choice[str]):
    # dựng recap lần đầu ~50s > 3s giới hạn của Discord → phải defer trước
    await itr.response.defer(thinking=True)
    try:
        r = await bot.recap(buoi.value)
    except Exception as e:                       # lỗi lõi ≠ bot chết
        return await itr.followup.send(f"⚠️ Không dựng được recap: `{type(e).__name__}: {e}`")

    msgs = render(r)
    head = await itr.followup.send(msgs[0], wait=True)
    # Mỗi block một message trong THREAD — đúng hình dung của lát cắt: học viên
    # nhảy vào đúng block cần, không bị bắt đọc tuần tự.
    try:
        th = await head.create_thread(name=f"Recap {r.buoi}"[:100],
                                      auto_archive_duration=1440)
        dest = th
    except (discord.Forbidden, discord.HTTPException):
        dest = itr.channel                       # thiếu quyền tạo thread → gửi thẳng
        await itr.followup.send("_(không tạo được thread — gửi vào channel)_")
    for m in msgs[1:]:
        for part in chunk(m):
            await dest.send(part)


@bot.tree.command(name="hoi", description="Hỏi về nội dung buổi học (trả lời kèm mã đoạn)")
@app_commands.describe(cau_hoi="vd: hai mùa đông AI là gì?")
async def cmd_hoi(itr: discord.Interaction, cau_hoi: str):
    await itr.response.defer(thinking=True)
    try:
        res = await bot.ask(cau_hoi)
    except Exception as e:
        return await itr.followup.send(f"⚠️ Lỗi: `{type(e).__name__}: {e}`")
    parts = chunk(res.text)
    await itr.followup.send(parts[0])
    for p in parts[1:]:
        await itr.channel.send(p)


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        sys.exit("Thiếu DISCORD_TOKEN trong .env — xem codebase/DISCORD-SETUP.md")
    bot.run(token, log_handler=None)
