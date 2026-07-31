"""Cấu hình chung cho agent `/recap` — đường dẫn, model, giới hạn."""

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Nạp .env ở gốc repo (OPENAI_API_KEY, ...) — .env đã bị gitignore chặn,
# key không bao giờ vào git (luật an toàn guide §3.4).
try:
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
except ImportError:
    pass
DATA = REPO / "data" / "vlearn-pack"
TRANSCRIPT_DIR = DATA / "transcript"
CHATLOG_CSV = DATA / "chatlog" / "chat_history_anonymized_for_hackathon.csv"
SLIDES_PDF_DIR = DATA / "slides"          # slide bản hackathon (trong data pack)
SLIDES_DIR = REPO / "codebase" / "data" / "slides"   # (cũ) output tách từ scroll-capture
LOGS_DIR = REPO / "codebase" / "logs"
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# ── Model ────────────────────────────────────────────────────────────────────
# Provider chọn qua env AGENT_PROVIDER: openai | anthropic | gemini | mock
# (mock = offline, dùng cho test suite — không cần key, không cần mạng)
# Mặc định: openai / gpt-4o-mini (quyết định nhóm 30/07 — xem spec §9).
PROVIDER = os.environ.get("AGENT_PROVIDER", "openai")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash")  # tên model thấy trong chatlog production của VLearn

MAX_TOKENS = 4096          # câu trả lời cỡ Discord, không phải văn bản dài
MAX_TURNS = 8              # số vòng tool-call tối đa / 1 câu hỏi

# ── Bảo mật log ──────────────────────────────────────────────────────────────
# Trace giữ trong repo (rubric R5 yêu cầu log/trace), nhưng data pack thuộc quy
# định bảo mật → mọi nội dung nguồn trong trace bị CẮT còn TRUNCATE ký tự và
# luôn kèm mã (Txx-NNN / M-code) để đối chiếu lại được từ data pack gốc.
TRUNCATE = 200

# ── Buổi học ─────────────────────────────────────────────────────────────────
# Registry buổi: transcript nào + deck slide nào. Chatlog KHÔNG map được theo
# ID (spec §4 giới hạn #1) nên thắc mắc lớp được khớp theo NỘI DUNG, không join.
#
# Nguồn registry (ưu tiên):
#   1. data/vlearn-pack/sessions.json  ← UI admin CRUD được (mentor tự tạo buổi)
#   2. _HARDCODED_SESSIONS dưới đây    ← fallback khi chưa có file (back-compat)
SESSIONS_FILE = DATA / "sessions.json"
_HARDCODED_SESSIONS: dict[str, dict] = {
    "day01": {
        "ten": "Day 1 — AI & LLM Foundation (giảng viên Blue)",
        "transcript": "transcript-04-clean.md",
        "prefix": "T04",
        # Slide bản hackathon trong data pack: 29 trang, CÓ text layer đầy đủ
        # (0 trang ảnh) → đọc trực tiếp bằng pypdf, không cần vision/OCR.
        "deck_pdf": "d1-slide-hackathon.pdf",
        "deck_ten": "d1-slide-hackathon (bản hackathon, 29 trang)",
    },
    "day02-sang": {
        "ten": "Day 2 sáng — Xác định bài toán kinh doanh cho AI",
        "transcript": "transcript-01-clean.md",
        "prefix": "T01",
        "deck_pdf": "d2-slide-hackathon.pdf",
        "deck_ten": "d2-slide-hackathon (bản hackathon, 29 trang)",
    },
}


def _load_sessions() -> dict[str, dict]:
    """Đọc registry từ JSON nếu có, fallback về hard-coded."""
    if SESSIONS_FILE.exists():
        try:
            data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_HARDCODED_SESSIONS)


SESSIONS: dict[str, dict] = _load_sessions()


def reload_sessions() -> dict[str, dict]:
    """Đọc lại registry từ JSON — gọi khi bot nhận /reload-sessions hoặc file đổi.

    Trả về dict mới; đồng thời ghi đè SESSIONS ở module scope để mọi chỗ import
    `from agent.config import SESSIONS` đều thấy data mới.
    """
    global SESSIONS
    SESSIONS = _load_sessions()
    return SESSIONS


def list_choices() -> list[tuple[str, str]]:
    """Trả về [(sid, ten)] cho slash command choices — luôn đọc SESSIONS hiện tại."""
    return [(sid, s.get("ten", sid)[:100]) for sid, s in SESSIONS.items()]


def sessions_signature() -> tuple:
    """Hash chữ ký của SESSIONS (id + transcript) — dùng để phát hiện file đổi."""
    return tuple(sorted((sid, s.get("transcript", "")) for sid, s in SESSIONS.items()))

# ⚠️ Số trang của bản hackathon KHÁC deck gốc mà chatlog trỏ tới.
# Đo được: chỉ 3/673 case chatlog khớp trang (0,4%), độ lệch không phải hằng số
# → KHÔNG join chatlog↔slide theo số trang. Mọi citation [slide tr.N] phải ghi
# rõ là trang của BẢN HACKATHON. Khớp thắc mắc↔nội dung vẫn theo NỘI DUNG.
SLIDE_PAGE_KHAC_DECK_GOC = True

# Khái niệm được hỏi nhiều nhưng KHÔNG có trong transcript nào (mining B14) —
# agent phải chỉ đúng chỗ nó thuộc về thay vì bịa.
NGOAI_NGUON = {
    "react": "buổi Day 3 (deck day03-tu-chatbot-den-agentic-agent-react.pdf)",
    "function calling": "buổi Day 3/Day 4 (deck day04-prompt-engineering-tool-calling.pdf)",
    "mcp": "buổi Day 3/Day 4",
}
