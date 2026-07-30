"""Pipeline `/recap` — quyết định TRUNG TÂM của lát cắt (spec §4).

Trước file này, agent chỉ có Q&A: `list_blocks` đọc heading có sẵn (21 mục, không
phải 8-15 block), và không có gì gán cụm thắc mắc vào block. Tức **AI call 1 và
AI call 3 trong spec §4 chưa tồn tại** — chiều C2 của quality bar không có gì để chấm.

Ba lời gọi AI, đúng như spec khai:
  AI call 1 — GỘP mục thô thành 8-15 block học được (automate: sai thì rẻ, học
              viên thấy ngay vì mỗi block mang dải mã đoạn).
  AI call 2 — TÓM TẮT từng block: 4-6 gạch + mã đoạn + dòng 🔑 Keyword.
  AI call 3 — GÁN cụm thắc mắc vào block (**conditional**): không đủ chắc thì
              đẩy vào `chua_gan_duoc`, KHÔNG gán bừa (spec §5 #15).

Kết quả cache xuống đĩa để demo không phải chờ và để chạy lại rẻ.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict

from . import config, sources

CACHE_DIR = config.REPO / "codebase" / "data" / "recap-cache"

BLOCK_MIN, BLOCK_MAX = 8, 15
CONF_TOI_THIEU = 0.6          # dưới ngưỡng ⇒ không gán (conditional, spec §4)
CUM_TOI_DA = 12               # cụm/buổi: nhiều hơn thì recap thành nhiễu
LO_GAN = 6                    # cụm/lô khi gọi AI call 3 (40 cụm/lô → model trả rỗng)


# ── AI call 1: gộp mục thô → 8-15 block ──────────────────────────────────────

GOP_SYSTEM = (
    "Bạn gộp các mục của một bản ghi bài giảng thành 8-15 BLOCK học được.\n"
    "Luật:\n"
    "1. Chỉ GỘP các mục LIỀN KỀ nhau — không đảo thứ tự, không tách một mục ra.\n"
    "2. Gộp khi hai mục cùng một ý lớn; giữ riêng khi là hai ý khác nhau.\n"
    "3. Tiêu đề block phải nói ĐƯỢC GÌ khi học phần đó, không phải 'Phần 2'.\n"
    "4. Mọi mục đầu vào phải xuất hiện đúng một lần trong kết quả.\n"
    'Trả DUY NHẤT JSON: {"blocks":[{"tieu_de":"...","muc":[1,2]}, ...]}'
)


def _goi_json(client, system: str, user: str, fallback):
    """Gọi AI và parse JSON, chịu được ```json fence. Lỗi thì trả fallback."""
    raw = client.subcall(system, user)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return fallback, f"không tìm thấy JSON trong output ({len(raw)} ký tự)"
    try:
        return json.loads(m.group(0)), None
    except json.JSONDecodeError as e:
        return fallback, f"JSON lỗi: {e}"


def gop_block(client, session_id: str) -> tuple[list[dict], str | None]:
    tr = sources.load_transcript(session_id)
    core = [b for b in tr.blocks if not b.non_core]
    bo = [b.title for b in tr.blocks if b.non_core]

    if len(core) <= BLOCK_MAX:                       # đã đủ mịn, không cần AI
        return ([{"tieu_de": b.title, "muc": [b.idx]} for b in core],
                f"{len(core)} mục ≤ {BLOCK_MAX} nên giữ nguyên, không gọi AI")

    danh_sach = "\n".join(f"{b.idx}. {b.title} ({len(b.codes)} đoạn)" for b in core)
    data, err = _goi_json(
        client, GOP_SYSTEM,
        f"Buổi: {tr.ten}\nCác mục (đã bỏ {len(bo)} mục chào lớp/bên lề):\n{danh_sach}\n\n"
        f"Gộp thành {BLOCK_MIN}-{BLOCK_MAX} block.",
        fallback={"blocks": [{"tieu_de": b.title, "muc": [b.idx]} for b in core]})
    blocks = data.get("blocks") or []

    # Kiểm tính toàn vẹn: mọi mục core phải xuất hiện đúng một lần. AI gộp sai
    # thì thà quay về mục thô còn hơn làm mất/nhân đôi nội dung buổi học.
    da_dung = [i for b in blocks for i in b.get("muc", [])]
    can_co = {b.idx for b in core}
    if sorted(da_dung) != sorted(can_co):
        thieu = sorted(can_co - set(da_dung))
        return ([{"tieu_de": b.title, "muc": [b.idx]} for b in core],
                f"AI gộp không toàn vẹn (thiếu mục {thieu}) → dùng mục thô")
    return blocks, err


# ── AI call 3: gán cụm thắc mắc vào block ────────────────────────────────────

GAN_SYSTEM = (
    "Bạn gán các CỤM THẮC MẮC của học viên vào đúng block của buổi học.\n"
    "Luật:\n"
    "1. Chỉ gán khi cụm thật sự nói về nội dung của block đó.\n"
    "2. KHÔNG ĐỦ CHẮC thì đặt block=null — thà để trống hơn gán bừa. Gán sai làm\n"
    "   học viên tưởng chỗ đó là chỗ khó của lớp rồi học lệch, và họ KHÔNG tự phát\n"
    "   hiện được.\n"
    "3. Mỗi cụm kèm một block GỢI Ý (nơi keyword xuất hiện). Gợi ý thường đúng,\n"
    "   nhưng bạn PHẢI tự kiểm: keyword có thể trùng chữ mà khác ý.\n"
    "4. confidence: 0.0-1.0, phản ánh mức chắc thật.\n"
    'Trả DUY NHẤT JSON: {"gan":[{"cum":"<chủ đề>","block":<số|null>,'
    '"confidence":0.0,"ly_do":"<1 câu>"}]}'
)


def gan_cum(client, blocks: list[dict], clusters: list[dict]) -> tuple[list[dict], str | None]:
    """Gán theo LÔ. Thử gộp 40 cụm vào một lời gọi thì gpt-4o-mini trả rỗng hoàn
    toàn (30/07) — chia lô nhỏ vừa chắc vừa dễ chẩn đoán khi một lô lỗi."""
    if not clusters:
        return [], "buổi này không có cụm thắc mắc nào (≥2 học viên) để gán"
    ds_block = "\n".join(f"{i}. {b['tieu_de']}" for i, b in enumerate(blocks, 1))
    gan, loi = [], []
    for k in range(0, len(clusters), LO_GAN):
        lo = clusters[k:k + LO_GAN]
        ds_cum = "\n".join(
            f"- {c['chu_de']} ({c['so_nguoi']} học viên) — keyword này đến từ block "
            f"{c.get('block_goi_y', '?')}: vd \"{c['vi_du'][0]['cau_hoi'][:90]}\""
            for c in lo)
        data, err = _goi_json(
            client, GAN_SYSTEM,
            f"Block của buổi:\n{ds_block}\n\nGán {len(lo)} cụm sau:\n{ds_cum}",
            fallback={"gan": []})
        gan += data.get("gan") or []
        if err:
            loi.append(f"lô {k // LO_GAN + 1}: {err}")
    return gan, "; ".join(loi) or None


# ── Kết quả ──────────────────────────────────────────────────────────────────

@dataclass
class BlockRecap:
    idx: int
    tieu_de: str
    muc_goc: list[int]
    ma_dau: str
    ma_cuoi: str
    so_doan: int
    tom_tat: str
    so_gach: int = 0
    so_gach_co_ma: int = 0
    co_khong_nghe_ro: bool = False
    cum_thac_mac: list[dict] = field(default_factory=list)

    @property
    def badge(self) -> str:
        if self.so_gach and self.so_gach_co_ma == self.so_gach:
            b = f"✅ {self.so_gach_co_ma}/{self.so_gach} ý có mã đoạn"
        else:
            b = f"⚠️ chỉ {self.so_gach_co_ma}/{self.so_gach} ý có mã đoạn"
        if self.co_khong_nghe_ro:
            b += " · ⚠️ bản ghi mất tiếng trong block này"
        return b


@dataclass
class Recap:
    session_id: str
    buoi: str
    blocks: list[BlockRecap]
    muc_da_bo: list[str]
    chua_gan_duoc: list[dict]
    cum_bo_le: int
    canh_bao: list[str]
    so_tu_goc: int
    so_tu_recap: int
    n_ai_calls: int
    giay: float

    @property
    def do_phu(self) -> str:
        p = 100 * self.so_tu_recap / self.so_tu_goc if self.so_tu_goc else 0
        return f"Recap giữ ~{p:.0f}% số từ của buổi ({self.so_tu_recap:,}/{self.so_tu_goc:,} từ)"

    @property
    def phut_doc(self) -> float:
        return self.so_tu_recap / 200          # đọc tiếng Việt ~200 từ/phút


def build_recap(session_id: str, client, dung_cache: bool = True) -> Recap:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{session_id}-{client.model}.json"
    if dung_cache and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        d["blocks"] = [BlockRecap(**b) for b in d["blocks"]]
        return Recap(**d)

    t0 = time.time()
    n_ai = 0
    canh_bao: list[str] = []
    tr = sources.load_transcript(session_id)
    ma_theo_muc = {b.idx: b.codes for b in tr.blocks}

    # AI call 1 — gộp block
    raw_blocks, err = gop_block(client, session_id)
    if err:
        canh_bao.append(f"gộp block: {err}")
    if "không gọi AI" not in (err or ""):
        n_ai += 1

    # AI call 2 — tóm tắt từng block
    from .tools import SUMMARIZE_SYSTEM
    blocks: list[BlockRecap] = []
    so_tu_goc = so_tu_recap = 0
    for i, rb in enumerate(raw_blocks, start=1):
        codes = [c for m in rb["muc"] for c in ma_theo_muc.get(m, [])]
        if not codes:
            continue
        body = "\n\n".join(f"[{c}] {tr.paragraphs[c]}" for c in codes)
        so_tu_goc += len(body.split())
        tom_tat = client.subcall(
            SUMMARIZE_SYSTEM,
            f"Block: {rb['tieu_de']}\n\n{body}\n\nTóm tắt theo luật trên.")
        n_ai += 1
        so_tu_recap += len(tom_tat.split())
        gach = [l for l in tom_tat.splitlines()
                if l.strip().startswith(("-", "•", "*")) or re.match(r"^\s*\d+\.", l)]
        blocks.append(BlockRecap(
            idx=i, tieu_de=rb["tieu_de"], muc_goc=rb["muc"],
            ma_dau=codes[0], ma_cuoi=codes[-1], so_doan=len(codes), tom_tat=tom_tat,
            so_gach=len(gach),
            so_gach_co_ma=sum(1 for g in gach if re.search(r"\[T\d{2}-\d{3}\]", g)),
            co_khong_nghe_ro=any("[không nghe rõ]" in tr.paragraphs[c] for c in codes)))

    # Ứng viên cụm = keyword do AI call 2 sinh ra cho từng block (thuật ngữ nguyên
    # văn của giảng viên), đối chiếu với chatlog. Keyword nào có ≥2 học viên khác
    # nhau hỏi thì thành cụm; chỉ 1 người thì đếm vào "bỏ lẻ" và khai báo.
    clusters, kw_le = [], 0
    da_thay = set()
    for b in blocks:
        for kw in sources.parse_keywords(b.tom_tat):
            k = kw.lower()
            if k in da_thay:
                continue
            da_thay.add(k)
            c = sources.cluster_for_keyword(kw)
            if c:
                c["block_goi_y"] = b.idx          # keyword đến TỪ block này
                clusters.append(c)
            elif sources.cluster_for_keyword(kw, toi_thieu_nguoi=1):
                kw_le += 1
    # giữ cụm nhiều người hỏi nhất — recap 40 cụm thì học viên không đọc nổi
    clusters.sort(key=lambda c: -c["so_nguoi"])
    if len(clusters) > CUM_TOI_DA:
        kw_le += 0
        canh_bao.append(f"có {len(clusters)} cụm, giữ {CUM_TOI_DA} cụm nhiều người hỏi nhất")
        clusters = clusters[:CUM_TOI_DA]
    gan, err3 = gan_cum(client, [asdict(b) for b in blocks], clusters)
    if err3:
        canh_bao.append(f"gán cụm: {err3}")
    if clusters:
        n_ai += (len(clusters) + LO_GAN - 1) // LO_GAN

    theo_chu_de = {c["chu_de"]: c for c in clusters}
    chua_gan: list[dict] = []
    da_gan = set()
    for g in gan:
        c = theo_chu_de.get(g.get("cum"))
        if c is None:
            continue
        da_gan.add(c["chu_de"])
        bi, conf = g.get("block"), float(g.get("confidence") or 0)
        muc = {"chu_de": c["chu_de"], "so_nguoi": c["so_nguoi"],
               "vi_du": c["vi_du"][:2], "confidence": round(conf, 2),
               "ly_do": g.get("ly_do", "")}
        if bi and 1 <= bi <= len(blocks) and conf >= CONF_TOI_THIEU:
            blocks[bi - 1].cum_thac_mac.append(muc)
        else:
            muc["vi_sao_chua_gan"] = ("confidence thấp" if bi else "không thuộc block nào")
            chua_gan.append(muc)
    # cụm AI bỏ sót cũng phải hiện, không được im lặng biến mất
    for c in clusters:
        if c["chu_de"] not in da_gan:
            chua_gan.append({"chu_de": c["chu_de"], "so_nguoi": c["so_nguoi"],
                             "vi_du": c["vi_du"][:2], "confidence": 0.0,
                             "vi_sao_chua_gan": "AI không trả kết quả cho cụm này"})

    r = Recap(session_id=session_id, buoi=tr.ten, blocks=blocks,
              muc_da_bo=[b.title for b in tr.blocks if b.non_core],
              chua_gan_duoc=chua_gan,
              cum_bo_le=kw_le,
              canh_bao=canh_bao, so_tu_goc=so_tu_goc, so_tu_recap=so_tu_recap,
              n_ai_calls=n_ai, giay=round(time.time() - t0, 1))
    d = asdict(r)
    cache.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


# ── Render ra text (Discord/web dùng chung) ──────────────────────────────────

def render(r: Recap) -> list[str]:
    """Trả list message — mỗi block một message, đúng hình dung thread Discord."""
    out = [
        f"**Recap {r.buoi}**\n"
        f"Dựng từ bản ghi ({sum(b.so_doan for b in r.blocks)} đoạn)"
        + (f" + slide ({len(sources.load_slides(r.session_id))} trang bản hackathon)"
           if sources.load_slides(r.session_id) else "") + "\n"
        f"**Mình tóm tắt và gom thắc mắc của lớp. Mình không trả lời câu hỏi ngoài "
        f"nguồn buổi học và không biết deadline.**\n\n"
        f"📚 {len(r.blocks)} block · {r.do_phu} · đọc hết ~{r.phut_doc:.0f} phút\n"
        + (f"⚠️ đã bỏ {len(r.muc_da_bo)} mục không phải nội dung học: "
           f"{', '.join(r.muc_da_bo)}\n" if r.muc_da_bo else "")
    ]
    for b in r.blocks:
        m = (f"**#{b.idx} · {b.tieu_de}**\n{b.badge} · `[{b.ma_dau}]`..`[{b.ma_cuoi}]`\n\n"
             f"{b.tom_tat}\n")
        for c in b.cum_thac_mac:
            m += (f"\n💬 **Bạn học từng vướng gì ở đây** ({c['so_nguoi']} người)\n"
                  f"   Cụm *{c['chu_de']}* — vd: \"{c['vi_du'][0]['cau_hoi'][:110]}\" "
                  f"`[{c['vi_du'][0]['ma']}]`\n   ↳ {c['ly_do']}\n")
        out.append(m)
    if r.chua_gan_duoc:
        m = ("❓ **Chưa gán được** — mình chưa đủ chắc các thắc mắc này thuộc phần nào:\n")
        for c in r.chua_gan_duoc:
            m += (f"• *{c['chu_de']}* ({c['so_nguoi']} người) — {c['vi_sao_chua_gan']}"
                  + (f", confidence {c['confidence']}" if c["confidence"] else "") + "\n")
        out.append(m)
    cuoi = f"đã bỏ {r.cum_bo_le} thắc mắc lẻ (chỉ 1 người hỏi)\n"   # khai cả khi 0
    cuoi += "**Recap không thay bản ghi** — block ⚠️ nên xem lại nguyên văn."
    if r.canh_bao:
        cuoi += "\n\n🔧 " + " · ".join(r.canh_bao)
    out.append(cuoi)
    return out
