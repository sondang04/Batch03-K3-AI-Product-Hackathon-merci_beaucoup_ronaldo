"""UI quản lý admin — upload file transcript, trigger build recap/quiz, preview.

Chạy:    uvicorn ui_admin:app --reload --port 8000
Mở:      http://localhost:8000

Stack: FastAPI + Jinja2 + Tailwind (CDN). Không có build step.
Bot Discord chạy process riêng (python bot.py) — UI này chỉ thao tác
với file transcript + cache, KHÔNG gọi tới Discord.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from agent import config
from agent.llm import make_client
from agent.recap import build_recap, render as render_recap
from agent.quiz import build_quiz, render as render_quiz
from agent import sources

import httpx


HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"

# Endpoint của bot Discord (cùng máy) — bot đã expose /health ở đâu thì dùng ở đó.
# Mặc định: bot có 1 mini-HTTP riêng (xem bot.py) chạy ở host/port này.
BOT_HTTP_URL = os.environ.get("BOT_HTTP_URL", "http://127.0.0.1:8765").rstrip("/")

app = FastAPI(title="VLearn Bot Admin", version="2.0")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# Bug Jinja2 3.1.6 + starlette 1.3.1: starlette.templating.Jinja2Templates cache
# theo (name, parent) tuple mà jinja2 3.1.6 không chấp nhận tuple làm dict key.
# Tự dựng Environment để bypass, render thủ công qua HTMLResponse.
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html"]),
    auto_reload=True,
)
jinja_env.filters["human_size"] = lambda n: _human_size(int(n))


def render_html(request: Request, name: str, context: dict | None = None,
                 status_code: int = 200) -> HTMLResponse:
    """Render template thủ công — thay cho Jinja2Templates để tránh bug cache."""
    ctx = dict(context or {})
    ctx["request"] = request
    return HTMLResponse(jinja_env.get_template(name).render(**ctx),
                        status_code=status_code)


# ── Helpers ─────────────────────────────────────────────────────────────────

ACCEPT_EXTS = {".md", ".txt", ".srt"}
MAX_UPLOAD_MB = 5
SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")   # day01, day03-chieu, ...
PREFIX_RE = re.compile(r"^T\d{2}$")                          # T01, T04, T12


def _allowed_session(session_id: str) -> bool:
    return session_id in config.SESSIONS


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _save_sessions() -> None:
    """Ghi SESSIONS hiện tại ra JSON (mentor CRUD từ UI)."""
    import json
    config.SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SESSIONS_FILE.write_text(
        json.dumps(config.SESSIONS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _bot_status() -> dict:
    """Ping bot HTTP endpoint để biết:
    - bot có đang chạy không
    - bot đã thấy buổi mới trong SESSIONS chưa (so với UI)
    Trả về dict: {reachable, bot_sessions, ui_sessions, mismatch, missing_in_bot}.
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{BOT_HTTP_URL}/sessions")
    except Exception:
        return {"reachable": False}

    try:
        data = r.json()
    except Exception:
        return {"reachable": True, "parse_error": True}

    bot_ids = set(data.get("sessions", []))
    ui_ids = set(config.SESSIONS.keys())
    missing = sorted(ui_ids - bot_ids)
    return {
        "reachable": True,
        "bot_sessions": sorted(bot_ids),
        "ui_sessions": sorted(ui_ids),
        "missing_in_bot": missing,
        "mismatch": bool(missing),
    }


def _validate_transcript_text(text: str, prefix: str) -> tuple[bool, str]:
    """Kiểm tra file transcript có đúng format mà agent đọc được không.
    Trả (ok, message). Mentor upload nhầm file Word/PDF sẽ bị chặn ngay, đỡ phải
    build recap rồi mới biết lỗi."""
    if not text.strip():
        return False, "File rỗng."
    if "##" not in text:
        return False, "Không thấy tiêu đề block dạng `## `. Cần có dòng `## Tên block`."
    code_re = re.compile(rf"\*\*\[{re.escape(prefix)}-\d{{3}}\]\*\*")
    n_codes = len(code_re.findall(text))
    if n_codes == 0:
        return False, (
            f"Không thấy mã đoạn `**[{prefix}-NNN]**`. Mỗi block phải có ít nhất 1 mã đoạn. "
            "Kiểm tra prefix (vd T01 vs T04)."
        )
    return True, f"Tốt — {n_codes} mã đoạn khớp pattern `[{prefix}-NNN]`."


