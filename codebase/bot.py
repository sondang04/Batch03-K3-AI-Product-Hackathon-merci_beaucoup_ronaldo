#!/usr/bin/env python3
"""Discord bot `/recap` — adapter mỏng lên lõi agent.

    .venv/bin/python codebase/bot.py

Lõi (`agent/recap.py`, `agent/agent.py`) không biết gì về Discord; file này chỉ
làm ba việc: nhận lệnh, gọi lõi, và chẻ output cho vừa giới hạn 2000 ký tự của
Discord. Web app `app.py` dùng đúng lõi đó — hai UI, một sản phẩm.

Lệnh:
    /recap  buoi:<Day 1|Day 2 sáng>   → header + MỤC LỤC chọn được (Select);
                                       chọn block → nội dung riêng cho bạn
    /hoi    cau_hoi:<...>             → trả lời có căn cứ, kèm mã đoạn
    (nhắc bot trong tin nhắn thường cũng được coi là /hoi)
    /quiz   buoi:<...>                → quiz tương tác trong Discord

Cần trong .env:  DISCORD_TOKEN=...   (ngoài OPENAI_API_KEY đã có)
Bot cần quyền: Send Messages · Create Public Threads · Send Messages in Threads.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict

# Fix encoding cho Windows console (emoji ✓ ⚠️ không in được mặc định)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discord                                  # noqa: E402
from discord import app_commands                # noqa: E402
from discord.ext import commands, tasks        # noqa: E402

from agent import config                        # noqa: E402
from agent.agent import run_agent               # noqa: E402
from agent.llm import make_client               # noqa: E402
from agent.recap import build_recap, render as render_recap  # noqa: E402
from agent.quiz import build_quiz, render as render_quiz     # noqa: E402
import ui_discord                              # noqa: E402

# Mini HTTP cho UI admin ping/reload — chạy ở 127.0.0.1:8765 (mặc định).
# UI truy vấn GET /sessions để biết buổi nào bot đã thấy, POST /reload để ép reload.
from aiohttp import web as _aioweb  # noqa: E402

MAX = 1900          # Discord cho 2000 ký tự/message — chừa chỗ cho đuôi
CLIENT = make_client()
# gpt-4o-mini call là blocking → đẩy sang thread, không chặn event loop của Discord
SEM = asyncio.Semaphore(2)

CHON_BUOI = [app_commands.Choice(name=ten, value=sid)
             for sid, ten in config.list_choices()]

QUIZ_HTML = config.REPO / "codebase" / "data" / "quiz-interactive.html"

# File watcher: hash của SESSIONS để phát hiện JSON đổi mà không cần lib ngoài
_LAST_SESSIONS_SIG: tuple = config.sessions_signature()


def _buoi_choices() -> list[app_commands.Choice[str]]:
    """Trả choices ĐÚNG THỜI ĐIỂM gọi — không cache như CHON_BUOI ở module scope.
    Dùng cho slash command khi đã reload SESSIONS."""
    return [app_commands.Choice(name=ten, value=sid)
            for sid, ten in config.list_choices()]


async def _refresh_commands() -> None:
    """Re-sync slash command sau khi reload SESSIONS.
    Vì /recap và /quiz dùng autocomplete thay vì choices, không cần mutate
    param.choices — chỉ cần tree.sync() để Discord nhận subcommand mới (nếu có).
    """
    try:
        await bot.tree.sync()
        print(f"✓ /reload-sessions: re-sync xong, {len(config.SESSIONS)} buổi trong registry")
    except Exception as e:
        print(f"⚠️ /reload-sessions: tree.sync() lỗi: {e}")


def inject_quiz_data(quiz_obj) -> Path:
    """Copy quiz data vào HTML template, trả path file."""
    html_path = QUIZ_HTML
    if not html_path.exists():
        raise FileNotFoundError("quiz-interactive.html not found")

    content = html_path.read_text(encoding="utf-8")

    # Inject quiz data vào JS
    cau_hoi_js = json.dumps({
        "session_id": quiz_obj.session_id,
        "buoi": quiz_obj.buoi,
        "cau_hoi": [
            {"loai": q.loai, "cau": q.cau, "dap_an": q.dap_an,
             "giai_thich": q.giai_thich, "nguon": q.nguon}
            for q in quiz_obj.cau_hoi
        ]
    }, ensure_ascii=False)

    # Thay data trong HTML — tìm placeholder rỗng
    content = re.sub(
        r'const quizData = \{[^}]*"cau_hoi": \[\][^}]*\};',
        f'const quizData = {cau_hoi_js};',
        content
    )

    out = html_path.parent / "quiz-active.html"
    out.write_text(content, encoding="utf-8")
    return out


# ── Mini HTTP cho UI admin (127.0.0.1:8765) ────────────────────────────────────
# UI admin gọi GET /sessions để biết bot đã thấy buổi nào, POST /reload để ép reload.
# Nếu port bận thì không crash — chỉ log warning. Bot vẫn chạy Discord bình thường.

ADMIN_HTTP_HOST = os.environ.get("BOT_HTTP_HOST", "127.0.0.1")
ADMIN_HTTP_PORT = int(os.environ.get("BOT_HTTP_PORT", "8765"))

async def _handle_sessions(request: _aioweb.Request) -> _aioweb.Response:
    return _aioweb.json_response({"sessions": sorted(config.SESSIONS.keys())})


async def _handle_reload(request: _aioweb.Request) -> _aioweb.Response:
    config.reload_sessions()
    global _LAST_SESSIONS_SIG
    _LAST_SESSIONS_SIG = config.sessions_signature()
    await _refresh_commands()
    return _aioweb.json_response({"ok": True, "sessions": sorted(config.SESSIONS.keys())})


async def _start_admin_http(bot_ref: "Bot") -> _aioweb.AppRunner:
    """Khởi mini HTTP ở 127.0.0.1:PORT. Trả runner để bot giữ ref."""
    app = _aioweb.Application()
    app.router.add_get("/sessions", _handle_sessions)
    app.router.add_post("/reload", _handle_reload)
    runner = _aioweb.AppRunner(app)
    try:
        await runner.setup()
        site = _aioweb.TCPSite(runner, ADMIN_HTTP_HOST, ADMIN_HTTP_PORT)
        await site.start()
        print(f"✓ admin HTTP: http://{ADMIN_HTTP_HOST}:{ADMIN_HTTP_PORT}/sessions")
    except OSError as e:
        # Port bận (vd có bot instance cũ) — không sao, bot vẫn chạy Discord
        print(f"⚠️ admin HTTP không start được (port {ADMIN_HTTP_PORT} bận): {e}")
    return runner


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
        self.core = CLIENT      # component truy cập lõi qua itr.client.core

    async def setup_hook(self):
        ui_discord.dang_ky_persistent(self)   # mục lục sống sót qua restart
        await self.tree.sync()
        print(f"✓ đã sync {len(self.tree.get_commands())} slash command")
        # Watch sessions.json — 5s/lần, không tốn pin
        self.watch_sessions_json.start()
        # Mini HTTP cho UI admin (GET /sessions + POST /reload)
        self._admin_runner = await _start_admin_http(self)

    @tasks.loop(seconds=5)
    async def watch_sessions_json(self):
        """Phát hiện sessions.json đổi (do UI admin ghi) → reload + re-sync."""
        global _LAST_SESSIONS_SIG
        if not config.SESSIONS_FILE.exists():
            return
        sig = config.sessions_signature()
        if sig != _LAST_SESSIONS_SIG:
            old = set(config.SESSIONS.keys())
            config.reload_sessions()
            new = set(config.SESSIONS.keys())
            added = new - old
            print(f"✓ watch_sessions_json: reload xong, buổi mới: {sorted(added) or '(chỉ sửa)'}")
            _LAST_SESSIONS_SIG = sig
            await _refresh_commands()

    @watch_sessions_json.before_loop
    async def before_watch(self):
        await self.wait_until_ready()

    async def on_interaction(self, itr: discord.Interaction):
        """Route button click từ QuizView — dùng custom_id 'quiz:*'."""
        if itr.type != discord.InteractionType.component:
            return
        cid = itr.data.get("custom_id", "") if itr.data else ""
        if not cid.startswith("quiz:"):
            return
        view = _quiz_views.get(itr.user.id)
        if view is None:
            await itr.response.send_message(
                "⚠️ Quiz state không tìm thấy (có thể bot đã restart). Gõ `/quiz` lại nhé.",
                ephemeral=True
            )
            return
        await view.handle_interaction(itr)

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

    async def quiz(self, sid: str):
        async with SEM:
            return await asyncio.to_thread(build_quiz, sid, CLIENT)


bot = Bot()


async def _buoi_autocomplete(itr: discord.Interaction, current: str):
    """Autocomplete cho /recap và /quiz — đọc SESSIONS fresh mỗi lần user gõ.
    Trả về tối đa 25 gợi ý (giới hạn Discord)."""
    items = config.list_choices()
    if current:
        items = [(sid, ten) for sid, ten in items if current.lower() in ten.lower() or current.lower() in sid.lower()]
    return [app_commands.Choice(name=ten[:100], value=sid) for sid, ten in items[:25]]


@bot.tree.command(name="recap", description="Recap một buổi học thành các block có trích dẫn")
@app_commands.describe(buoi="Buổi học cần recap")
@app_commands.autocomplete(buoi=_buoi_autocomplete)
async def cmd_recap(itr: discord.Interaction, buoi: str):
    # dựng recap lần đầu ~50s > 3s giới hạn của Discord → phải defer trước
    await itr.response.defer(thinking=True)
    if buoi not in config.SESSIONS:
        return await itr.followup.send(f"⚠️ Không tìm thấy buổi `{buoi}` trong registry.")
    try:
        r = await bot.recap(buoi)
    except Exception as e:                       # lỗi lõi ≠ bot chết
        return await itr.followup.send(f"⚠️ Không dựng được recap: `{type(e).__name__}: {e}`")

    # MỘT message: header + mục lục Select. Học viên bấm chọn block → nội dung
    # trả riêng (ephemeral) cho người bấm. Đổ 11 block ra channel thì vừa ngập
    # vừa bắt đọc tuần tự — trái G8.
    await itr.followup.send(ui_discord.header(r), view=ui_discord.MucLuc(buoi, r))


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


# ── Quiz Discord Interactive (trắc nghiệm A/B/C/D) ───────────────────────────

@dataclass
class QuizState:
    """State lưu quiz của một user."""
    buoi: str
    cau_hoi: list[dict]  # [{loai, cau, lua_chon, dap_an_dung, dap_an_text, giai_thich, nguon}]
    user_choice: list = field(default_factory=list)  # [None, 0, 1, 2, 3] — lựa chọn của user
    current: int = 0

    def init(self):
        self.user_choice = [None] * len(self.cau_hoi)
        self.current = 0

    @property
    def total(self) -> int:
        return len(self.cau_hoi)

    @property
    def correct(self) -> int:
        return sum(
            1 for q, c in zip(self.cau_hoi, self.user_choice)
            if c is not None and c == q.get("dap_an_dung", -1)
        )

    @property
    def incorrect(self) -> int:
        return sum(
            1 for q, c in zip(self.cau_hoi, self.user_choice)
            if c is not None and c != q.get("dap_an_dung", -1)
        )

    @property
    def answered(self) -> int:
        return sum(1 for c in self.user_choice if c is not None)

    @property
    def all_done(self) -> bool:
        return self.answered == self.total

    def get_loai_icon(self, loai: str) -> str:
        return {"RECALL": "📖", "KEYWORD": "🔑", "APPLICATION": "💬"}.get(loai, "❓")


class QuizView(discord.ui.View):
    """Trắc nghiệm A/B/C/D — user chọn đáp án → bot chấm → hiển thị giải thích."""

    KIEU_DAP_AN = ["A", "B", "C", "D"]

    def __init__(self, state: QuizState, user_id: int):
        super().__init__(timeout=1800)
        self.state = state
        self.user_id = user_id
        self._build_buttons()

    async def interaction_check(self, itr: discord.Interaction) -> bool:
        if itr.user.id != self.user_id:
            await itr.response.send_message("❌ Đây là quiz của người khác!", ephemeral=True)
            return False
        return True

    def _build_buttons(self):
        """4 buttons A/B/C/D + Trước/Sau + Xem kết quả (nếu xong)."""
        self.clear_items()

        cur = self.state.current
        total = self.state.total
        q = self.state.cau_hoi[cur]
        lua_chon = q.get("lua_chon", [])
        chosen = self.state.user_choice[cur]
        correct_idx = q.get("dap_an_dung", 0)

        # Row 1: 4 đáp án A/B/C/D — bot.py là nơi DUY NHẤT thêm prefix "A./B./C./D."
        # (quiz.py đã strip hết prefix từ LLM rồi, opt giờ là text thuần)
        for i, opt in enumerate(lua_chon[:4]):
            label = f"{self.KIEU_DAP_AN[i]}. {opt}"
            # Rút gọn label nếu quá dài (Discord limit 80 char/button)
            if len(label) > 80:
                label = label[:77] + "..."
            style = discord.ButtonStyle.secondary
            if chosen is not None:
                if i == correct_idx:
                    style = discord.ButtonStyle.success
                elif i == chosen:
                    style = discord.ButtonStyle.danger
            self.add_item(discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"quiz:ans:{i}",
                disabled=(chosen is not None),  # khóa sau khi chọn
            ))

        # Row 2: Trước / Sau / Kết quả
        self.add_item(discord.ui.Button(
            label="◀ Trước",
            style=discord.ButtonStyle.secondary,
            custom_id="quiz:prev",
            disabled=(cur == 0),
        ))
        is_last = (cur == total - 1)
        self.add_item(discord.ui.Button(
            label="Sau ▶" if not is_last else "Kết thúc ▶",
            style=discord.ButtonStyle.primary if is_last else discord.ButtonStyle.secondary,
            custom_id="quiz:next",
            disabled=False,
        ))

        # Row 2: nút xem kết quả nếu đã xong hết
        if self.state.all_done:
            self.add_item(discord.ui.Button(
                label="📊 Xem kết quả",
                style=discord.ButtonStyle.primary,
                custom_id="quiz:result",
            ))

    def _build_embed(self) -> discord.Embed:
        """Embed hiển thị câu hỏi + 4 lựa chọn + (nếu đã chọn) giải thích."""
        q = self.state.cau_hoi[self.state.current]
        cur = self.state.current
        total = self.state.total
        loai_icon = self.state.get_loai_icon(q["loai"])
        chosen = self.state.user_choice[cur]
        correct_idx = q.get("dap_an_dung", 0)

        # Truncate
        cau = q["cau"][:800]
        giai_thich = q.get("giai_thich", "")[:600]
        nguon = q.get("nguon", "")[:200]

        embed = discord.Embed(
            title=f"{loai_icon} Câu {cur + 1}/{total} · [{q['loai']}]",
            description=cau,
            color=discord.Color.blue()
        )

        # Hiển thị 4 lựa chọn dạng text trong embed (Discord truncate button label)
        opts_text = "\n".join(
            f"{'  ' if chosen is None else ('🟢' if i == correct_idx else ('🔴' if i == chosen else '⚪'))} "
            f"**{self.KIEU_DAP_AN[i]}.** {opt}"
            for i, opt in enumerate(q.get("lua_chon", [])[:4])
        )
        embed.add_field(name="Lựa chọn", value=opts_text, inline=False)

        # Nếu đã chọn → hiển thị kết quả + giải thích
        if chosen is not None:
            if chosen == correct_idx:
                embed.color = discord.Color.green()
                embed.add_field(name="✅ Chính xác!", value="Bạn đã chọn đúng đáp án.", inline=False)
            else:
                embed.color = discord.Color.red()
                embed.add_field(
                    name="❌ Chưa đúng",
                    value=f"Đáp án đúng: **{self.KIEU_DAP_AN[correct_idx]}.** {q.get('lua_chon', [''])[correct_idx]}",
                    inline=False
                )
            if giai_thich:
                embed.add_field(name="💡 Giải thích", value=giai_thich, inline=False)
            if nguon:
                embed.add_field(name="📎 Nguồn", value=nguon, inline=False)

        embed.set_footer(
            text=f"📊 Đúng {self.state.correct} · Sai {self.state.incorrect} · Còn {total - self.state.answered}"
        )
        return embed

    async def _refresh(self, itr: discord.Interaction):
        self._build_buttons()
        await itr.response.edit_message(embed=self._build_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def handle_interaction(self, itr: discord.Interaction):
        """Entry point duy nhất — gọi từ Bot.on_interaction."""
        if not await self.interaction_check(itr):
            return
        cid = itr.data.get("custom_id", "")
        cur = self.state.current
        total = self.state.total

        if cid.startswith("quiz:ans:"):
            try:
                idx = int(cid.split(":")[2])
            except (ValueError, IndexError):
                return
            if not (0 <= idx <= 3):
                return
            if self.state.user_choice[cur] is not None:
                # đã chọn rồi → không cho chọn lại
                await itr.response.send_message("Bạn đã chọn đáp án cho câu này rồi.", ephemeral=True)
                return
            self.state.user_choice[cur] = idx
            await self._refresh(itr)

        elif cid == "quiz:prev" and cur > 0:
            self.state.current -= 1
            await self._refresh(itr)

        elif cid == "quiz:next":
            if cur < total - 1:
                if self.state.user_choice[cur] is None:
                    await itr.response.send_message(
                        "⚠️ Bạn chưa chọn đáp án cho câu này. Hãy chọn A/B/C/D trước.",
                        ephemeral=True
                    )
                    return
                self.state.current += 1
                await self._refresh(itr)
            else:
                # Câu cuối và đã chọn → hiển thị kết quả
                if self.state.all_done:
                    await itr.response.edit_message(
                        embed=self._build_result_embed(),
                        view=self
                    )
                else:
                    await itr.response.send_message(
                        "⚠️ Bạn chưa trả lời hết các câu.", ephemeral=True
                    )

        elif cid == "quiz:result":
            await itr.response.edit_message(
                embed=self._build_result_embed(),
                view=self
            )

    def _build_result_embed(self) -> discord.Embed:
        correct = self.state.correct
        total = self.state.total
        percent = int(correct / total * 100) if total else 0

        if percent >= 80:
            emoji, title, desc = "🎉", "Xuất sắc!", "Bạn nắm vững kiến thức rồi!"
            color = discord.Color.green()
        elif percent >= 60:
            emoji, title, desc = "👍", "Khá tốt!", "Cố gắng ôn lại những phần chưa đúng nhé!"
            color = discord.Color.yellow()
        elif percent >= 40:
            emoji, title, desc = "📚", "Cần cải thiện", "Hãy xem lại bài giảng và làm lại quiz nhé!"
            color = discord.Color.orange()
        else:
            emoji, title, desc = "💪", "Đừng nản chí!", "Hãy học lại nội dung và thử lại lần nữa!"
            color = discord.Color.red()

        embed = discord.Embed(
            title=f"{emoji} {title}",
            description=f"**Quiz: {self.state.buoi}**\n\n{desc}",
            color=color
        )
        embed.add_field(
            name="📝 Kết quả",
            value=f"**{correct}/{total}** câu đúng ({percent}%)",
            inline=False
        )

        # Chi tiết từng câu — 1 dòng/câu
        detail = []
        for i, (q, c) in enumerate(zip(self.state.cau_hoi, self.state.user_choice)):
            idx = q.get("dap_an_dung", 0)
            if c is None:
                mark = "⏳"
                tail = "chưa làm"
            elif c == idx:
                mark = "✅"
                tail = f"đúng ({self.KIEU_DAP_AN[idx]})"
            else:
                mark = "❌"
                tail = f"sai → đáp án {self.KIEU_DAP_AN[idx]}"
            detail.append(f"{mark} Câu {i+1}: {tail}")
        embed.add_field(name="📋 Chi tiết", value="\n".join(detail), inline=False)
        return embed


# Lưu view theo user để xử lý button click
_quiz_views: dict[int, QuizView] = {}


@bot.tree.command(name="quiz", description="Trắc nghiệm 4 lựa chọn A/B/C/D — chấm tự động")
@app_commands.describe(buoi="Buổi học cần quiz")
@app_commands.autocomplete(buoi=_buoi_autocomplete)
async def cmd_quiz(itr: discord.Interaction, buoi: str):
    """Quiz trắc nghiệm A/B/C/D tương tác trong Discord."""
    await itr.response.defer(thinking=True)
    if buoi not in config.SESSIONS:
        return await itr.followup.send(f"⚠️ Không tìm thấy buổi `{buoi}` trong registry.")
    try:
        q = await bot.quiz(buoi)
    except Exception as e:
        return await itr.followup.send(f"⚠️ Không sinh được quiz: `{type(e).__name__}: {e}`")

    if not q.cau_hoi:
        return await itr.followup.send("⚠️ Không có câu hỏi nào trong quiz này.")

    # Lọc câu hỏi có đủ 4 lựa chọn
    valid = [cq for cq in q.cau_hoi if len(cq.lua_chon) >= 4]
    if not valid:
        return await itr.followup.send(
            "⚠️ LLM sinh quiz không đủ 4 lựa chọn. Hãy thử lại hoặc dùng `/quiz` buổi khác."
        )

    # Tạo state + view
    state = QuizState(
        buoi=q.buoi,
        cau_hoi=[asdict(cq) for cq in valid]
    )
    state.init()

    view = QuizView(state, itr.user.id)
    _quiz_views[itr.user.id] = view

    await itr.followup.send(
        f"📝 **Quiz — {q.buoi}** ({len(valid)} câu trắc nghiệm)\n"
        f"👆 **Chọn A/B/C/D** cho mỗi câu — bot chấm và giải thích ngay.",
        embed=view._build_embed(),
        view=view
    )


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        sys.exit("Thiếu DISCORD_TOKEN trong .env — xem codebase/DISCORD-SETUP.md")
    bot.run(token, log_handler=None)


# ── Lệnh admin (chỉ người có quyền Administrator mới dùng được) ────────────────

@bot.tree.command(name="reload-sessions",
                  description="(Admin) Reload danh sách buổi học từ sessions.json — dùng sau khi tạo/sửa buổi qua UI admin")
@app_commands.checks.has_permissions(administrator=True)
async def cmd_reload_sessions(itr: discord.Interaction):
    """Reload SESSIONS + re-sync slash command choices.
    Thường không cần — bot tự watch file; nhưng có lệnh để mentor ép reload ngay."""
    await itr.response.defer(thinking=True, ephemeral=True)
    config.reload_sessions()
    global _LAST_SESSIONS_SIG
    _LAST_SESSIONS_SIG = config.sessions_signature()
    await _refresh_commands()
    n = len(config.SESSIONS)
    ids = ", ".join(sorted(config.SESSIONS.keys()))
    await itr.followup.send(f"✓ Reload xong — {n} buổi: `{ids}`", ephemeral=True)


@cmd_reload_sessions.error
async def cmd_reload_sessions_error(itr: discord.Interaction, error: Exception):
    if isinstance(error, app_commands.MissingPermissions):
        await itr.response.send_message("❌ Chỉ admin server mới dùng được lệnh này.", ephemeral=True)
    else:
        await itr.response.send_message(f"⚠️ Lỗi: `{type(error).__name__}: {error}`", ephemeral=True)


