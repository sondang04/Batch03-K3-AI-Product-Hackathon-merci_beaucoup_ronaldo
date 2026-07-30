# Bộ câu hỏi khảo sát — Đường A

**Mục tiêu:** chứng minh học viên **muốn** job "ôn lại một buổi lecture" được giải — bổ sung cho Đường B (mining) đã chứng minh pain *tồn tại*.

**Chuẩn đạt (đề bài tiêu chí 2 / rubric R1):** ≥20 người **ngoài nhóm** · ≥50% xác nhận · log đầy đủ câu đã hỏi + từng câu trả lời nguyên văn + ai trả lời.

| Vòng | Trạng thái | n | Hình thức | File |
|---|---|---|---|---|
| **1** | ✅ **đã thu** 30/07/2026 10:40-10:55 | **25** | Google Form 6 câu, tự điền, giờ nghỉ | `survey-log.md` · `survey-analysis.txt` |
| **2** | ⬜ chưa thu — trước CP5 | mục tiêu ≥15 | hỏi trực tiếp, 3 câu hồi tưởng | `survey-log-vong2.md` |

---

# VÒNG 1 — đã chạy (n = 25)

## 6 câu đã dùng (nguyên văn trong form)

1. Họ và Tên
2. Mã học viên (5 số cuối)
3. Đánh giá từ 1 đến 5 về độ khó của nội dung trong các buổi lecture
4. Bạn dành bao nhiêu thời gian để đọc nội dung trong slide bài học của lecture buổi chiều?
5. Trong buổi học lecture chiều, thời gian bạn thực sự tập trung nghe giảng chiếm tới bao nhiêu phần trăm? (Bấm số)
6. Nếu có một discord bot có thể giúp bạn tóm tắt bài học thực tế đã nghe trong buổi chiều, có bao gồm phản ánh nội dung bài học cũng như phần Q&A, bạn có muốn sử dụng không?
7. Bạn có comment gì khác không?

## Đánh giá chất lượng bộ câu hỏi vòng 1 — làm trước khi trích số

| Câu | Loại | Dùng được? |
|---|---|---|
| Q3 độ khó | cảm nhận có thang | ✅ |
| Q4 thời gian đọc slide | **hành vi** (đã xảy ra) | ✅ mạnh |
| Q5 % tập trung | **hành vi tự khai** (đã xảy ra) | ✅ **mạnh nhất** |
| Q6 ý định dùng | ❌ **ý kiến về tính năng chưa tồn tại, kèm mô tả sản phẩm ngay trong câu hỏi** | ⚠️ không dùng làm bằng chứng nhu cầu |
| Q7 comment mở | tự do | ⚠️ chỉ 1/25 có nội dung |

**Vì sao Q6 không tính:** guide §1.3 mục 4 — *"tránh hỏi ý kiến kiểu 'bạn có cần tính năng X không?' — hầu như ai cũng trả lời có, dữ liệu thu được không dùng được."* Q6 đúng dạng đó, lại còn mô tả sẵn sản phẩm (kể cả phần Q&A) trong chính câu hỏi. Kết quả 84% "Có" là con số **đã được dự đoán trước**, không phải phát hiện.

**Nhóm dùng Q6 đúng một việc:** **0/25 trả lời "Không"** ⇒ không ai phản đối hướng đi; và **4 người "Chưa chắc"** trở thành danh sách ưu tiên cho vòng validation CP5.

**Bài học mang sang vòng 2:** không mô tả sản phẩm trước khi hỏi. Chỉ mô tả **sau** khi đã ghi xong câu trả lời.

---

# VÒNG 2 — chưa thu, chốt sẵn để không tự nới tay khi đếm

**Vá 3 giới hạn của vòng 1:** ① Q6 hỏi ý kiến · ③ chưa có số phút thật cho việc *ôn lại* (nên chưa đối chiếu được với mining B11 = 85 phút đọc transcript/buổi) · ⑤ chưa ai là willing user.

