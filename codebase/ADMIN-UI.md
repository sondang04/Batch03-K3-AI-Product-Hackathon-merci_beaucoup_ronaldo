# UI Admin — Upload & Quản lý Transcript

UI web nhỏ (FastAPI + Jinja2 + Tailwind CDN) để upload file transcript mới và
trigger build recap/quiz — không cần SSH vào máy, không cần Discord.

## Cài đặt (1 lần)

```bash
pip install fastapi "uvicorn[standard]" jinja2 python-multipart
```

## Chạy

UI chạy **port riêng**, không xung đột với bot Discord.

```bash
# Terminal 1 (đang chạy) — Discord bot
python bot.py

# Terminal 2 (mới) — UI admin
cd codebase
python -m uvicorn ui_admin:app --host 127.0.0.1 --port 8000
```

Mở browser: **http://localhost:8000**

## Tính năng

- **Trang chủ `/`**: liệt kê buổi học, trạng thái recap/quiz, có nút **+ Tạo buổi mới**
- **Trang buổi `/session/{id}`**: build recap, build quiz, xem preview, upload file transcript, sửa metadata, xóa buổi
- **Tạo buổi `/sessions/new`**: form khai báo buổi mới (id, tên, prefix Txx, transcript gắn vào, deck PDF)
- **Upload**: nhận `.md` / `.txt` / `.srt` (tối đa 5 MB), **tự validate format** (phải có `## Tiêu đề block` + mã đoạn `**[Txx-NNN]**` đúng prefix buổi), lưu vào `data/vlearn-pack/transcript/` và gắn vào `config.SESSIONS[session_id]["transcript"]`. File sai → rollback. Tự động xóa cache recap/quiz cũ
- **Preview**: xem recap/quiz dùng lại hàm `render()` có sẵn của bot → giống hệt Discord
- **Registry buổi** lưu ở `data/vlearn-pack/sessions.json` — UI CRUD trực tiếp. Fallback về hard-coded trong `agent/config.py` nếu JSON chưa có

## Luồng mentor tạo buổi mới

1. Upload file transcript ở UI (bất kỳ buổi nào) — file được lưu vào `data/vlearn-pack/transcript/`
2. Bấm **+ Tạo buổi mới** ở trang chủ, điền id (vd `day03`), tên buổi, prefix (vd `T03`), chọn transcript đã upload
3. Bot Discord tự động thấy buổi mới trong ~5s (không cần restart). Nếu UI vẫn báo "Bot chưa thấy" → bấm nút **🔄 Reload bot ngay** trên banner vàng, hoặc gõ `/reload-sessions` trong Discord (admin only)
4. Build recap/quiz ngay trên UI, học viên dùng `/recap` / `/quiz` trên Discord như cũ. Slash command dùng **autocomplete** nên buổi mới tự xuất hiện khi user gõ

## Format file transcript

Để agent đọc được, file phải có:

- Tiêu đề block dạng `## ` ở đầu section
- Mã đoạn dạng `**[Txx-NNN]**` (xx = prefix buổi, ví dụ `T04`, `T01`)
- Đoạn văn ngay sau mỗi mã, cách nhau 1 dòng trống

Mẫu (xem file sẵn `data/vlearn-pack/transcript/transcript-04-clean.md`):

```markdown
# Tiêu đề buổi

## Tên block 1

**[T04-001]** Nội dung đoạn 1...

**[T04-002]** Nội dung đoạn 2...

## Tên block 2

**[T04-003]** Nội dung đoạn 3...
```

## Lưu ý

- Upload file mới sẽ **xóa cache** recap/quiz cũ của buổi đó. Lần sau gõ `/recap` trên
  Discord hoặc bấm "Build" trên UI sẽ sinh lại từ dữ liệu mới.
- Bot Discord đang chạy sẽ **tự nhận file mới** ở lần gọi `/recap` tiếp theo
  (nhờ `sources.load_transcript.cache_clear()` được gọi khi upload).
- **Tạo buổi mới**: thay đổi `config.SESSIONS` qua UI sẽ được ghi vào `data/vlearn-pack/sessions.json`.
  **Bot Discord sẽ tự nhận buổi mới trong vòng ~5 giây** nhờ:
  - Bot watch `sessions.json` mỗi 5s (qua `Bot.watch_sessions_json`) → reload `SESSIONS` + `tree.sync()`.
  - UI admin **ping** `http://127.0.0.1:8765/sessions` (bot HTTP) để biết buổi nào bot đã thấy.
  - Nếu lệch, UI hiện banner vàng "Bot Discord chưa thấy buổi mới" với nút **🔄 Reload bot ngay** (POST `/api/reload-bot` → bot reload ngay lập tức).
  - Hoặc trong Discord gõ `/reload-sessions` (chỉ admin server).
  - Upload/sửa transcript cho buổi đã có thì bot nhận ngay (qua `sources.load_transcript.cache_clear()`).
- Khi upload file transcript cho buổi chưa tồn tại, hệ thống sẽ **auto-register** buổi tạm với
  `prefix=""` — mentor cần vào trang buổi đó sửa prefix sau. Validate transcript chỉ chạy khi buổi
  đã có prefix.

## Kiến trúc

- `codebase/ui_admin.py` — FastAPI app, ~450 dòng, import trực tiếp `agent/`
- `codebase/agent/config.py` — registry buổi học (ưu tiên JSON, fallback hard-coded)
- `codebase/data/vlearn-pack/sessions.json` — registry buổi (UI CRUD tại đây)
- `codebase/templates/base.html` — layout (Tailwind CDN)
- `codebase/templates/index.html` — trang chủ
- `codebase/templates/session.html` — chi tiết buổi + form upload + sửa metadata
- `codebase/templates/session_new.html` — form tạo buổi mới
- `codebase/templates/preview.html` — preview recap/quiz (render Discord-style)

Không có build step, không có npm, không có DB — chỉ thao tác file + cache có sẵn.
