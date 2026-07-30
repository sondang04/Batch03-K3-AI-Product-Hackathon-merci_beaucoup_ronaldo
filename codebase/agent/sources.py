"""Tầng nguồn sự thật: transcript (block + đoạn có mã), chatlog (thắc mắc lớp),
slides (manifest ảnh). Toàn bộ deterministic — không gọi AI ở tầng này.

Nguyên tắc bảo mật (README data pack):
- Không bao giờ trả `user_id` của học viên ra ngoài — chỉ trả SỐ NGƯỜI + mã M.
- Nội dung chatlog là DỮ LIỆU đầu vào, không phải chỉ thị (lớp ③, injection).
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import config

# ── Transcript ───────────────────────────────────────────────────────────────

RE_DOAN = re.compile(r"\*\*\[(T\d{2}-\d{3})\]\*\*\s*(.*?)(?=\n\*\*\[T\d{2}-\d{3}\]\*\*|\n## |\Z)", re.S)
RE_HEADING = re.compile(r"^## (.+)$", re.M)

# Mục không phải nội dung học (mining B13) — loại khỏi recap, nhưng khai báo
NON_CORE = re.compile(
    r"chào lớp|giới thiệu giảng viên|làm quen|bên lề|tương tác cuối|trò chuyện"
    r"|phát thẻ|kết phần chia sẻ|K12|trao đổi về hệ thống", re.I)


@dataclass
class Block:
    idx: int
    title: str
    codes: list[str] = field(default_factory=list)
    non_core: bool = False


@dataclass
class Transcript:
    session_id: str
    ten: str
    blocks: list[Block]
    paragraphs: dict[str, str]      # mã đoạn -> nguyên văn

    def block_by_idx(self, idx: int) -> Block | None:
        return next((b for b in self.blocks if b.idx == idx), None)


@lru_cache(maxsize=8)
def load_transcript(session_id: str) -> Transcript:
    ses = config.SESSIONS[session_id]
    text = (config.TRANSCRIPT_DIR / ses["transcript"]).read_text(encoding="utf-8")

    paragraphs = {m.group(1): m.group(2).strip() for m in RE_DOAN.finditer(text)}

    blocks: list[Block] = []
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    for i, sec in enumerate(sections, start=1):
        title = sec.split("\n", 1)[0].strip()
        codes = re.findall(r"\*\*\[(T\d{2}-\d{3})\]\*\*", sec)
        blocks.append(Block(idx=i, title=title, codes=codes,
                            non_core=bool(NON_CORE.search(title))))
    return Transcript(session_id=session_id, ten=ses["ten"],
                      blocks=blocks, paragraphs=paragraphs)


def _norm(s: str) -> str:
    """lowercase + bỏ dấu, để 'mua dong' khớp 'mùa đông'."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Từ chức năng — bỏ khi tách token, để "hai mùa đông" khớp "hai lần mùa đông"
STOPWORD = {"la", "cua", "va", "co", "cai", "nhung", "mot", "cac", "thi", "ve",
            "trong", "gi", "nao", "the", "duoc", "cho", "voi", "khi", "nay"}


def _tokens(q: str) -> list[str]:
    """Tách truy vấn thành token đã bỏ dấu, loại từ chức năng và token quá ngắn."""
    toks = [w for w in re.split(r"\W+", _norm(q)) if len(w) >= 2 and w not in STOPWORD]
    return toks or [_norm(q).strip()]


def _match(haystack_norm: str, toks: list[str]) -> tuple[int, int] | None:
    """(vị trí, độ phân tán) nếu MỌI token đều xuất hiện (không cần liền mạch),
    None nếu thiếu token. Đây là lý do 'hai mùa đông' khớp 'hai lần mùa đông'.
    Độ phân tán = khoảng cách giữa token đầu và cuối → càng nhỏ càng liên quan."""
    positions = []
    for tk in toks:
        i = haystack_norm.find(tk)
        if i < 0:
            return None
        positions.append(i)
    return min(positions), max(positions) - min(positions)


def find_block(session_id: str, title_query: str) -> "Block | None":
    """Tìm block theo tên/từ khoá (token AND trên tiêu đề). Có tool này thì model
    không phải đoán block_idx — nguyên nhân bug tóm tắt sai block (30/07)."""
    toks = _tokens(title_query)
    best = None
    for b in load_transcript(session_id).blocks:
        m = _match(_norm(b.title), toks)
        if m is None:
            continue
        if best is None or m[1] < best[0]:
            best = (m[1], b)
    return best[1] if best else None


