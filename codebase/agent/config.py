"""Cấu hình chung cho agent `/recap` — đường dẫn, model, giới hạn."""

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
SLIDES_DIR = REPO / "codebase" / "data" / "slides"
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
SESSIONS = {
    "day01": {
        "ten": "Day 1 — AI & LLM Foundation (giảng viên Blue)",
        "transcript": "transcript-04-clean.md",
        "prefix": "T04",
        "deck": "day01_302",          # 82/83 slide đã tách, KHÔNG có text layer
    },
    "day02-sang": {
        "ten": "Day 2 sáng — Xác định bài toán kinh doanh cho AI",
        "transcript": "transcript-01-clean.md",
        "prefix": "T01",
        "deck": None,
    },
}

# Khái niệm được hỏi nhiều nhưng KHÔNG có trong transcript nào (mining B14) —
# agent phải chỉ đúng chỗ nó thuộc về thay vì bịa.
NGOAI_NGUON = {
    "react": "buổi Day 3 (deck day03-tu-chatbot-den-agentic-agent-react.pdf)",
    "function calling": "buổi Day 3/Day 4 (deck day04-prompt-engineering-tool-calling.pdf)",
    "mcp": "buổi Day 3/Day 4",
}
