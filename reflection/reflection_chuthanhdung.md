# Reflection Cá Nhân — Chu Thành Dũng

- **Học viên**: Chu Thanh Dũng
- **Dự án**: `/recap` — Trợ lý AI ôn tập bài giảng qua Discord / Web
- **Nhóm**: Merci Beaucoup Ronaldo

---

## 1. Phân công công việc
Trong dự án, tôi phụ trách các phần kỹ thuật chính sau:
- **Bộ Tools & Agent Loop**: Khai báo 7 tools (`tools.py`) và triển khai vòng lặp suy luận ReAct (`agent.py`).
- **Discord Bot**: Cài đặt Slash Commands (`/recap`, `/hoi`), xử lý giao diện Select Menu, tin nhắn `ephemeral` và tối ưu bất đồng bộ (`bot.py`, `ui_discord.py`).
- **Trace Logger**: Ghi vết log chi tiết cho từng phiên chạy AI (`trace.py`).

---

## 2. Bài học rút ra & Thách thức
* **Tư duy thiết kế Tool**: Đưa đúng giới hạn và ngữ cảnh cho AI qua Tool là chìa khóa chống bịa đặt (Anti-Hallucination), ép AI phải lấy dữ liệu thật trước khi trả lời.
* **Tối ưu UX Discord**: Xử lý giới hạn 3s timeout bằng `defer()` và cắt chia tin nhắn thông minh giúp người dùng có trải nghiệm mượt mà.

---

## 3. Đánh giá bản thân
* **Đã hoàn thành**: Các module được giao chạy ổn định, kết nối mượt mà giữa Lõi AI và Discord.
* **Hướng cải thiện**: Tiếp tục tối ưu thêm xử lý lỗi mạng khi gọi API và viết thêm unit test.
