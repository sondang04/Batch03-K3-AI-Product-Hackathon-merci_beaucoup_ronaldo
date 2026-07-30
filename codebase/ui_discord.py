"""Component Discord cho `/recap` — mục lục CHỌN ĐƯỢC thay vì đổ hết ra thread.

Vì sao Select chứ không Button: một buổi có 9-11 block. Button thì hết 2 hàng và
đọc như một bức tường; Select là **một dòng, mở ra danh sách có mô tả** — mỗi option
mang luôn badge độ phủ và số người vướng, nên học viên chọn được block cần TRƯỚC
khi đọc. Đúng G8 (gạt bỏ dễ: không bị bắt đọc tuần tự).

Giới hạn Discord đã tính vào: Select ≤25 option · label ≤100 ký tự · description
≤100 · custom_id ≤100 · button label ≤80 · message ≤2000.

Trả lời từng người là **ephemeral** — 30 học viên bấm cùng lúc không làm ngập channel.

View của mục lục là **persistent** (`timeout=None` + `custom_id` cố định, đăng ký
trong `setup_hook`) nên bot restart xong mục lục cũ vẫn bấm được — recap đã cache
trên đĩa, callback dựng lại từ `session_id` trong custom_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import discord

from agent import config, sources
from agent.recap import BlockRecap, Recap, build_recap

VALIDATION = Path(__file__).resolve().parents[1] / "validation"
LOAI_LOI = [("sai block", "cụm thắc mắc gán sai phần"),
            ("thiếu ý", "block bỏ mất ý quan trọng"),
            ("trích dẫn sai đoạn", "mã đoạn không khớp nội dung")]


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def block_text(r: Recap, b: BlockRecap) -> str:
    """Nội dung một block, gói cho vừa một message Discord."""
    t = (f"**#{b.idx} · {b.tieu_de}**\n{b.badge} · `[{b.ma_dau}]`..`[{b.ma_cuoi}]`"
         f" · {b.so_doan} đoạn\n\n{b.tom_tat}\n")
    for c in b.cum_thac_mac:
        t += (f"\n💬 **Bạn học từng vướng gì ở đây** ({c['so_nguoi']} người)\n"
              f"Cụm *{c['chu_de']}* — vd: \"{_cut(c['vi_du'][0]['cau_hoi'], 120)}\" "
              f"`[{c['vi_du'][0]['ma']}]`\n")
        if c.get("ly_do"):
            t += f"↳ {c['ly_do']}\n"
    return _cut(t, 1900)


# ── Hành động trên một block ─────────────────────────────────────────────────

class KhoiLoi(discord.ui.View):
    """Bấm 'Sai chỗ nào?' → chọn LOẠI lỗi. G15: feedback có loại thì mới vá được,
    👎 trơn thì không biết sai đâu (lỗi đo lường của tutor hiện tại: 2,8% tin có
    rating và không cho biết vì sao)."""

    def __init__(self, sid: str, idx: int, tieu_de: str):
        super().__init__(timeout=300)
        for nhan, mo_ta in LOAI_LOI:
            self.add_item(self._nut(sid, idx, tieu_de, nhan, mo_ta))

    @staticmethod
    def _nut(sid, idx, tieu_de, nhan, mo_ta):
        b = discord.ui.Button(label=_cut(nhan, 80), style=discord.ButtonStyle.secondary)

        async def cb(itr: discord.Interaction):
            VALIDATION.mkdir(parents=True, exist_ok=True)
            with open(VALIDATION / "feedback-log.md", "a", encoding="utf-8") as f:
                f.write(f"| {datetime.now(timezone.utc):%Y-%m-%d %H:%M} | "
                        f"{itr.user.display_name} | {sid} #{idx} {tieu_de} | "
                        f"{nhan} — {mo_ta} | discord |\n")
            await itr.response.send_message(
                f"✅ Đã ghi **{nhan}** cho block #{idx} vào `validation/feedback-log.md`."
                " Cảm ơn bạn — nhóm dùng đúng mục này để sửa trước demo.",
                ephemeral=True)
        b.callback = cb
        return b


class HanhDongBlock(discord.ui.View):
    def __init__(self, sid: str, b: BlockRecap):
        super().__init__(timeout=600)
        self.sid, self.b = sid, b

    @discord.ui.button(label="📖 Xem nguyên văn", style=discord.ButtonStyle.primary)
    async def nguyen_van(self, itr: discord.Interaction, _):
        """G11: giải thích gắn với hành động tiếp theo — học viên tự đối chiếu bot
        có bịa không, không phải tin lời bot."""
        tr = sources.load_transcript(self.sid)
        codes = [c for m in self.b.muc_goc for c in
                 next((x.codes for x in tr.blocks if x.idx == m), [])]
        txt = f"**Nguyên văn block #{self.b.idx}** ({len(codes)} đoạn)\n\n"
        for c in codes:
            them = f"`[{c}]` {tr.paragraphs[c]}\n\n"
            if len(txt) + len(them) > 1850:
                txt += f"_… còn {len(codes) - codes.index(c)} đoạn — mã `[{codes[-1]}]` là đoạn cuối._"
                break
            txt += them
        await itr.response.send_message(_cut(txt, 1950), ephemeral=True)

    @discord.ui.button(label="⚠️ Sai chỗ nào?", style=discord.ButtonStyle.danger)
    async def sai_cho_nao(self, itr: discord.Interaction, _):
        await itr.response.send_message(
            f"Block #{self.b.idx} sai ở đâu?", view=KhoiLoi(self.sid, self.b.idx,
                                                            self.b.tieu_de),
            ephemeral=True)


# ── Mục lục: Select chọn block ───────────────────────────────────────────────

class MucLuc(discord.ui.View):
    """Persistent — custom_id cố định theo buổi, recap đọc lại từ cache đĩa."""

    def __init__(self, sid: str, r: Recap | None = None):
        super().__init__(timeout=None)
        self.sid = sid
        self.add_item(ChonBlock(sid, r))
        if r is None or r.chua_gan_duoc:
            self.add_item(NutChuaGan(sid))


class ChonBlock(discord.ui.Select):
    def __init__(self, sid: str, r: Recap | None):
        opts = []
        if r:
            for b in r.blocks:
                cum = sum(c["so_nguoi"] for c in b.cum_thac_mac)
                mo_ta = b.badge.replace("✅ ", "").replace("⚠️ ", "⚠ ")
                if cum:
                    mo_ta += f" · {cum} bạn từng vướng"
                opts.append(discord.SelectOption(
                    label=_cut(f"#{b.idx} · {b.tieu_de}", 100),
                    value=str(b.idx), description=_cut(mo_ta, 100),
                    emoji="💬" if b.cum_thac_mac else "📄"))
        super().__init__(
            custom_id=f"recap:block:{sid}",          # ≤100 ký tự
            placeholder=f"📚 Chọn block để đọc ({len(opts)} block)" if opts
                        else "📚 Chọn block",
            options=opts or [discord.SelectOption(label="(chưa dựng recap)", value="0")],
            min_values=1, max_values=1)
        self.sid = sid

    async def callback(self, itr: discord.Interaction):
        r = build_recap(self.sid, itr.client.core)     # cache ⇒ tức thì
        b = next((x for x in r.blocks if x.idx == int(self.values[0])), None)
        if b is None:
            return await itr.response.send_message("Không tìm thấy block đó.",
                                                   ephemeral=True)
        await itr.response.send_message(block_text(r, b),
                                        view=HanhDongBlock(self.sid, b),
                                        ephemeral=True)


class NutChuaGan(discord.ui.Button):
    """G10: cụm không đủ chắc thì hiện riêng, không gán bừa vào block."""

    def __init__(self, sid: str):
        super().__init__(label="❓ Thắc mắc chưa gán được",
                         style=discord.ButtonStyle.secondary,
                         custom_id=f"recap:chuagan:{sid}")
        self.sid = sid

    async def callback(self, itr: discord.Interaction):
        r = build_recap(self.sid, itr.client.core)
        if not r.chua_gan_duoc:
            return await itr.response.send_message(
                "Buổi này mọi cụm thắc mắc đều gán được vào một block.", ephemeral=True)
        t = ("❓ **Chưa gán được** — mình chưa đủ chắc các thắc mắc này thuộc phần nào,"
             " nên không gán bừa:\n\n")
        for c in r.chua_gan_duoc:
            t += (f"• *{c['chu_de']}* ({c['so_nguoi']} người) — {c['vi_sao_chua_gan']}"
                  + (f", confidence {c['confidence']}" if c["confidence"] else "") + "\n")
        await itr.response.send_message(_cut(t, 1950), ephemeral=True)


def header(r: Recap) -> str:
    """Message đầu — đứng một mình phải nói đủ phạm vi (G1) và giới hạn (G2)."""
    n_slide = len(sources.load_slides(r.session_id))
    return (
        f"**📚 Recap {r.buoi}**\n"
        f"Dựng từ bản ghi ({sum(b.so_doan for b in r.blocks)} đoạn)"
        + (f" + slide ({n_slide} trang bản hackathon)" if n_slide else "") + "\n"
        f"**Mình tóm tắt và gom thắc mắc của lớp. Mình không trả lời câu hỏi ngoài "
        f"nguồn buổi học và không biết deadline.**\n\n"
        f"**{len(r.blocks)} block** · {r.do_phu} · đọc hết ~{r.phut_doc:.0f} phút\n"
        + (f"⚠️ đã bỏ {len(r.muc_da_bo)} mục không phải nội dung học: "
           f"{_cut(', '.join(r.muc_da_bo), 200)}\n" if r.muc_da_bo else "")
        + f"đã bỏ {r.cum_bo_le} thắc mắc lẻ (chỉ 1 người hỏi)\n\n"
        "_Chọn block bên dưới — mỗi block trả riêng cho bạn, không làm ngập channel._\n"
        "**Recap không thay bản ghi** — block ⚠️ nên xem lại nguyên văn.")


def dang_ky_persistent(bot):
    """Gọi trong setup_hook: mục lục cũ vẫn bấm được sau khi bot restart."""
    for sid in config.SESSIONS:
        bot.add_view(MucLuc(sid))
