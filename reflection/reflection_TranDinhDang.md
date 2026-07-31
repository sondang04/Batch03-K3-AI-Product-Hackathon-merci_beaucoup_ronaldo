# Reflection cá nhân — Trần Đình Đăng

Nhóm **merci_beaucoup_ronaldo** · Hướng C (làn mở, dùng data pack VLearn, giao diện Discord)
Sản phẩm: `/recap` — agent dựng lại một buổi lecture thành các block có trích dẫn + cụm thắc mắc của bạn học.

---

## 1. Vai trò và phần tôi làm

**Vai trò: Prompt + golden set** — theo bảng phân công [spec.md §8](spec.md#L385): *3 AI call · `eval/golden-set.md` 28 case · chấm lượt 1-3*. Tôi chịu trách nhiệm xây dựng bộ golden set, viết script đánh giá tự động, và điền kết quả chấm cho 3 lượt đầu tiên.

| Việc | Artifact trỏ về được |
|---|---|
| Xây dựng golden set 28 case chia 6 lớp: ① Nguồn sự thật, ② Mơ hồ/thiếu thông tin, ③ Ngoài phạm vi/thẩm quyền, ④ Đặc thù domain, ⑤ Thường, ⑥ Hiếm | [eval/golden-set.md](eval/golden-set.md) |
| Viết `lam_bang_cham.py` — script sinh bảng chấm tự động từ JSON output của golden run | `eval/lam_bang_cham.py` |
| Chấm lượt 1 (22/28), lượt 2 (24/28), lượt 3 (26/28) — điền bảng và ghi failure | [eval/runs/luot-1.md](eval/runs/luot-1.md), [luot-2.md](eval/runs/luot-2.md), [luot-3.md](eval/runs/luot-3.md) |
| Ghi note phát hiện hai lỗi tool qua demo live: `summarize_block` gán sai block, `search_transcript` khớp substring quá cứng | [codebase/logs/notes/2026-07-30-summarize-block-doan-sai-index.md](codebase/logs/notes/2026-07-30-summarize-block-doan-sai-index.md), [2026-07-30-s2-search-substring-qua-cung.md](codebase/logs/notes/2026-07-30-s2-search-substring-qua-cung.md) |

Tôi **không** viết `bot.py`, không viết `system prompt`, không viết `run_golden.py` — đó là phần của Dũng, Sơn, Cường. Phần tôi chịu trách nhiệm giải thích là ba mục dưới đây.

---

## 2. Ba quyết định tôi phải giải thích được (vibe-coding rule)

### (a) Vì sao golden set có 6 lớp, không phải 1 lớp gộp

28 case nghe nhiều. Tôi bắt đầu với một bảng phẳng 28 case ngẫu nhiên, nhưng phát hiện ra rằng **cùng một thất bại có nhiều gốc rễ khác nhau**, và việc gộp chung khiến không phân biệt được:

- Case 12 (hỏi danh tính U0270) và case 11 (injection) đều fail C4, nhưng **case 12 là lỗi riêng tư cố hữu** — model lọt thông tin cá nhân; **case 11 là lỗi safety** — model tuân theo instruction injection. Nếu gộp, ta chỉ biết "C4 fail", không biết sửa cái nào trước.
- Case 02 (bản ghi mất tiếng) và case 06 (token nằm ở nhiều block) đều liên quan "thiếu thông tin", nhưng **case 02 là giới hạn của nguồn** (transcript hỏng), còn **case 06 là giới hạn của gán** (khái niệm mơ hồ). Sửa prompt cho case 02 không giúp case 06.

Sáu lớp phản ánh **sáu gốc rễ failure khác nhau**, và bảng chấm theo lớp giúp nhóm thấy lộ trình sửa: sửa lớp ③ (an toàn) trước lớp ② (mơ hồ), vì lớp ③ sửa bằng luật rõ ràng, còn lớp ② cần thêm data hoặc thay đổi tool.

### (b) Vì sao máy chấm và người chấm không gộp vào một con số

Bảng chấm mỗi lượt có ba loại ô: `✅`/`❌` (máy chấm được), `✅⏳`/`⏳` (còn phần người đọc mới kết luận), và `—` (chiều không áp dụng). Tôi cố ý **không gộp phần người chấm vào cột Pass?** — không phải vì người chấm không đáng tin, mà vì **không tự cho điểm khống được**.

Lý do thấy rõ ở **lượt 1**: máy ghi 22/28 pass, nhưng cột ghi chú 20/28 case còn `⏳` — nghĩa là 20 case cần người đọc nội dung thật để xác nhận. Nếu tôi cộng luôn phần `⏳` vào mà không đọc, tôi sẽ tự cho mình điểm. Mà đây là golden set — nếu người chấm tự cho mình điểm thì không còn là chuẩn.

Hệ quả: mỗi lượt tôi chấm xong bảng, còn một bảng `⏳` dài 20 dòng chưa đọc. Cường (chấm lượt 4) và tôi cần ngồi đọc cùng nhau để so sánh — và spec ghi rõ đó là việc trước CP5. Tôi đã không đẩy nó thành việc có deadline sớm, nên nó còn đó đến cuối.

### (c) Vì sao check "mã đoạn tồn tại thật" là một phép đo cần hai lớp

Lượt 1 và 2 dùng một regex duy nhất: `có mã đoạn` → `mã đoạn tồn tại thật`. Regex này trả **fail** cho cả hai trường hợp rất khác nhau:

- **Model bịa mã** (điều kiện cứng của quality bar): ghi `T04-999` — mã không tồn tại.
- **Model không ghi mã** (lỗi format C1 thường): ghi toàn văn, không mã nào.

Hai trường hợp này đánh cùng một ô `❌`, nhưng ý nghĩa hoàn toàn khác. Lượt 3 case 06 là ví dụ điển hình: model viết `**T04-006**` (không có ngoặc vuông), mã **thật và đúng**, nhưng không đúng format nên regex báo fail → bảng ghi "bịa 1/28" → kết luận CHƯA ĐẠT bar. Sai ở thước đo, không phải ở sản phẩm.

Từ lượt 4, tôi đề xuất tách thành hai check: `có mã đoạn` (C1) và `mã đoạn không bịa` (điều kiện cứng, quét mọi format). Lượt 4 ra 28/28 với 0 bịa — phần bịa thật sự giảm, nhưng phần "format đúng" cũng được phân biệt rõ hơn. Bài học: **một metric phải đo một thứ, không phải hai thứ trộn lại** — nếu không thì khi kết quả xấu, ta không biết sửa prompt, sửa tool, hay sửa cách đo.

---

## 3. AI hỗ trợ thế nào

**Chỗ AI làm tốt.** Xây dựng golden set: khi đã có khung 6 lớp, AI giúp tôi viết mô tả từng case ngắn gọn và chính xác hơn (đảm bảo đủ thông tin để người chấm tái hiện input). Với `lam_bang_cham.py`, AI viết logic regex nhanh hơn tôi debug tay nhiều lần — đặc biệt phần tách format mã đoạn `[T04-NNN]` ở nhiều dạng (ngoặc, đậm, không đậm).

**Chỗ tôi không giao cho AI.** Ba thứ: **chọn case nào vào lớp nào**, **đặt kỳ vọng pass cho từng chiều**, và **quyết định máy chấm vs người chấm cho chiều nào**. Không phải vì AI viết dở, mà vì AI viết ra kỳ vọng nào cũng nghe hợp lý — nó không biết con số 78,4% câu bị 👎 là câu không cite trong B6, nên không hiểu vì sao case C2 (gán thắc mắc) cần kỳ vọng cao hơn case C1 (trích dẫn). Con số đến từ data, không đến từ suy luận.

**Chỗ AI làm tôi suýt sai.** Khi tôi nhờ soạn script so sánh output với golden, AI viết logic so sánh rất gọn — nhưng nó **không phân biệt** giữa "model không ghi mã" và "model ghi mã giả" vì cả hai đều "không khớp". Tôi phát hiện ra khi đọc lại kết quả lượt 3 case 06. Nếu không tự mình đối chiếu với transcript thật, tôi đã tưởng sản phẩm bịa thật.

---

## 4. Bài học từ hai case fail mà tôi phát hiện qua demo

### Case A: `summarize_block` tóm tắt đúng nội dung, sai block

**Case:** Trong quá trình chạy demo live thực tế, tôi phát hiện model gọi `summarize_block(block_idx=3)` và `(block_idx=5)` để trả lời câu hỏi về "Attention, multi-head và bài học quản lý context", nhưng nhận về nội dung *Turing test / hai mùa đông* và *AlphaGo / Transformer*, rồi **in ra dưới nhãn "Block Attention, multi-head"**. Nội dung đúng, mã đoạn thật, chỉ có điều **sai block**.

Hai điều tôi rút ra:

**(1) Spec lường đúng rủi ro nhưng sản phẩm vẫn hỏng.** Spec đã có kịch bản ④ #15: *"gán sai block → học viên học lệch, và không tự phát hiện được"*. Tool `summarize_block` nhận `block_idx` (số) nhưng **không trả về block_idx** — chỉ trả một chuỗi tóm tắt. Model đoán số, nhận về văn bản trông hợp lý, và không có tín hiệu nào để phát hiện đã chọn sai. Đây là lỗi **contract của tool**, không phải lỗi model.

**(2) Test suite cũ mock sẵn đáp án.** Bộ test cũ dùng `block_idx: 8` cố định — tức là nó đã cho sẵn model đáp án của bước dễ sai nhất. Test luôn xanh, sản phẩm vẫn hỏng. Cách sửa: thêm case regression S3 với `live_forbid` là `turing test|alphago` — nếu sau này model lại dán nhãn Attention lên nội dung khác thì test đỏ.

### Case B: `search_transcript` từ chối oan vì khớp substring quá cứng

**Case:** Khi chạy demo S2 ("Giảng viên nói gì về hai mùa đông của AI?"), model gọi `search_transcript` với query `"hai mùa đông"` — nhận về 0 kết quả — rồi **từ chối thật thà** rằng buổi học không có nội dung này. Thực tế, transcript viết *"trải qua **hai lần** mùa đông"*, chữ "lần" chen vào giữa nên substring `"hai mùa đông"` không khớp.

**Một điều tôi rút ra:** đây là lỗi của **tool, không phải model**. Trace cho thấy model làm đúng quy trình: search → 0 kết quả → từ chối. Hành vi đúng theo spec. Nhưng hành vi đúng lại sai ở tầng người dùng — học viên hỏi đúng nội dung buổi học mà bị từ chối.

**Hai bài học chung cho cả hai case:**

1. **Agent chỉ tốt bằng contract của tool bên dưới nó.** Cả hai lỗi đều không phải do model suy nghĩ sai — mà do tool không trả đủ thông tin để model tự kiểm tra, hoặc tool tìm kiếm quá hẹp. Sửa prompt không giải quyết được; phải sửa tool.

2. **Demo thật bắt được lỗi mà test suite bỏ sót.** Cả hai case đều không nằm trong golden set (vì golden set chỉ chấm output, không chấm trace), và đều lộ qua demo live. Test suite giỏi kiểm output, nhưng cần demo để kiểm contract.

---

## 5. Điều tôi biết là còn dở

Ghi thẳng, không giấu:

- **Phần người chấm vẫn chưa xong.** Bảng `⏳` dài 20/28 case chưa đọc — tôi ghi rõ "cần đọc gì" nhưng chưa đọc. Spec ghi đó là việc trước CP5; cuối cùng vẫn chưa làm. Đáng ra tôi phải chốt một buổi ngồi đọc cùng Cường, hoặc giao cho người thứ ba độc lập, thay vì để nó trôi nổi trong bảng.
- **100% ở lượt 4 không phải độ tin cậy thật.** Case 06 và case 15 pass ở lượt 4 mà **sản phẩm không đổi giữa lượt 3 và 4** — đó là model biến động, không phải sửa thật. Lượt 4 do Cường chấm; tôi đã ghi rõ điều này vào [luot-4.md](eval/runs/luot-4.md#L44) thay vì để con số 100% đứng một mình, nhưng cách tốt hơn là mỗi case cần chạy ≥3 lần lấy tỉ lệ.
- **`peer_questions` vẫn còn failure chưa sửa**: nó khớp substring trên **mọi** câu hỏi nên gom cả câu logistics vào cụm "lớp vướng gì", và có lượt in "5 người" rồi liệt kê 6 mã M. Ghi ở [note lượt live 2-3](codebase/logs/notes/2026-07-30-summarize-block-doan-sai-index.md#L41), chưa xử lý.
- **Tách check "bịa mã" khỏi "thiếu mã" chỉ là đề xuất, chưa có trong script.** Tôi ghi ở [luot-4.md](eval/runs/luot-4.md#L60-L65) là nên tách, nhưng `lam_bang_cham.py` vẫn chưa cập nhật. Nếu chạy lại lượt 1-3 với logic mới, con số "bịa" sẽ thay đổi.

**Một câu mang đi:** thứ tôi tưởng mình làm — *viết script và chấm bài* — hoá ra là phần dễ. Phần khó là làm cho kết quả chấm phản ánh đúng **gốc rễ** của failure (prompt, tool, hay đo lường), chứ không phải chỉ một con số pass/fail. Chỗ nào metric đo hai thứ trộn lại thì khi kết quả xấu, ta không biết sửa ở đâu.
