# Giải pháp của team — một đoạn

> Bản điền vào form BTC. Mọi con số đều tái tạo được: mining `evidence/mining/`,
> khảo sát `evidence/survey/`, số đo sản phẩm `eval/runs/`.

## Bản chính (điền vào form)

**278/369 học viên K3 (75,3%)** đang gặp khó khăn khi họ **ôn lại một buổi lecture
2-3 tiếng** trong bối cảnh **chỉ có bộ slide bullet rời và một bản ghi dài, không có
bản đồ nào cho biết buổi học gồm mấy phần và mình vướng ở đâu — còn thắc mắc của cả
lớp thì khoá kín trong 585 hội thoại riêng tư, không ai xem được của ai**, với tần
suất **sau mỗi buổi lecture, ~6 buổi/khoá**. Hiện họ đang **chữa cháy bằng cách tự
đọc lại slide (65,5% mất ≥30 phút, 24% mất ≥1 giờ) hoặc hỏi lại AI tutor — nhưng
40% yêu cầu tóm tắt bị tutor trả "không tìm thấy nội dung", và 46,2% câu trả lời
không kèm căn cứ**. Dẫn tới **mất 85 phút đọc transcript cho một buổi; học viên có
mặt vẫn tự khai mất ~37,3% buổi giảng; 27,6% vừa mất tập trung vừa không ôn lại nên
nội dung buổi đó mất luôn; và 53 nhóm câu hỏi trùng nguyên văn (263 tin) — hỏi lại
đúng câu người khác đã hỏi**. Team **merci_beaucoup_ronaldo** giải quyết vấn đề đấy
bằng **một Discord bot `/recap`: cắt buổi học thành 8-15 block bấm chọn được, mỗi
block 4-6 ý mà ý nào cũng mang mã đoạn `[T04-053]` bấm ra xem được nguyên văn lời
giảng viên, kèm mục "Bạn học từng vướng gì ở đây" gom từ thắc mắc thật của lớp; chỗ
nào không có căn cứ trong buổi thì bot nói thẳng là không có và chỉ sang đúng nơi,
không bịa**. Team **giảm 88% thời gian ôn một buổi (85 phút → 10 phút) và đưa tỉ lệ
câu trả lời có căn cứ từ 53,8% lên 100%**.

## Số ở đâu ra (để team khác hỏi được)

| Con số | Nguồn |
|---|---|
| 75,3% · 40% · 46,2% · 53 nhóm trùng · 85 phút | Mining **toàn bộ** 1.261 câu hỏi chatlog VLearn + 6 transcript — `python3 evidence/mining/mine_chatlog.py` |
| 65,5% · 37,3% · 27,6% | Khảo sát **n=29** người ngoài nhóm — `evidence/survey/` |
| 10 phút · 100% có căn cứ | Đo trên **recap thật** do sản phẩm sinh ra — `eval/runs/luot-4.md` |

## Ba câu team khác hay hỏi

**"88% là đo hay đoán?"** — Đo trên artifact: recap Day 1 giữ 12% số từ buổi
(2.011/17.088 từ) → ~10 phút đọc so với 85 phút đọc transcript. **Nhưng chưa có
user thật nào ngồi đọc để xác nhận** — đó là việc vòng validation CP5.

**"Sao không để bot trả lời mọi thứ như ChatGPT?"** — Vì sai thì học viên học sai
mà không tự phát hiện. Bot chỉ trích và sắp xếp lại lời giảng viên; hỏi ReAct
(26 học viên từng hỏi) thì nó nói "không có trong buổi này, thuộc Day 3" chứ không
tự giảng. Hỏi deadline thì từ chối, chỉ sang `#logistics`.

**"Gán thắc mắc vào block sai thì sao?"** — Đó là rủi ro lớn nhất: học viên tưởng
chỗ đó là chỗ khó của lớp rồi học lệch, và **không có cách nào tự phát hiện**. Nên
bot chạy **conditional**: confidence <0.6 thì không gán, dồn vào mục `❓ Chưa gán
được` — thà để trống hơn gán bừa.
