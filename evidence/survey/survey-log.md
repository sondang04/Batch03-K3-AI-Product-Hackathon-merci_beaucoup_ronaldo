# Log khảo sát Đường A — vòng 1 · n = 25 · 30/07/2026 10:40-10:55

**Hình thức:** Google Form 6 câu, tự điền, thu trong giờ nghỉ. **Người ngoài nhóm:** 25/25.
**Phân tích:** `python3 evidence/survey/analyze_survey.py` → `survey-analysis.txt`.

> **Mã học viên đã mask** (giữ 2 số cuối). Lý do: guide §3.4 cấm đưa thông tin cá nhân lên repo public; rubric R1/R6 chỉ yêu cầu **tên/vai**, không yêu cầu mã HV. Bản thô có mã đầy đủ giữ ngoài repo, ban tổ chức cần thì nhóm xuất lại được.
> **File CSV thô không commit** — chứa họ tên đầy đủ + mã HV của 25 người.

## Câu hỏi đã dùng (nguyên văn trong form)

1. Họ và Tên
2. Mã học viên (5 số cuối)
3. Đánh giá từ 1 đến 5 về độ khó của nội dung trong các buổi lecture
4. Bạn dành bao nhiêu thời gian để đọc nội dung trong slide bài học của lecture buổi chiều?
5. Trong buổi học lecture chiều, thời gian bạn thực sự tập trung nghe giảng chiếm tới bao nhiêu phần trăm? (Bấm số)
6. Nếu có một discord bot có thể giúp bạn tóm tắt bài học thực tế đã nghe trong buổi chiều, có bao gồm phản ánh nội dung bài học cũng như phần Q&A, bạn có muốn sử dụng không?
7. Bạn có comment gì khác không?

## Log từng phản hồi

| # | Tên | Mã HV | Độ khó (1-5) | Đọc slide | % tập trung | Muốn dùng? | Comment nguyên văn |
|---|---|---|:---:|---|:---:|---|---|
| 1 | Đoàn Nhật Nam | `…23` | 3 | 30p-1h | 68% | Chưa chắc | "Nố nô nố" |
| 2 | Trần Đức Mạnh | `…67` | 2 | <30p | 60% | Có | — |
| 3 | Dũng | `…19` | 3 | 30p-1h | 70% | Có | "Không" |
| 4 | Vi Minh Hiền | `…43` | 4 | <30p | 40% | Có | — |
| 5 | Phạm Bách | `…26` | 1 | <30p | 5% | Có | "Không" |
| 6 | Nguyễn Xuân Phượng | `…74` | 3 | 30p-1h | 80% | Có | — |
| 7 | Phạm Nguyễn Đăng Khôi | `…43` | 2 | 30p-1h | 40% | Chưa chắc | — |
| 8 | Phước | `…15` | 3 | 1h-2h | 80% | Có | **"Mình cần nó phải tóm tắt được những keyword chính."** |
| 9 | Trần Quốc Hùng | `…83` | 3 | 30p-1h | 60% | Có | — |
| 10 | Đinh Xuân Huh | `…94` | 4 | 1h-2h | 60% | Có | — |
| 11 | Bùi Thị Như Ngọc | `…82` | 4 | <30p | 50% | Có | "không" |
| 12 | Cao Thị Thu Trang | `…85` | 3 | 30p-1h | 80% | Chưa chắc | — |
| 13 | Trương Thảo Nguyên | `…89` | 3 | 1h-2h | 90% | Có | — |
| 14 | Nguyễn Doãn Hoàng | `…19` | 3 | 30p-1h | 70% | Có | — |
| 15 | Phạm Hà Linh | `…41` | 3 | 1h-2h | 90% | Có | — |
| 16 | Đinh Quốc Trung | `…87` | 4 | 30p-1h | 60% | Có | "Không có" |
| 17 | Hà Hùng | `…29` | 3 | 30p-1h | 60% | Có | — |
| 18 | Dương Vũ | `…63` | 3 | 30p-1h | 50% | Có | — |
| 19 | Cao Nhật Minh | `…21` | 3 | <30p | 60% | Có | — |
| 20 | Nguyễn Nam Anh | `…03` | 4 | 30p-1h | 90% | Có | "Chúc anh em thành công" |
| 21 | Trần Anh Thư | `…11` | 4 | Hơn 2h | 70% | Có | — |
| 22 | Việt | `…37` | 2 | <30p | 70% | Có | "Không" |
| 23 | Phùng Văn Đạt | `…12` | 3 | <30p | 80% | Chưa chắc | — |
| 24 | Nguyễn Đức Tín | `…85` | 3 | <30p | 50% | Có | — |
| 25 | Nguyễn Đức Sơn | `…85` | 3 | 1h-2h | 30% | Có | "Không" |

