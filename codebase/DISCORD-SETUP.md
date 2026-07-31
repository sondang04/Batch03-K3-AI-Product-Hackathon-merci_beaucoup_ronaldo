# Chạy bot Discord — 5 bước

Lõi agent đã xong và test rồi; phần này chỉ là nối vào Discord.

## 0 · Môi trường (đã dựng)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # openai · python-dotenv · pypdf · discord.py
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

```

Kiểm nhanh: `.venv/bin/python -c "import discord; print(discord.__version__)"` → `2.7.1`

## 1 · Tạo application + bot

[discord.com/developers/applications](https://discord.com/developers/applications) → **New Application**
→ tab **Bot** → **Reset Token** → copy token (chỉ hiện **một lần**).

Cùng tab **Bot**, bật **MESSAGE CONTENT INTENT** — bot cần nó để đọc tin nhắn khi
bị nhắc tên (`@bot multi-head là gì?`). Không bật thì `/recap` và `/hoi` vẫn chạy,
nhưng nhắc tên sẽ không phản hồi.

## 2 · Dán token vào `.env`

```
DISCORD_TOKEN=<token vừa copy>
```

`.env` đã bị `.gitignore` chặn — token không vào git. **Đừng** paste token vào
Discord chat hay commit message; ai có token là điều khiển được bot.

## 3 · Mời bot vào server

Tab **OAuth2 → URL Generator**:

- **Scopes**: `bot`, `applications.commands`
- **Bot Permissions**: `Send Messages`, `Create Public Threads`,
  `Send Messages in Threads`, `Read Message History`

Mở URL sinh ra → chọn server của nhóm. Không cần quyền admin.

## 4 · Chạy

```bash
.venv/bin/python codebase/bot.py
```

Mong đợi:

```
✓ đã sync 2 slash command
✓ online: RecapBot#1234 · provider=openai model=gpt-4o-mini
```

Slash command mới sync có thể mất tới ~1 giờ để hiện toàn cục. Muốn thấy ngay khi
dev: sửa `setup_hook` thành `await self.tree.sync(guild=discord.Object(id=<GUILD_ID>))`.

## Dùng

| Lệnh | Ra gì |
|---|---|
| `/recap buoi:Day 1` | **1 message duy nhất**: header (số block · độ phủ · ~phút đọc · mục đã loại) + **mục lục Select chọn được**. Mỗi option hiện badge độ phủ và *số bạn từng vướng*; 💬 = block có thắc mắc lớp. Kèm nút `❓ Thắc mắc chưa gán được` |
| → chọn một block | Nội dung block trả **riêng cho người bấm** (ephemeral): 4-6 ý + mã đoạn + `🔑 Keyword` + `💬 Bạn học từng vướng gì ở đây`, kèm 2 nút: `📖 Xem nguyên văn` (in đoạn gốc để đối chiếu) và `⚠️ Sai chỗ nào?` → chọn *sai block / thiếu ý / trích dẫn sai đoạn* → ghi vào `validation/feedback-log.md` |
| `/hoi cau_hoi:hai mùa đông AI là gì?` | Trả lời có căn cứ, kèm `[T04-022]`; ngoài nguồn thì từ chối + chỉ chỗ hỏi |
| `@bot multi-head là gì?` | Như `/hoi` |

**Lần `/recap` đầu của mỗi buổi mất ~50 giây** (12-13 lời gọi AI). Bot `defer` nên
Discord không timeout. Kết quả cache xuống `codebase/data/recap-cache/` → lần sau
tức thì. Muốn dựng sẵn trước khi demo:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'codebase')
from agent.llm import make_client; from agent.recap import build_recap
for s in ('day01','day02-sang'): build_recap(s, make_client())"
```

## Hỏng ở đâu, xem đâu

| Hiện tượng | Nguyên nhân thường gặp |
|---|---|
| `Thiếu DISCORD_TOKEN` | chưa dán token vào `.env`, hoặc chạy bằng `python3` thay vì `.venv/bin/python` |
| `LoginFailure: Improper token` | token bị cắt/lẫn dấu cách, hoặc đã Reset lần nữa (token cũ chết) |
| Slash command không hiện | chưa mời với scope `applications.commands`, hoặc đang chờ sync toàn cục |
| Nhắc tên không phản hồi | chưa bật **MESSAGE CONTENT INTENT** |
| Mục lục bấm không phản hồi sau khi restart bot | mục lục là **persistent view**, chỉ cần recap còn cache trên đĩa. Nếu đã xoá `codebase/data/recap-cache/` thì chạy `/recap` lại |
| Nhiều người bấm cùng lúc | mỗi người nhận message **ephemeral** riêng — không ngập channel, không cần lo |
| Trả lời sai/thiếu mã đoạn | mở trace tương ứng trong `codebase/logs/traces/*-discord-*.jsonl` — xem model gọi tool gì, tool trả gì |

## Chạy nền khi demo

```bash
nohup .venv/bin/python codebase/bot.py > codebase/logs/bot.log 2>&1 &
tail -f codebase/logs/bot.log
```

Web app (`codebase/app.py`) và bot dùng **cùng một lõi** — bật cả hai được, nhưng
mỗi tiến trình có cache riêng trong RAM; cache đĩa thì chung.
