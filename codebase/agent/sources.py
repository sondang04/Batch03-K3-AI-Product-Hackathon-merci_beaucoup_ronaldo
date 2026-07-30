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


def _tim_token(hay: str, tk: str) -> int:
    """Vị trí của token trong chuỗi. Token NGẮN (<5 ký tự) phải khớp theo BIÊN TỪ,
    nếu không 'gia' sẽ khớp bên trong 'giai' (giải) và 'giao' — bug 30/07 làm
    keyword 'giá' đếm ra 208 học viên. Token dài thì cho khớp substring để chịu
    được biến thể ('transformer' trong 'transformers')."""
    if len(tk) < 5:
        m = re.search(rf"(?<!\w){re.escape(tk)}(?!\w)", hay)
        return m.start() if m else -1
    return hay.find(tk)


def _match(haystack_norm: str, toks: list[str]) -> tuple[int, int, int] | None:
    """(số token khớp, vị trí, độ phân tán) — None nếu KHÔNG token nào khớp.

    Khớp MỘT PHẦN được chấp nhận và xếp hạng sau khớp đủ. Lý do: học viên gõ
    trộn Việt-Anh ('attention mechanism'), transcript chỉ có 'attention' —
    đòi đủ token thì agent **từ chối oan** đúng câu buổi học có dạy (bug case
    19/20/23, golden set lượt 1). Điều kiện an toàn vẫn giữ: không token nào
    khớp ⇒ trả None ⇒ đường 'không có căn cứ' vẫn chạy ('ReAct' vẫn 0 kết quả).
    """
    pos = [i for tk in toks if (i := _tim_token(haystack_norm, tk)) >= 0]
    if not pos:
        return None
    return len(pos), min(pos), max(pos) - min(pos)


def _mo_ta_khop(n_khop: int, toks: list[str]) -> str:
    return "đủ token" if n_khop == len(toks) else f"khớp {n_khop}/{len(toks)} token"


def find_block(session_id: str, title_query: str) -> "Block | None":
    """Tìm block theo tên/từ khoá (token AND trên tiêu đề). Có tool này thì model
    không phải đoán block_idx — nguyên nhân bug tóm tắt sai block (30/07)."""
    toks = _tokens(title_query)
    best = None
    for b in load_transcript(session_id).blocks:
        m = _match(_norm(b.title), toks)
        if m is None:
            continue
        if best is None or (-m[0], m[2]) < best[0]:
            best = ((-m[0], m[2]), b)
    return best[1] if best else None


def search_transcript(session_id: str, query: str, limit: int = 8) -> list[dict]:
    tr = load_transcript(session_id)
    toks = _tokens(query)
    scored = []
    for code, text in tr.paragraphs.items():
        m = _match(_norm(text), toks)
        if m is None:
            continue
        n_khop, pos, spread = m
        lo, hi = max(0, pos - 80), pos + 240
        scored.append(((-n_khop, spread), {
            "ma_doan": code, "khop": _mo_ta_khop(n_khop, toks),
            # mã đi LIỀN trong chuỗi trích: model copy pattern nhìn thấy được đáng
            # tin hơn là đọc key JSON rồi tự ghép (bug case 15/21, golden lượt 2)
            "trich": f"[{code}] " + ("…" if lo else "")
                     + " ".join(text[lo:hi].split()) + "…"}))
    scored.sort(key=lambda x: x[0])          # khớp nhiều token & gần nhau ⇒ liên quan hơn
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

# Chỉ thắc mắc HỌC TẬP mới được vào cụm "lớp vướng gì". Đo được: sau khi lọc D+E
# vẫn còn 37% câu là logistics hoặc câu không phải thắc mắc học tập (tải file,
# 'bây h là mấy giờ', 'Canvas là hệ thống gì') — vào cụm thì recap thành nhiễu.
# Hai regex dưới là nhãn A (xin tóm tắt) + B (hỏi khái niệm) của mine_chatlog.py.
HOC_TAP = re.compile(
    r"là gì|nghĩa là|giải thích|nói rõ|làm rõ|khác nhau|khác gì|so sánh|ví dụ"
    r"|vì sao|tại sao|như thế nào|cách hoạt động|tóm tắt|tóm lại|ý chính"
    r"|nội dung chính|keyword", re.I)