def search_transcript(session_id: str, query: str, limit: int = 8) -> list[dict]:
    tr = load_transcript(session_id)
    toks = _tokens(query)
    scored = []
    for code, text in tr.paragraphs.items():
        m = _match(_norm(text), toks)
        if m is None:
            continue
        pos, spread = m
        lo, hi = max(0, pos - 80), pos + 240
        scored.append((spread, {"ma_doan": code,
                                "trich": ("…" if lo else "")
                                         + " ".join(text[lo:hi].split()) + "…"}))
    scored.sort(key=lambda x: x[0])          # token gần nhau ⇒ liên quan hơn
    return [h for _, h in scored[:limit]]


def search_all_sessions(query: str, limit_per: int = 4) -> dict:
    """Tìm xuyên MỌI buổi. Dùng khi câu hỏi không nêu buổi nào — thà quét hết
    còn hơn đoán một buổi rồi kết luận sai là 'không có' (bug S2, 30/07)."""
    out = {}
    for sid, ses in config.SESSIONS.items():
        tr = search_transcript(sid, query, limit=limit_per)
        sl = search_slides(sid, query, limit=limit_per)
        if tr or sl:
            out[sid] = {"buoi": ses["ten"], "transcript": tr, "slide": sl}
    return out


# ── Chatlog: thắc mắc của lớp ────────────────────────────────────────────────

PREFIX_SELECTION = re.compile(r"^\(Trang \d+, đoạn được chọn: .*?\)\s*", re.S)
# Nhãn D (probe/jailbreak) và E (tin cụt) — lọc TRƯỚC khi bất kỳ nội dung
# chatlog nào đi vào context của agent (spec §5 #9, #12).
PROBE = re.compile(
    r"password|api key|guardrail|jailbreak|bỏ qua.*quy tắc|base64|prompt injection"
    r"|kiểm tra bảo mật|admin|pretrain|fine tune|model của bạn|bạn dùng api", re.I)
MIN_LEN = 12


@lru_cache(maxsize=1)
def _load_student_rows() -> list[dict]:
    rows = []
    with open(config.CHATLOG_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["role"] != "student":
                continue
            q = PREFIX_SELECTION.sub("", r["content"] or "").strip()
            if len(q) < MIN_LEN or PROBE.search(q):
                continue                      # nhãn E / D — không vào context
            rows.append({"m": r["message_id"], "u": r["user_id"], "q": q})
    return rows


def peer_questions(topic: str, limit: int = 6) -> dict:
    """Thắc mắc THẬT của lớp khớp chủ đề. Chỉ trả cụm ≥2 học viên khác nhau;
    output chứa số người + mã M, KHÔNG chứa mã học viên (spec §5 #13)."""
    t = _norm(topic)
    matched = [r for r in _load_student_rows() if t in _norm(r["q"])]
    n_users = len({r["u"] for r in matched})
    if n_users < 2:
        return {"chu_de": topic, "so_cau": len(matched), "so_nguoi": n_users,
                "cum": [], "ghi_chu": "dưới 2 học viên — không dựng cụm (spec §5 #8)"}
    seen, examples = set(), []
    for r in matched:
        key = _norm(r["q"])[:60]
        if key in seen:
            continue
        seen.add(key)
        examples.append({"ma": r["m"], "cau_hoi": r["q"][:160]})
        if len(examples) >= limit:
            break
    return {"chu_de": topic, "so_cau": len(matched), "so_nguoi": n_users,
            "cum": examples}


# ── Slides (bản hackathon trong data pack — CÓ text layer) ───────────────────

@lru_cache(maxsize=4)
def load_slides(session_id: str) -> dict[int, str]:
    """{số trang -> text của trang}. Đọc trực tiếp PDF bằng pypdf: ~12ms/trang,
    deterministic, không vision/OCR. Trang trong data pack đều có text layer
    (đã đo: 0/29 trang rỗng ở cả hai deck)."""
    pdf = config.SESSIONS[session_id].get("deck_pdf")
    if not pdf:
        return {}
    path = config.SLIDES_PDF_DIR / pdf
    if not path.exists():
        return {}
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return {i: (pg.extract_text() or "").strip()
            for i, pg in enumerate(reader.pages, start=1)}


def slide_title(text: str) -> str:
    """Tiêu đề slide = dòng có nội dung đầu tiên, bỏ header/footer lặp."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 3 and not line.startswith("AI IN ACTION"):
            return line[:100]
    return "(không có tiêu đề)"


def search_slides(session_id: str, query: str, limit: int = 6) -> list[dict]:
    toks = _tokens(query)
    scored = []
    for page, text in load_slides(session_id).items():
        m = _match(_norm(text), toks)
        if m is None:
            continue
        pos, spread = m
        lo, hi = max(0, pos - 70), pos + 220
        scored.append((spread, {"trang": page, "tieu_de": slide_title(text),
                                "trich": ("…" if lo else "")
                                         + " ".join(text[lo:hi].split()) + "…"}))
    scored.sort(key=lambda x: x[0])
    return [h for _, h in scored[:limit]]