## Kết quả tổng hợp

| Câu | Kết quả | Dùng được không |
|---|---|---|
| **Q5 · % tập trung** | mean **62,5%** · median 60% · min 5% · max 90% · **52% học viên tập trung ≤60%** | ✅ **số mạnh nhất vòng này** — hành vi tự khai, không phải ý kiến |
| **Q4 · đọc slide** | **68% (17/25) dành ≥30 phút** · 24% (6/25) dành ≥1 giờ | ✅ hành vi |
| **Q3 · độ khó** | mean **3,04**/5 · **84% (21/25) chấm ≥3** · không ai chấm 5 | ✅ hành vi/cảm nhận |
| **Giao nhau khó ≥3 ∧ tập trung ≤60%** | **40% (10/25)** | ✅ đoạn user cần recap nhất |
| **Q6 · ý định dùng** | Có **84%** (21/25) · Chưa chắc 16% (4/25) · **Không 0%** | ⚠️ **KHÔNG dùng làm bằng chứng chính** — xem dưới |
| **Q7 · comment** | **1/25 (4%)** có nội dung | ⚠️ quá ít để rút pattern |
| **Tỷ lệ xác nhận** | **23/25 = 92%** — xác nhận = (a) tập trung ≤60% *hoặc* (b) đọc slide ≥30 phút *(a: 52% · b: 68% · cả hai: 28%)* | ✅ đạt ≥50%, ⚠️ định nghĩa **post-hoc** — xem giới hạn 6 |

## Giới hạn — ghi để không tự lừa mình

1. **Q6 là câu hỏi ý kiến về tính năng chưa tồn tại, và mô tả sẵn sản phẩm ngay trong câu hỏi.** Guide §1.3 mục 4 cảnh báo đúng dạng câu này: "hầu như ai cũng trả lời có, dữ liệu thu được không dùng được". Nên **84% "Có" không được dùng để chứng minh nhu cầu**. Nhóm dùng nó đúng một việc: **0% trả lời "Không"** ⇒ không ai phản đối hướng đi, và 4 người "Chưa chắc" là **người thử tốt nhất** cho vòng validation CP5.
2. **Q5 là tự khai, không đo.** Có thể lệch cả hai chiều. Một phản hồi ghi 5% — hoặc là thật, hoặc là điền cho xong; nhóm giữ nguyên trong log thay vì loại, và báo cáo cả mean lẫn median.
3. **Không có câu nào hỏi "lần gần nhất"** ⇒ chưa có số phút thật cho việc *ôn lại một buổi*, chưa đối chiếu được với mining B11 (85 phút đọc transcript/buổi).
4. **Không có câu nào hỏi "bạn có đồng ý thử prototype không?"** ⇒ 25 người này **chưa phải willing user**. Vẫn phải đi xin riêng ≥3 người (spec §8).
5. **Thu trong 15 phút giờ nghỉ, tự chọn tham gia** ⇒ thiên lệch về người đang có mặt và chịu điền form.
6. **Định nghĩa "xác nhận" là post-hoc.** Form không có câu hỏi trực tiếp "bạn có từng bỏ dở việc ôn lại", nên tiêu chí xác nhận được dựng từ Q4+Q5 **sau khi đã thấy dữ liệu**. Guide yêu cầu chốt trước khi đếm ⇒ 92% là số đúng nhưng ở bậc bằng chứng thấp hơn mining. Vòng 2 có định nghĩa chốt trước.

→ **Vòng 2 vá điểm 1, 3, 4** bằng 3 câu hồi tưởng ở `survey-instrument.md`.