def _list_transcripts() -> list[dict]:
    """Liệt kê file trong TRANSCRIPT_DIR + match với SESSIONS."""
    out = []
    seen = set()
    if config.TRANSCRIPT_DIR.exists():
        for p in sorted(config.TRANSCRIPT_DIR.glob("*.md")):
            seen.add(p.name)
            out.append({
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "linked": any(s.get("transcript") == p.name for s in config.SESSIONS.values()),
            })
        # Cũng nhặt .txt và .srt
        for ext in ("*.txt", "*.srt"):
            for p in sorted(config.TRANSCRIPT_DIR.glob(ext)):
                if p.name in seen:
                    continue
                seen.add(p.name)
                out.append({
                    "filename": p.name,
                    "size_kb": round(p.stat().st_size / 1024, 1),
                    "linked": any(s.get("transcript") == p.name for s in config.SESSIONS.values()),
                })
    return out


def _session_summary(sid: str) -> dict:
    """Tóm tắt 1 session: tên, file gắn với, có cache recap/quiz không."""
    ses = config.SESSIONS.get(sid, {})
    transcript_path = config.TRANSCRIPT_DIR / ses.get("transcript", "")
    recap_cache = list((config.REPO / "codebase" / "data" / "recap-cache").glob(f"{sid}-*.json"))
    quiz_cache = list((config.REPO / "codebase" / "data" / "quiz-cache").glob(f"quiz-{sid}-*.json"))
    return {
        "id": sid,
        "ten": ses.get("ten", ""),
        "prefix": ses.get("prefix", ""),
        "transcript_file": ses.get("transcript", "(chưa gắn)"),
        "transcript_exists": transcript_path.exists(),
        "transcript_size_kb": round(transcript_path.stat().st_size / 1024, 1) if transcript_path.exists() else 0,
        "deck_pdf": ses.get("deck_pdf", ""),
        "has_recap": bool(recap_cache),
        "has_quiz": bool(quiz_cache),
    }


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def trang_chinh(request: Request):
    sessions = [_session_summary(sid) for sid in config.SESSIONS]
    transcripts = _list_transcripts()
    bot_status = await _bot_status()
    flash = None
    if request.query_params.get("deleted") == "1":
        flash = "Đã xóa buổi khỏi registry."
    elif request.query_params.get("reloaded") == "1":
        flash = "Đã gửi tín hiệu reload tới bot Discord."
    return render_html(request, "index.html", {
        "sessions": sessions,
        "transcripts": transcripts,
        "max_upload_mb": MAX_UPLOAD_MB,
        "flash": flash,
        "bot_status": bot_status,
    })


