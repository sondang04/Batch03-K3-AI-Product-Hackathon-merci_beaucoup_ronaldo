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


def search_transcript(session_id: str, query: str, limit: int = 8) -> list[dict]:
    tr = load_transcript(session_id)
    q = _norm(query)
    hits = []
    for code, text in tr.paragraphs.items():
        pos = _norm(text).find(q)
        if pos < 0:
            continue
        lo, hi = max(0, pos - 80), pos + len(q) + 160
        hits.append({"ma_doan": code, "trich": ("…" if lo else "") + text[lo:hi] + "…"})
        if len(hits) >= limit:
            break
    return hits


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


# ── Slides ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def slide_manifest(deck: str) -> dict[int, dict]:
    import json
    path = config.SLIDES_DIR / deck / "manifest.jsonl"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        out[r["page"]] = r
    return out
