# Logs — trace & vòng cải thiện agent

## Cấu trúc

```
logs/
├── traces/        # 1 file JSONL / 1 phiên agent (tự sinh bởi agent/trace.py)
│                  #   session_start → user_message → llm_call / tool_call … → session_end
├── eval-runs/     # kết quả mỗi lượt chạy test --live (run_tests.py tự ghi)
└── notes/         # ghi chú cải thiện — MỖI LẦN SỬA PROMPT/TOOL MỘT FILE (xem dưới)
```

**Trace giữ trong repo** — rubric R5 yêu cầu "≥1 lời gọi AI thật ở quyết định
trung tâm (log/trace trong repo)". Để không vi phạm bảo mật data pack, mọi
chuỗi trong trace bị cắt ≤200 ký tự và luôn kèm mã (`Txx-NNN`/`M…`) — người
chấm đối chiếu ngược về data pack được, nhưng repo không chứa nguyên văn dài.
Test offline có một kiểm riêng bắt buộc điều này (`trace bị cắt ≤…`).

## Vòng cải thiện (guide §4.1 — nhịp lặp)

1. **Chạy trọn bộ**: `python3 codebase/tests/run_tests.py --live --provider …`
   → báo cáo JSON mới trong `eval-runs/`.
2. **Đọc trace của case fail** trong `traces/` — xem model gọi thiếu tool nào,
   tool trả gì, model bịa ở lượt nào.
3. **Chọn MỘT failure đau nhất** → sửa (system prompt / tool description /
   dispatch). Ghi một file vào `notes/`:

   ```markdown
   # 2026-07-30-o3-react-van-giai-thich.md
   - Case fail: O3 — model vẫn giảng ReAct dù search rỗng
   - Trace: traces/20260730-...-live-O3-....jsonl
   - Chẩn đoán: ghi_chú 'thuộc Day 3' nằm cuối kết quả tool, model bỏ qua
   - Sửa: đưa ghi_chú lên đầu JSON + thêm 1 dòng nhấn trong system prompt
   - Kết quả sau sửa: eval-runs/live-...json — O3 pass, không case nào vỡ
   ```

4. **Chạy lại TRỌN BỘ** (sửa chỗ này vỡ chỗ kia là chuyện thường của prompt).
5. Thay đổi có ý nghĩa sản phẩm → ghi thêm vào `spec.md` §9 Changelog.

Bộ test này là **smoke test cho dev loop** — chấm đậu/rớt bằng regex.
Golden set 28 case chấm tay theo 4 chiều C1-C4 vẫn ở `eval/golden-set.md`
và là thứ tính điểm (quality bar đã chốt, không đổi).
