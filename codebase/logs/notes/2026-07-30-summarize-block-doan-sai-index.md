# Lượt live 2-3: `summarize_block` tóm tắt SAI block, nhãn vẫn là block học viên hỏi

- **Phát hiện**: chạy demo thật trên Day 1, không phải từ test suite (bộ test cũ
  mock sẵn `block_idx: 8` nên không bao giờ bắt được lỗi này).
- **Câu hỏi**: "Recap block *Attention, multi-head và bài học quản lý context*"
- **Kết quả sai**: model gọi `summarize_block(block_idx=3)` và `(block_idx=5)` →
  nhận về nội dung *Turing test / hai mùa đông* và *AlphaGo / Transformer*, rồi
  **in ra dưới nhãn "Block Attention, multi-head"**. Nội dung đúng và có mã đoạn
  thật, nhưng **sai block** — học viên hỏi Attention lại được đọc lịch sử AI.
- **Không cố định**: lượt sau nó chọn `block_idx=8` (đúng). Sai ngẫu nhiên còn
  khó phát hiện hơn sai đều.

## Nguyên nhân gốc

`summarize_block` trả về **duy nhất chuỗi tóm tắt** — không nói nó đã tóm tắt
block nào. Model đoán một số, nhận về văn bản trông hợp lý, và **không có bất kỳ
tín hiệu nào để tự phát hiện đã chọn sai**. Lỗi thiết kế tool, không phải lỗi model.

Đây là biến thể của kịch bản ④ #15 trong spec ("gán sai block → học viên học lệch,
và **không tự phát hiện được**"). Spec đã lường đúng rủi ro; tool thì chưa chặn.

## Sửa (hai lớp, cùng hướng "đừng để model phải đoán")

1. **`title_query`** — `summarize_block` nhận tên block thay vì số:
   `find_block()` khớp token trên tiêu đề. `'attention multi-head'` → `#8`,
   `'double diamond'` → `#7` (day02), `'xyz'` → `None` (không khớp bừa).
2. **Echo danh tính** — kết quả trả `{block_idx, tieu_de, dai_ma, tom_tat, nhac}`.
   Model **nhìn thấy** tiêu đề nó vừa tóm tắt và có dòng nhắc phải đối chiếu với
   điều học viên hỏi. Không còn "tóm tắt mù".
3. Tool description: "**KHÔNG đoán block_idx**" + phải `list_blocks` trước hoặc
   dùng `title_query`.

## Kiểm sau khi sửa

- Thêm case regression **S3** với `live_forbid` là `turing test|alphago` —
  nghĩa là nếu tương lai nó lại dán nhãn Attention lên nội dung khác, test đỏ.
- Live trọn bộ: **10/10** (`eval-runs/live-20260730-071737-openai.json`).
- Chạy lại chính câu hỏi đã gây lỗi: giờ ra đúng `[T04-053] [T04-054] [T04-056]
  [T04-057]` với ẩn dụ gốc của giảng viên ("nhiều con mắt", "thầy bói xem voi").

## Failure kế tiếp (chưa sửa) — ưu tiên sau

`peer_questions` khớp substring trên **mọi** câu hỏi, không chỉ câu hỏi *học tập*.
Lượt demo trả về cả câu logistics ("tìm tài liệu ở workspace", "tiêu đề buổi học và
danh tính giảng viên") dưới nhãn "lớp vướng gì" — nhiễu, và lệch định nghĩa cụm
thắc mắc trong spec. Cần lọc theo nhãn A/B của `mine_chatlog.py` trước khi gom cụm.
Ngoài ra model in ra "5 người" rồi liệt kê 6 mã M — số người và số câu bị lẫn.