**Ai đi hỏi:** `[Tên 2]`. **Cách hỏi:** trực tiếp, ~2 phút/người, gõ lại nguyên văn ngay tại chỗ. Ưu tiên hỏi lại đúng 25 người vòng 1 để ghép được hai vòng theo tên.

## Nguyên tắc

**Hỏi về LẦN GẦN NHẤT, không hỏi ý kiến.**

- ❌ Không hỏi: "Bạn có muốn có bản tóm tắt buổi học không?" (đã mắc ở vòng 1)
- ❌ Không mô tả `/recap` trước khi hỏi.
- ✅ Hỏi chuyện đã xảy ra, có mốc thời gian, có con số phút.

## 3 câu (hỏi đúng thứ tự, không thêm gợi ý)

**Q1.** "Lần gần nhất bạn muốn xem lại một buổi lecture đã học — bạn đã làm gì? Mất bao lâu?"
→ Ghi: cách làm (tua bản ghi / đọc slide / hỏi bạn / hỏi Tutor / không làm gì) + **số phút họ tự nói ra**.

**Q2.** "Lần đó bạn có xem hết không? Nếu bỏ dở thì bỏ ở chỗ nào?"
→ Ghi: xem hết / bỏ dở + chỗ bỏ + lý do nguyên văn.

**Q3.** "Bạn có bao giờ hỏi Tutor hoặc TA một câu mà sau đó phát hiện bạn khác đã hỏi y hệt? Kể lần gần nhất."
→ Ghi: có/không + câu chuyện cụ thể.

**Q4 (bắt buộc hỏi, ghi riêng — không tính vào tỷ lệ xác nhận):** "Bọn mình đang dựng một bot recap buổi học trong Discord. Bạn có đồng ý thử 10 phút trước chiều mai không?" → đây là câu **duy nhất** biến người trả lời thành **willing user** cho §8.

## Định nghĩa "xác nhận" — chốt TRƯỚC khi đi hỏi

Một người tính là **xác nhận** khi thoả **≥1** trong 2 điều:

- **(a)** Q2 = đã từng **bỏ dở** việc ôn lại, **hoặc** Q1 = **không làm gì cả** dù muốn ôn — tức chi phí duyệt lại nội dung đủ lớn để chặn họ; **hoặc**
- **(b)** Q1 cho ra **≥30 phút** cho một lần ôn lại một buổi.

Q3 = "có" ghi thành **tỷ lệ thứ hai** (trùng lặp thắc mắc), **không** gộp vào tỷ lệ xác nhận chính.

## Bảng log vòng 2 → `evidence/survey/survey-log-vong2.md`

| # | Tên / vai | Đã trả lời vòng 1? | Q1: làm gì + bao lâu (nguyên văn) | Q2: xem hết? bỏ ở đâu (nguyên văn) | Q3: từng hỏi trùng? (nguyên văn) | Xác nhận (a/b/không) | Q4 willing user? |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| … | | | | | | | |

**Tổng kết cần điền sau khi thu:**
- n = `__` người ngoài nhóm · ghép được với vòng 1: `__` người
- Xác nhận: `__/__` = `__%` → **đạt / chưa đạt** chuẩn ≥50% · theo (a): `__` · theo (b): `__`
- Q3 "có": `__/__` = `__%` *(đối chiếu mining B8: 53 nhóm câu trùng / 263 tin)*
- **Số phút trung vị cho một lần ôn lại: `__` phút** *(đối chiếu mining B11: 85 phút đọc transcript/buổi, và vòng 1 A2: 68% dành ≥30 phút đọc slide)*
- Willing user thu được: `__` tên → cập nhật `spec.md` §8

---

## Quy tắc bảo mật cho cả hai vòng

- CSV thô từ Google Form (có họ tên đầy đủ + mã HV) **không commit**.
- Log trong repo: giữ **tên** (rubric R1/R6 cần tên/vai để phúc khảo), **mask mã HV** còn 2 số cuối — guide §3.4 cấm đưa thông tin cá nhân lên repo public, và mã HV không giúp gì cho việc chấm.
- Không suy ngược, không ghép mã HV với mã ẩn danh `U….` của chatlog.
