# Reflection cá nhân — Cao Nam Cường

Nhóm **merci_beaucoup_ronaldo** · Hướng C (làn mở, data pack VLearn, giao diện Discord)
Sản phẩm: `/recap` — agent dựng lại một buổi lecture thành các block có trích dẫn + cụm thắc mắc của bạn học.

---

## 1. Vai trò và phần tôi làm

**Vai trò: Evidence** — theo [spec.md §8](spec.md#L386): mining chatlog và khảo sát Đường A. Ngoài ra tôi làm vòng tối ưu system prompt đầu tiên (`1a4b502`) và giữ nhánh tích hợp của nhóm.

| Việc | Artifact trỏ về được |
|---|---|
| Mining toàn bộ chatlog — 1.261 turn / 369 học viên, không lấy mẫu; 15 phát hiện B1–B15 nuôi §1–§2 | [evidence/mining/mine_chatlog.py](evidence/mining/mine_chatlog.py) · [mining-log.txt](evidence/mining/mining-log.txt) |
| Khảo sát Đường A vòng 1, **n = 29** (chuẩn ≥20) — thiết kế form 6 câu, thu 2 đợt, phân tích A1–A6 + A4b | [analyze_survey.py](evidence/survey/analyze_survey.py) · [survey-log.md](evidence/survey/survey-log.md) · [survey-analysis.txt](evidence/survey/survey-analysis.txt) |
| Chốt bộ 3 câu **hồi tưởng** cho vòng 2 (vá giới hạn ①③④) | [survey-instrument.md](evidence/survey/survey-instrument.md) |
| Tối ưu system prompt vòng 1 + merge nhánh Sơn / Dũng / Đăng về nhánh chung | [agent/prompts/system.md](codebase/agent/prompts/system.md) · `git log` |

Tôi **không** viết `bot.py`, `recap.py`, `run_golden.py` — đó là phần của Dũng, Sơn, Đăng.

---

## 2. Ba quyết định tôi phải giải thích được (vibe-coding rule)

### (a) Vì sao đọc tay 40 mẫu **trước** khi viết regex phân loại

Cám dỗ là mở CSV rồi viết luôn regex theo những nhãn mình đoán sẵn. Tôi đọc tay 40 tin đầu trước để biết *loại pattern nào thực sự tồn tại*, rồi mới chốt 7 nhãn. Nhờ vậy mới thấy hai thứ không ai đoán ra từ trước: 99,3% câu hỏi có tiền tố `(Trang N, đoạn được chọn: …)` — **cầu nối kỹ thuật** cho việc gán thắc mắc vào block (B10); và 1,5% là probe/jailbreak (nhãn D), thứ sau này thành kịch bản #12.

Quy tắc đếm chốt trong code chứ không trong đầu: 7 nhãn **xét theo thứ tự, dừng ở nhãn khớp đầu tiên** (một tin chỉ vào đúng một nhãn, không đếm trùng), tin <12 ký tự vào nhãn E và **không** tính là câu hỏi. Ai chạy lại `mine_chatlog.py` cũng phải ra đúng số đó — đó là lý do nó là bằng chứng bậc **Mạnh** còn khảo sát chỉ là **Vừa**.

### (b) Vì sao tôi vứt con số đẹp nhất của khảo sát

A5 ra **79,3% nói "Có" muốn dùng bot tóm tắt**. Đây là con số dễ lên slide nhất, và tôi đề nghị nhóm **không dùng nó làm bằng chứng nhu cầu**. Vì câu đó hỏi ý kiến về một tính năng chưa tồn tại **và mô tả sẵn sản phẩm ngay trong câu hỏi** — guide §1.3 mục 4 cảnh báo đúng dạng này: hầu như ai cũng trả lời có. Thứ dùng được chỉ là **0% "Không"**, và **6 người "Chưa chắc" là người thử giá trị nhất** cho CP5, vì họ tập trung cao hơn (68,8% vs 61,1%) và đọc slide nhiều hơn (83,3% vs 60,9%) — họ có tiêu chuẩn so sánh nên sẽ nói thật.

Cùng tinh thần đó, tôi tự khai A6 (93,1% xác nhận) là **post-hoc**: form vòng 1 không có câu hỏi trực tiếp nào, nên tiêu chí xác nhận được dựng **sau khi đã thấy dữ liệu**. Số đúng, nhưng đứng ở bậc bằng chứng thấp hơn số mining, và tôi ghi thẳng điều đó vào [spec.md §1, giới hạn ⑥](spec.md#L137).

### (c) Phát hiện đắt nhất là một con số **0**

**B14:** `ReAct` — 35 câu hỏi từ 26 học viên trong chatlog, nhưng **0 lần xuất hiện trong cả 6 transcript**. Đây là chỗ nguy hiểm nhất của sản phẩm: cầu hỏi lớn ở đúng chỗ **không có căn cứ**, tức là chỗ agent sẽ bịa nếu không ai chặn. Tôi không dừng ở việc báo "không có", mà truy tiếp tên file slide trong chatlog và ra được `day03-tu-chatbot-den-agentic-agent-react.pdf` — **buổi Day 3, không có transcript trong pack**. Nhờ vậy agent nói được câu hữu ích hơn: *"ReAct thuộc buổi Day 3, không nằm trong buổi này"* thay vì chỉ từ chối. Phát hiện này đẻ ra mục `⚠️ Thắc mắc chưa có căn cứ` và kịch bản #1 — case nhóm chủ động demo live.

Cặp phát hiện thứ hai đến từ khảo sát chứ mining mù hoàn toàn: **A4b — 27,6% học viên vừa mất tập trung (≤60%) vừa không ôn lại (<30 phút)**, và tương quan `tập trung ↔ thời gian đọc` là **+0,32, CÙNG chiều** — nghĩa là khoảng cách **cộng dồn**, không tự bù. Nhóm này đã chứng minh bằng hành vi rằng họ không bỏ ≥30 phút ra ôn, nên recap phải **rẻ ≤15 phút**. Đó là ràng buộc thiết kế cứng duy nhất đến thẳng từ số khảo sát ([spec.md §4](spec.md#L235)).

---

## 3. AI hỗ trợ thế nào

**Làm tốt:** viết regex cho 7 nhãn, dựng script phân tích khảo sát, và soát chéo tính nhất quán của spec 400+ dòng (chỗ nào còn `n=25` sau khi khảo sát đóng ở 29, số block trong bảng đo lệch ràng buộc 8–15).

**Không giao cho AI:** định nghĩa nhãn và ngưỡng đếm. Không phải vì AI viết dở, mà vì nhãn là chỗ quyết định con số cuối cùng — đổi ngưỡng "≥2 học viên" thành "≥3" là 77,8% tụt còn 61,1%. Ngưỡng phải do người chốt **trước** khi đếm, nếu không thì mình đang chọn ngưỡng nào ra số đẹp.

**Chỗ AI làm tôi suýt sai:** khi nhờ tóm tắt kết quả khảo sát, AI đưa "79,3% muốn dùng" lên đầu như phát hiện chính — hợp lý theo đúng khung tôi đưa, và sai theo đúng cái bẫy guide đã cảnh báo. AI tối ưu theo khung mình đưa cho nó; đưa sai khung thì nó sẽ giúp mình sai một cách rất thuyết phục.

---

## 4. Bài học từ một case fail của chính nhóm

**Case:** keyword `giá` đếm ra **208 học viên** cùng hỏi — con số vô lý trên tổng 369, mà lại trông giống hệt một "điểm nóng" ngon lành. Nguyên nhân: khớp substring trên tiếng Việt bỏ dấu, `gia` khớp bên trong `giai` (giải) — mà "giải thích" là từ phổ biến nhất trong cả chatlog. Sau khi bắt token <5 ký tự phải khớp **biên từ**, con số thật là **7 người**.

Ba điều tôi rút ra:

**(1) Lỗi đếm không tự lộ ra — nó lộ ra ở chỗ số quá đẹp.** Không có exception, không có test đỏ. Thứ duy nhất bắt được nó là tôi nhìn `208/369` và thấy tỉ lệ đó không thể đúng. Từ đó tôi thêm thói quen: mọi con số mining phải kèm mẫu số và phải tự hỏi "tỉ lệ này có hợp lý không" trước khi đưa vào spec.

**(2) Cùng một gốc còn đẻ ra lỗi thứ hai.** Cụm thắc mắc lúc đầu gom **cả câu logistics** (`'bây h là mấy giờ'`, `'Canvas là hệ thống gì'`) — 37% câu vào cụm là rác. Sửa bằng cách chỉ lấy câu nhãn **A/B** của `mine_chatlog.py`. Bài học: bộ nhãn tôi làm ở bước mining là **hạ tầng cho các bước sau**, không phải một bảng thống kê để trưng bày — mà tôi đã không chủ động đem nó cho người dùng cụm.

**(3) Số sai làm hỏng sản phẩm chứ không chỉ hỏng slide.** `208 người vướng giá` mà lọt vào recap thì học viên đọc xong sẽ tin đó là chỗ khó nhất của lớp và đầu tư thời gian sai chỗ — đúng kịch bản ④ #15, chỉ khác là lỗi đến từ phía tôi chứ không từ model.

---

## 5. Điều tôi biết là còn dở

- **Khảo sát vòng 2 chưa chạy.** Bộ 3 câu hồi tưởng đã chốt trong `survey-instrument.md` nhưng chưa thu được phản hồi nào, nên ba giới hạn ①③④ vẫn còn nguyên: chưa có **số phút thật** cho việc ôn lại một buổi để đối chiếu với B11 (85 phút), và **29 người này chưa ai là willing user** vì vòng 1 không hỏi câu "bạn có đồng ý thử prototype không". Bảng willing user ở §8 còn trống là hệ quả trực tiếp của một câu hỏi tôi quên đưa vào form.
- **A1 là tự khai, không đo.** Con số quan trọng nhất của cả vòng khảo sát (62,7% tập trung) dựa vào trí nhớ người trả lời, lệch được cả hai chiều. Tôi giữ nguyên phản hồi ghi 5% trong log thay vì loại cho số đẹp, và báo cả mean lẫn median — nhưng đó là minh bạch về giới hạn, không phải khắc phục nó.
- **`day_code` trong chatlog không map được sang transcript** ([spec.md §4](spec.md#L240)). Tôi chỉ xác nhận được là *không map được*, chưa tìm ra đường nối nào khác, nên toàn bộ việc gán thắc mắc phải chạy bằng khớp nội dung — chính chỗ đẻ ra rủi ro C2 mà nhóm phải đi đường conditional.

**Một câu mang đi:** phần khó của evidence không phải chạy ra số, mà là chịu bỏ con số đẹp nhất mình vừa thu được và ghi rõ con số nào đứng ở bậc nào.
