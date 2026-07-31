# Reflection cá nhân — Cao Nam Cường

Nhóm **merci_beaucoup_ronaldo** · Hướng C (làn mở, dùng data pack VLearn, giao diện Discord)
Sản phẩm: `/recap` — agent dựng lại một buổi lecture thành các block có trích dẫn + cụm thắc mắc của bạn học.

---

## 1. Vai trò và phần tôi làm

**Vai trò: chủ spec** — theo bảng phân công [spec.md §8](spec.md#L385): *spec.md §1–§9, changelog, chốt quality bar trước 23:59 N1*. Ngoài ra tôi làm **vòng tối ưu system prompt đầu tiên** và giữ nhánh tích hợp của nhóm.

| Việc | Artifact trỏ về được |
|---|---|
| Viết toàn bộ [spec.md](spec.md) §1–§9: problem statement không-chữ-AI, bảng impact 5 ứng viên + lý do loại, lát cắt một câu, 6 non-goals, mức automation, 7 nguyên tắc HAX/PAIR, 4 lớp chỗ khó + 16 kịch bản, 4 chiều chất lượng, quality bar, changelog | [spec.md](spec.md) |
| Chốt **quality bar bằng số trước 23:59 N1** và không sửa sau đó | [spec.md §7 · Quality bar](spec.md#L343) |
| Tối ưu system prompt vòng 1 (commit `1a4b502 optimize prompt version 1`) | [codebase/agent/prompts/system.md](codebase/agent/prompts/system.md) |
| Tích hợp nhánh của Sơn / Dũng / Đăng về nhánh chung, giữ spec khớp với bản build thật | `git log` các commit merge trên `2A202601661-caonamcuong` |

Tôi **không** viết `bot.py`, không viết `mine_chatlog.py`, không viết `run_golden.py` — đó là phần của Dũng, Sơn, Đăng. Phần tôi chịu trách nhiệm giải thích là ba mục dưới đây.

---

## 2. Ba quyết định tôi phải giải thích được (vibe-coding rule)

### (a) Vì sao loại ứng viên #2 — "sửa prompt tutor bắt buộc cite" — dù nó có con số pain to nhất

46,2% câu trả lời của tutor hiện tại không có citation (B5), 78,4% câu bị 👎 là câu không cite (B6). Nhìn số thì đây là ứng viên mạnh nhất. Tôi loại nó vì **con số B3**: trong các turn xin tóm tắt, **40,0% (52/130) tutor trả lời "không tìm thấy / không truy cập được nội dung"**. Đó là fail ở **tầng nguồn**, không phải tầng prompt — tutor không được cấp bản ghi buổi học. Sửa prompt khi vẫn thiếu nguồn thì chỉ làm câu từ chối nghe hay hơn. Ứng viên #1 giải đúng nguyên nhân đó: **cấp nguồn (transcript + slide) và cấp cấu trúc (block)**. Ghi tại [spec.md §2](spec.md#L168).

### (b) Vì sao automation là **conditional**, không phải automate

Lát cắt có hai quyết định AI, cost-of-error khác hẳn nhau:

- **Cắt block + tóm tắt** → sai thì **rẻ và học viên tự thấy**: mỗi gạch đầu dòng mang mã `[Txx-NNN]`, bấm là đối chiếu nguyên văn trong 5 giây.
- **Gán cụm thắc mắc vào block** → sai thì **đắt và học viên KHÔNG tự thấy**. Gán cụm "26 người vướng ReAct" vào block Attention thì học viên tin Attention là chỗ khó của lớp, đầu tư thời gian sai chỗ, và không có bản gốc nào để phát hiện. Nên ngưỡng `confidence ≥ 0.6`; dưới ngưỡng → `❓ Chưa gán được`. **Thà để trống hơn gán bừa.**

Có một lý do kỹ thuật đứng sau, không phải cảm tính: `day_code` trong chatlog **không map được** sang file transcript, nên gán thắc mắc là **khớp theo nội dung**, không phải join theo ID — [spec.md §4, giới hạn dữ liệu #1](spec.md#L240). Một phép khớp mềm thì buộc phải có đường từ chối. Đó cũng là lý do chiều **C2** tồn tại trong bộ tiêu chí.

### (c) Vì sao quality bar viết dạng "% **AND** hai điều kiện cứng"

Bar chốt: *≥75% (21/28) case pass, **VÀ** (a) 0/28 case bịa nội dung ngoài đoạn được trỏ, (b) 0/28 case fail C4 (an toàn & phạm vi)*.

Tôi cố ý không cho hai điều kiện cứng đổi lấy phần trăm. Lý do thấy ngay ở **lượt 1**: máy chấm ra **22/28 = 79%**, tức là *đạt %* — nhưng case 12 model gán câu hỏi của lớp cho một mã học viên cụ thể (`U0270`). Nếu bar chỉ là một con số phần trăm, nhóm đã tuyên bố "đạt bar" ở lượt 1 và đi tiếp với một lỗi lộ danh tính trong sản phẩm. Vì bar là AND, lượt 1 bị tính là **không đạt**, và việc phải làm là chặn ở tầng tool chứ không phải xin thêm điểm phần trăm. Bảng 4 lượt: [spec.md §7](spec.md#L357).

### (d) Phần prompt tôi sửa — sửa gì và vì sao

Vòng `optimize prompt version 1` không phải viết lại cho "văn hay". Bốn thay đổi, mỗi cái vá một lỗi quan sát được:

1. **Thứ tự ưu tiên khi luật va nhau**: *an toàn & riêng tư → có căn cứ → đúng phạm vi → giọng văn*. Trước đó các luật nằm ngang hàng, model gặp xung đột thì tự chọn — và nó có xu hướng chọn luật định dạng.
2. **Luật copy mã trích dẫn**: "không suy ra mã lân cận — đã đọc `T04-046` thì KHÔNG được viết `T04-047`". Đây là kiểu bịa nguy hiểm nhất vì mã **trông đúng format** nên qua được mắt người đọc.
3. **Ngân sách 8 lượt + lệnh gọi tool song song**: recap cả buổi trước đó gọi tuần tự từng block rồi hết lượt giữa chừng, trả ra recap cụt.
4. **Mục "Định dạng recap" tách riêng + một mẫu câu trả lời đạt**: luật `🔑 Keyword`, luật `⚠️` cho block mất tiếng, luật khai báo phần chào lớp đã loại. Dòng Keyword đến từ feedback thật của Phước `…15` trong khảo sát (*"cần tóm tắt được keyword chính"*) — và tôi đưa nó vào **định nghĩa chiều C3** để nó thành tiêu chí đạt/không đạt, chứ không dừng ở một câu trong prompt.

---

## 3. AI hỗ trợ thế nào

**Chỗ AI làm tốt.** Dựng khung spec theo template và soát chéo tính nhất quán — spec 400+ dòng có rất nhiều chỗ dễ lệch nhau (non-goal #1 nói "không Q&A" trong khi §4 đã build grounded Q&A; số block trong bảng đo khác ràng buộc 8–15). Tôi dùng AI để quét những mâu thuẫn đó, nhanh hơn đọc tay nhiều lần. Với prompt, tôi dùng AI để viết lại một luật thành câu ngắn, cụ thể hơn (kiểu "không suy ra mã lân cận" thay cho "phải trích dẫn chính xác").

**Chỗ tôi không giao cho AI.** Ba thứ: **chọn ứng viên**, **chốt bar**, và **quyết định automation**. Không phải vì AI viết dở, mà vì AI viết ra một đoạn nghe rất hợp lý cho *bất kỳ* lựa chọn nào tôi đưa — nó không phản đối, nên nó không kiểm được lập luận của tôi. Cả ba quyết định này đều được ràng vào một con số cụ thể trong `mining-log.txt` / `survey-analysis.txt`, và đó là ràng buộc do người đặt.

**Chỗ AI làm tôi suýt sai.** Khi tôi nhờ soạn bảng impact, AI viết ứng viên #2 (sửa tutor) thành lựa chọn thắng — vì cột "bao nhiêu người × tần suất" của nó to nhất và AI chỉ nhìn bảng. Nó không tự nối sang B3 (fail ở tầng nguồn) để thấy rằng ứng viên đó **sửa nhầm tầng**. Bài học nhỏ: AI tối ưu theo đúng khung mình đưa cho nó; chọn sai khung thì nó sẽ giúp mình sai một cách rất thuyết phục.

---

## 4. Bài học từ một case fail của chính nhóm

**Case:** [`summarize_block` tóm tắt SAI block, nhãn vẫn là block học viên hỏi](codebase/logs/notes/2026-07-30-summarize-block-doan-sai-index.md) (lượt live 2–3, ngày 30/07).

Học viên hỏi recap block *"Attention, multi-head và bài học quản lý context"*. Model gọi `summarize_block(block_idx=3)` và `(block_idx=5)`, nhận về nội dung *Turing test / hai mùa đông* và *AlphaGo / Transformer*, rồi **in ra dưới nhãn "Block Attention, multi-head"**. Nội dung đúng, mã đoạn thật, chỉ có điều **sai block**. Lượt chạy sau nó chọn `block_idx=8` — đúng. Sai ngẫu nhiên, còn khó phát hiện hơn sai đều.

**Ba điều tôi rút ra, xếp theo mức đau:**

**(1) Spec lường đúng rủi ro không có nghĩa là sản phẩm đã chặn rủi ro đó.** Đây đúng là kịch bản ④ #15 tôi đã viết trong [spec.md §5](spec.md#L266): *"gán sai block → học viên học lệch, và không tự phát hiện được"*. Tôi đã viết ra nó, đã dựa vào nó để chọn automation conditional — và vẫn để lọt, vì tôi chặn ở **tầng prompt và tầng ngưỡng confidence**, còn lỗ hổng nằm ở **tầng contract của tool**. `summarize_block` trả về **duy nhất một chuỗi tóm tắt**, không nói nó vừa tóm tắt block nào. Model đoán một số, nhận về văn bản trông hợp lý, và **không có tín hiệu nào để tự biết đã chọn sai**. Không phải lỗi model — lỗi thiết kế tool. Bài học tôi mang đi: *một dòng trong spec chỉ có giá trị khi trỏ được vào chỗ trong code nơi nó được thực thi.* Đúng ra ở cột "áp cụ thể vào đâu trong prototype" của §4b, tôi nên bắt mình trỏ tới **chữ ký hàm**, không chỉ tới một câu luật trong prompt.

**(2) Bộ test tự mock mất phần dễ sai nhất thì nó không còn là test.** Lỗi này **không phải test suite bắt được** — nó lộ ra khi chạy demo thật. Bộ test cũ mock sẵn `block_idx: 8`, tức là nó đã cho sẵn model đáp án của đúng bước dễ sai nhất (chọn block). Test luôn xanh, sản phẩm vẫn hỏng. Cách sửa: thêm case regression **S3** với `live_forbid: turing test|alphago` — nếu sau này nó lại dán nhãn Attention lên nội dung khác thì test đỏ.

**(3) Đừng để model phải đoán — hãy trả lại danh tính của thứ nó vừa nhận.** Bản sửa đi theo hướng đó: `summarize_block` nhận `title_query` (tên block) thay vì số; kết quả trả về `{block_idx, tieu_de, dai_ma, tom_tat, nhac}` để model **nhìn thấy** tiêu đề nó vừa tóm tắt và đối chiếu với điều học viên hỏi. Live trọn bộ sau khi sửa: **10/10**. Cùng bài học này còn cứu một lỗi thứ hai — case S2 "hai mùa đông": model search, nhận 0 kết quả, rồi **từ chối thật thà** — hành vi đúng như spec muốn, nhưng từ chối **oan**, vì `search_transcript` khớp substring liền mạch còn transcript viết *"trải qua hai lần mùa đông"*. Tool yếu làm agent từ chối một câu mà buổi học có trả lời, và học viên sẽ tưởng nội dung không có trong bài. Hai case, cùng một gốc: **agent chỉ tốt bằng contract của tool bên dưới nó.**

---

## 5. Điều tôi biết là còn dở

Ghi thẳng, không giấu:

- **100% ở lượt 4 không phải độ tin cậy thật.** Case 06 và case 15 fail ở lượt 3, pass ở lượt 4 mà **sản phẩm không đổi một dòng**. Hai chiều `C1 format` và `C3 giữ giọng` đang flaky. Kết luận đúng phải là chạy mỗi case ≥3 lần lấy tỉ lệ, không lấy một lượt làm số cuối. Tôi đã ghi điều này vào [spec.md §7](spec.md#L364) thay vì để con số 100% đứng một mình.
- **Willing user và vòng validation là chỗ nhóm yếu nhất.** [validation/feedback-log.md](validation/feedback-log.md) đến giờ vẫn trống bảng; khảo sát vòng 1 (n=29) không hỏi câu "bạn có đồng ý thử prototype không", nên phải đi xin trực tiếp — và bảng willing user trong §8 vẫn còn ô `⬜ chưa xin`. Là chủ spec, tôi đưa được kế hoạch phiên test 10 phút/người vào spec nhưng không đẩy nó thành việc có deadline sớm như đã làm với quality bar. Nếu làm lại, tôi chốt willing user ngay ở CP1 cùng lúc chốt lát cắt — vì nó cũng là một dòng của tiêu chí nghiệm thu, chỉ khác là nó không tự chạy được bằng script.
- **`peer_questions` vẫn còn failure chưa sửa**: nó khớp substring trên **mọi** câu hỏi nên gom cả câu logistics vào cụm "lớp vướng gì", và có lượt in "5 người" rồi liệt kê 6 mã. Cần lọc theo nhãn A/B của `mine_chatlog.py` trước khi gom cụm. Đã ghi lại ở [note lượt live 2-3](codebase/logs/notes/2026-07-30-summarize-block-doan-sai-index.md#L41), chưa xử lý.

**Một câu mang đi:** thứ tôi tưởng mình làm — *viết spec* — hoá ra là phần dễ. Phần khó là làm cho mỗi dòng trong spec có một chỗ tương ứng trong code chịu trách nhiệm thi hành nó, và một case trong golden set chịu trách nhiệm kiểm nó. Chỗ nào đứt một trong hai mắt xích ấy thì dòng spec đó chỉ là một câu hay.