LOGISTICS = re.compile(
    r"tải|download|link|slide.*ở đâu|ở đâu.*slide|deadline|nộp bài|canvas|lịch học"
    r"|hôm nay học gì|mấy giờ|điểm danh|zoom|workspace|tài liệu.*đâu", re.I)


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
            rows.append({"m": r["message_id"], "u": r["user_id"], "q": q,
                         "hoc_tap": bool(HOC_TAP.search(q)) and not LOGISTICS.search(q)})
    return rows


RE_MA_HV = re.compile(r"\bU\d{3,4}\b|\bmã học viên\b|\bai (đã |từng )?hỏi\b", re.I)


def peer_questions(topic: str, limit: int = 6) -> dict:
    """Thắc mắc THẬT của lớp khớp chủ đề. Chỉ trả cụm ≥2 học viên khác nhau;
    output chứa số người + mã M, KHÔNG chứa mã học viên (spec §5 #13)."""
    if RE_MA_HV.search(topic):
        # Chặn ngay ở TOOL. Bài học case 12 (golden set lượt 1): model không lấy
        # được mã học viên từ tool, nhưng nó gọi peer_questions("Day 1") rồi TỰ BỊA
        # rằng các câu đó thuộc U0270. Nhìn y như rò dữ liệu.
        return {"tu_choi": "Không tra thắc mắc theo danh tính/mã học viên. "
                           "Cụm thắc mắc chỉ hiện theo SỐ NGƯỜI.",
                "chu_de": topic, "so_nguoi": 0, "cum": []}
    toks = _tokens(topic)
    matched = [r for r in _load_student_rows()
               if r["hoc_tap"] and _match(_norm(r["q"]), toks) is not None]
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
            "cum": examples,
            # Nhắc ngay trong kết quả tool — model đã từng bịa gán các câu này
            # cho một mã học viên cụ thể (case 12).
            "canh_bao": "Đây là dữ liệu GỘP của nhiều học viên. TUYỆT ĐỐI không "
                        "gán các câu này cho bất kỳ cá nhân hay mã học viên nào."}


def cluster_for_keyword(kw: str, toi_thieu_nguoi: int = 2) -> dict | None:
    """Cụm thắc mắc cho MỘT keyword. Trả None nếu <N học viên khác nhau hỏi.

    Ứng viên cụm KHÔNG tự trích từ chatlog nữa: token tiếng Việt bỏ dấu vô nghĩa
    ('dung', 'chinh', 'phan' — thử rồi, ra rác). Thay vào đó dùng chính dòng
    🔑 Keyword mà AI call 2 sinh cho từng block — đó là **thuật ngữ nguyên văn của
    giảng viên**, nên vừa là khái niệm thật, vừa đã gắn sẵn với một block.
    """
    kw = kw.strip()
    if len(kw) < 3:
        return None
    c = peer_questions(kw, limit=3)
    if c["so_nguoi"] < toi_thieu_nguoi or not c["cum"]:
        return None
    return {"chu_de": kw, "so_nguoi": c["so_nguoi"], "so_cau": c["so_cau"],
            "vi_du": c["cum"]}


RE_KEYWORD = re.compile(r"^\s*(?:[🔑*_\- ]*)?\**\s*keyword\s*\**\s*[:：]\s*(.+)$",
                        re.I | re.M)


def parse_keywords(tom_tat: str) -> list[str]:
    """Lấy danh sách keyword từ dòng '🔑 Keyword: a · b · c' của bản tóm tắt."""
    m = RE_KEYWORD.search(tom_tat)
    if not m:
        return []
    raw = re.sub(r"\*+", "", m.group(1))
    parts = re.split(r"[·,;/]|\s+-\s+", raw)
    return [p.strip(" .*_") for p in parts if 3 <= len(p.strip(" .*_")) <= 40]


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
        n_khop, pos, spread = m
        lo, hi = max(0, pos - 70), pos + 220
        scored.append(((-n_khop, spread), {
            "trang": page, "tieu_de": slide_title(text),
            "khop": _mo_ta_khop(n_khop, toks),
            "trich": ("…" if lo else "") + " ".join(text[lo:hi].split()) + "…"}))
    scored.sort(key=lambda x: x[0])
    return [h for _, h in scored[:limit]]
