# S2 fail ở lượt live đầu — search substring quá cứng

- **Lượt đo**: `eval-runs/live-20260730-070824-openai.json` — pass **8/9**
- **Case fail**: `S2-hoi-dap-can-cu` — "Giảng viên nói gì về hai mùa đông của AI vậy?"
  → trả lời **không có mã đoạn** `[T04-NNN]`
- **Trace**: `traces/20260730-070835-live-S2-hoi-dap-can-cu-e50567.jsonl`

## Chẩn đoán — lỗi của TOOL, không phải của model

Trace cho thấy model làm **đúng**:

```
tool_call  search_sources {"session_id":"day01","query":"hai mùa đông"}
result     {"transcript":[], "slide":[], "ghi_chu":"KHÔNG có trong ... không được tự giải thích"}
→ model: "Khái niệm không nằm trong bản ghi buổi học này. Bạn có thể hỏi VLearn Tutor hoặc TA…"
```

Model search, nhận 0 kết quả, rồi **từ chối thật thà thay vì bịa** — đúng hành vi
mình muốn. Vấn đề là `search_transcript` khớp **substring liền mạch**: model gõ
`"hai mùa đông"`, transcript viết *"trải qua **hai lần** mùa đông"* → chữ "lần"
chen vào giữa nên không khớp.

Đây là kiểu lỗi nguy hiểm: tool yếu khiến agent **từ chối oan** một câu hỏi mà
buổi học thực sự có trả lời. Học viên sẽ tưởng nội dung không có trong bài.

## Sửa

`sources.py` — search chuyển từ substring sang **token AND**:

- `_tokens()` tách truy vấn, bỏ dấu, loại từ chức năng (`la/cua/va/mot/…`)
- `_match()` trả `(vị trí, độ phân tán)` khi **mọi** token đều xuất hiện, không
  cần liền mạch → `"hai mùa đông"` khớp `"hai lần mùa đông"`
- Xếp hạng theo **độ phân tán** (token gần nhau ⇒ liên quan hơn) thay vì thứ tự
  xuất hiện trong file

Áp cho cả `search_transcript` và `search_slides`.

## Kiểm sau khi sửa

| Truy vấn | Trước | Sau |
|---|---|---|
| `hai mùa đông` | **0** | 6 đoạn — top: `T04-029, T04-022, T04-023` |
| `attention multi-head` | 0 | `T04-056` |
| `ReAct` | 0 | **0** ✅ (đường từ chối không vỡ) |
| `token economy` | 0 | **0** ✅ (không khớp bừa) |

Hai dòng cuối quan trọng: nới search **không được** làm mất khả năng nói "không có".
`ReAct` vẫn 0 ⇒ case O3 vẫn chạy đúng.

## Sau đó

Chạy lại **trọn bộ** (offline + live), không chỉ S2 — xem `eval-runs/` lượt kế tiếp.