@app.post("/api/reload-bot")
async def reload_bot():
    """Gửi POST /reload tới bot HTTP để nó reload SESSIONS + re-sync slash command.

    Nếu bot chưa expose HTTP endpoint, sẽ fail nhẹ — UI vẫn không crash.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(f"{BOT_HTTP_URL}/reload")
        return JSONResponse({"ok": r.status_code == 200, "status": r.status_code})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)


@app.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str):
    if not _allowed_session(session_id):
        raise HTTPException(404, "Session không tồn tại")
    summary = _session_summary(session_id)
    transcripts = _list_transcripts()
    slides_files = sorted(p.name for p in (config.SLIDES_PDF_DIR.glob("*.pdf") if config.SLIDES_PDF_DIR.exists() else []))
    flash = None
    qp = request.query_params
    if qp.get("uploaded") == "1":
        flash = "Upload thành công. Cache recap/quiz cũ đã được xóa."
    elif qp.get("created") == "1":
        flash = "Đã tạo buổi mới trong registry."
    elif qp.get("edited") == "1":
        flash = "Đã lưu thay đổi metadata."
    elif qp.get("err"):
        flash = qp.get("err")
    return render_html(request, "session.html", {
        "s": summary,
        "transcripts": transcripts,
        "slides_files": slides_files,
        "uploaded": qp.get("uploaded") == "1",
        "flash": flash,
        "can_delete": len(config.SESSIONS) > 1,
    })


@app.post("/upload")
async def upload_transcript(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    replace_filename: str = Form(""),
    overwrite: str = Form(""),          # "1" nếu mentor tick 'ghi đè'
):
    """Upload transcript mới → lưu vào TRANSCRIPT_DIR và gắn vào session.

    Cho phép upload kể cả khi session MỚI CHƯA TỒN TẠI (mentor tạo buổi mới
    bằng cách upload file transcript trước, khai báo buổi ở bước sau). Đây là
    luồng mentor thật sự: soạn bài → upload → khai báo buổi.
    """
    if not SESSION_ID_RE.match(session_id):
        raise HTTPException(
            400,
            "session_id chỉ gồm chữ thường/số/dấu gạch ngang, vd: day03, day04-chieu",
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ACCEPT_EXTS:
        raise HTTPException(
            400,
            f"Định dạng {ext} không hỗ trợ. Chỉ nhận: {', '.join(ACCEPT_EXTS)}",
        )

    config.TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    # Tên file: ưu tiên replace_filename (giữ tên trong SESSIONS để bot nhận ra),
    # fallback về tên gốc của file upload.
    target_name = replace_filename.strip() or file.filename or ""
    if not target_name:
        raise HTTPException(400, "Tên file rỗng")

    target_path = config.TRANSCRIPT_DIR / target_name
    is_new_session = session_id not in config.SESSIONS

    if target_path.exists() and not overwrite:
        raise HTTPException(
            409,
            f"File {target_name} đã tồn tại. Tick 'Ghi đè' nếu muốn thay.",
        )

    # Ghi file
    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File quá lớn (> {MAX_UPLOAD_MB} MB)")

    target_path.write_bytes(content)

    # Validate nội dung sau khi ghi
    try:
        text = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        target_path.unlink(missing_ok=True)
        raise HTTPException(400, "File không phải UTF-8 (có thể là .docx/.pdf đổi tên).")

    prefix = config.SESSIONS.get(session_id, {}).get("prefix", "")
    if prefix:
        ok, msg = _validate_transcript_text(text, prefix)
        if not ok:
            target_path.unlink(missing_ok=True)
            raise HTTPException(400, f"Transcript KHÔNG đúng format → đã rollback.\n{msg}")

    # Auto-register session nếu chưa có (mentor upload cho buổi hoàn toàn mới)
    if is_new_session:
        config.SESSIONS[session_id] = {
            "ten": session_id,
            "transcript": target_name,
            "prefix": "",            # mentor phải sửa sau
            "deck_pdf": "",
            "deck_ten": "",
        }
        _save_sessions()
    else:
        config.SESSIONS[session_id]["transcript"] = target_name
        _save_sessions()

    # Xóa cache recap/quiz cũ vì dữ liệu đã đổi
    for cache_dir, pat in [
        (config.REPO / "codebase" / "data" / "recap-cache", f"{session_id}-*.json"),
        (config.REPO / "codebase" / "data" / "quiz-cache",  f"quiz-{session_id}-*.json"),
    ]:
        if cache_dir.exists():
            for f in cache_dir.glob(pat):
                f.unlink()

    # Invalidate LRU cache của load_transcript để lần đọc sau nhận file mới
    sources.load_transcript.cache_clear()
    sources.load_slides.cache_clear()

    return RedirectResponse(url=f"/session/{session_id}?uploaded=1", status_code=303)


# ── Quản lý buổi (CRUD SESSIONS) ────────────────────────────────────────────

@app.get("/sessions/new", response_class=HTMLResponse)
async def new_session_form(request: Request):
    """Form tạo buổi mới — mentor chọn ID, tên, prefix, deck PDF."""
    return render_html(request, "session_new.html", {
        "existing_ids": list(config.SESSIONS.keys()),
        "slides_files": sorted(p.name for p in (config.SLIDES_PDF_DIR.glob("*.pdf") if config.SLIDES_PDF_DIR.exists() else [])),
        "transcript_files": [t["filename"] for t in _list_transcripts()],
    })


@app.post("/sessions/new")
async def create_session(
    session_id: str = Form(...),
    ten: str = Form(...),
    prefix: str = Form(...),
    transcript: str = Form(...),
    deck_pdf: str = Form(""),
):
    """Tạo buổi mới → validate đầu vào → ghi vào sessions.json."""
    if not SESSION_ID_RE.match(session_id):
        raise HTTPException(400, "session_id chỉ gồm chữ thường/số/dấu gạch ngang (vd: day03, day04-chieu)")
    if session_id in config.SESSIONS:
        raise HTTPException(409, f"session_id '{session_id}' đã tồn tại. Bấm vào buổi đó để sửa.")
    if not PREFIX_RE.match(prefix):
        raise HTTPException(400, "prefix phải dạng Txx (vd T01, T04, T12)")
    if not ten.strip():
        raise HTTPException(400, "Tên buổi không được rỗng")
    tp = config.TRANSCRIPT_DIR / transcript
    if not tp.exists():
        raise HTTPException(400, f"File transcript '{transcript}' không tồn tại trong data/vlearn-pack/transcript/")

    config.SESSIONS[session_id] = {
        "ten": ten.strip(),
        "transcript": transcript,
        "prefix": prefix,
        "deck_pdf": deck_pdf or "",
        "deck_ten": deck_pdf or "",
    }
    _save_sessions()
    return RedirectResponse(url=f"/session/{session_id}?created=1", status_code=303)


@app.post("/sessions/{session_id}/delete")
async def delete_session(session_id: str):
    """Xóa 1 buổi khỏi SESSIONS (chỉ xóa registry, KHÔNG xóa file transcript).

    Sau khi xóa, transcript vẫn nằm trong data/vlearn-pack/transcript/ — nếu
    không buổi nào tham chiếu, nó vẫn hiện ở 'File chưa gắn'.
    """
    if session_id not in config.SESSIONS:
        raise HTTPException(404, "Session không tồn tại")
    if len(config.SESSIONS) <= 1:
        raise HTTPException(400, "Không thể xóa buổi cuối cùng — phải còn ít nhất 1 buổi.")
    del config.SESSIONS[session_id]
    _save_sessions()
    return RedirectResponse(url="/?deleted=1", status_code=303)


@app.post("/session/{session_id}/edit")
async def edit_session(
    session_id: str,
    ten: str = Form(...),
    prefix: str = Form(...),
    transcript: str = Form(...),
    deck_pdf: str = Form(""),
):
    """Sửa metadata buổi — đổi tên, prefix, transcript gắn vào, deck PDF."""
    if session_id not in config.SESSIONS:
        raise HTTPException(404, "Session không tồn tại")
    if not PREFIX_RE.match(prefix):
        raise HTTPException(400, "prefix phải dạng Txx (vd T01, T04, T12)")
    if not ten.strip():
        raise HTTPException(400, "Tên buổi không được rỗng")
    tp = config.TRANSCRIPT_DIR / transcript
    if not tp.exists():
        raise HTTPException(400, f"File transcript '{transcript}' không tồn tại")

    config.SESSIONS[session_id] = {
        "ten": ten.strip(),
        "transcript": transcript,
        "prefix": prefix,
        "deck_pdf": deck_pdf or "",
        "deck_ten": deck_pdf or "",
    }
    _save_sessions()
    return RedirectResponse(url=f"/session/{session_id}?edited=1", status_code=303)


@app.post("/session/{session_id}/build/recap")
async def build_recap_endpoint(session_id: str):
    """Build recap cho 1 session (chạy sync trong thread, không block event loop)."""
    if not _allowed_session(session_id):
        raise HTTPException(400, f"session_id không hợp lệ")
    client = make_client()
    recap = await asyncio.to_thread(build_recap, session_id, client, False)
    sources.load_transcript.cache_clear()
    return RedirectResponse(url=f"/session/{session_id}/preview/recap", status_code=303)


@app.post("/session/{session_id}/build/quiz")
async def build_quiz_endpoint(session_id: str):
    if not _allowed_session(session_id):
        raise HTTPException(400, f"session_id không hợp lệ")
    client = make_client()
    quiz = await asyncio.to_thread(build_quiz, session_id, client, False)
    return RedirectResponse(url=f"/session/{session_id}/preview/quiz", status_code=303)


@app.get("/session/{session_id}/preview/recap", response_class=HTMLResponse)
async def preview_recap(request: Request, session_id: str):
    if not _allowed_session(session_id):
        raise HTTPException(404)
    client = make_client()
    recap = await asyncio.to_thread(build_recap, session_id, client, True)
    messages = render_recap(recap)
    return render_html(request, "preview.html", {
        "title": f"Recap — {recap.buoi}",
        "subtitle": f"{len(recap.blocks)} block · {recap.do_phu} · {recap.n_ai_calls} AI calls · {recap.giay}s",
        "messages": messages,
        "back_url": f"/session/{session_id}",
    })


@app.get("/session/{session_id}/preview/quiz", response_class=HTMLResponse)
async def preview_quiz(request: Request, session_id: str):
    if not _allowed_session(session_id):
        raise HTTPException(404)
    client = make_client()
    quiz = await asyncio.to_thread(build_quiz, session_id, client, True)
    return render_html(request, "preview.html", {
        "title": f"Quiz — {quiz.buoi}",
        "subtitle": f"{quiz.tong_cau} câu trắc nghiệm · {quiz.n_ai_calls} AI calls · {quiz.giay}s",
        "messages": [render_quiz(quiz)],
        "back_url": f"/session/{session_id}",
    })


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "sessions": list(config.SESSIONS.keys())})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ui_admin:app", host="127.0.0.1", port=8000, reload=False)
