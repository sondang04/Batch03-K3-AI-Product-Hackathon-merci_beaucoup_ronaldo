#!/usr/bin/env python3
"""
Phân tích khảo sát Đường A — Google Form, 29 phản hồi, 30/07/2026 10:40-13:32.
(đợt 1: 25 phản hồi trong 15 phút giờ nghỉ · đợt 2: +4 phản hồi rải đến chiều)

Chạy:  python3 evidence/survey/analyze_survey.py > evidence/survey/survey-analysis.txt

Nguồn thô: Google Form export (`Untitled form (Responses) - Form Responses 1.csv`).
File thô KHÔNG commit vào repo — nó chứa họ tên đầy đủ + mã học viên của 25 người.
Repo chỉ giữ `survey-log.md` (đã mask mã học viên) và output của script này.

6 câu trong form:
  Q1 Họ và Tên
  Q2 Mã học viên (5 số cuối)
  Q3 Đánh giá 1-5 độ khó nội dung các buổi lecture
  Q4 Thời gian đọc slide bài học của lecture buổi chiều
  Q5 % thời gian thực sự tập trung nghe giảng trong buổi chiều
  Q6 Nếu có discord bot tóm tắt bài học + Q&A, bạn có muốn dùng không?
  Q7 Comment khác
"""

import statistics as st

# (tên, mã HV, độ khó 1-5, thời gian đọc slide, % tập trung, ý định dùng, comment)
R = [
    ("Đoàn Nhật Nam",           "01123", 3, "30p-1h", 68, "Chưa chắc", "Nố nô nố"),
    ("Trần Đức Mạnh",           "01567", 2, "<30p",   60, "Có",        ""),
    ("Dũng",                    "01819", 3, "30p-1h", 70, "Có",        "Không"),
    ("Vi Minh Hiền",            "01743", 4, "<30p",   40, "Có",        ""),
    ("Phạm Bách",               "01526", 1, "<30p",    5, "Có",        "Không"),
    ("Nguyễn Xuân Phượng",      "01874", 3, "30p-1h", 80, "Có",        ""),
    ("Phạm Nguyễn Đăng Khôi",   "01243", 2, "30p-1h", 40, "Chưa chắc", ""),
    ("Phước",                   "01215", 3, "1h-2h",  80, "Có",
     "Mình cần nó phải tóm tắt được những keyword chính."),
    ("Trần Quốc Hùng",          "01683", 3, "30p-1h", 60, "Có",        ""),
    ("Đinh Xuân Huh",           "01894", 4, "1h-2h",  60, "Có",        ""),
    ("Bùi Thị Như Ngọc",        "01882", 4, "<30p",   50, "Có",        "không"),
    ("Cao Thị Thu Trang",       "01885", 3, "30p-1h", 80, "Chưa chắc", ""),
    ("Trương Thảo Nguyên",      "01389", 3, "1h-2h",  90, "Có",        ""),
    ("Nguyễn Doãn Hoàng",       "01119", 3, "30p-1h", 70, "Có",        ""),
    ("Phạm Hà Linh",            "01041", 3, "1h-2h",  90, "Có",        ""),
    ("Đinh Quốc Trung",   "2A202601687", 4, "30p-1h", 60, "Có",        "Không có"),
    ("Hà Hùng",                 "01629", 3, "30p-1h", 60, "Có",        ""),
    ("Dương Vũ",                "01663", 3, "30p-1h", 50, "Có",        ""),
    ("Cao Nhật Minh",     "2A202601721", 3, "<30p",   60, "Có",        ""),
    ("Nguyễn Nam Anh",          "01703", 4, "30p-1h", 90, "Có",        "Chúc anh em thành công"),
    ("Trần Anh Thư",            "01611", 4, "Hơn 2h", 70, "Có",        ""),
    ("Việt",                    "01737", 2, "<30p",   70, "Có",        "Không"),
    ("Phùng Văn Đạt",           "02012", 3, "<30p",   80, "Chưa chắc", ""),
    ("Nguyễn Đức Tín",          "01185", 3, "<30p",   50, "Có",        ""),
    ("Nguyễn Đức Sơn",          "01485", 3, "1h-2h",  30, "Có",        "Không"),
    # ── đợt 2: thu thêm 11:12-13:32 cùng ngày (n 25 → 29) ────────────────────
    ("Trần Chí Tâm",            "01535", 3, "30p-1h", 75, "Chưa chắc", ""),
    ("Trương Văn Thái",         "01801", 2, "<30p",   60, "Có",        ""),
    ("Hoang Phong",             "01077", 2, "<30p",   50, "Có",        ""),
    ("Đào Tùng Bách",     "2A202601745", 3, "1h-2h",  70, "Chưa chắc", ""),
]

# Comment vô nội dung — không tính là feedback
RỖNG = {"", "không", "Không", "Không có", "Nố nô nố", "Chúc anh em thành công"}

BUCKET = ["<30p", "30p-1h", "1h-2h", "Hơn 2h"]


def pct(a, b):
    return f"{a}/{b} = {100 * a / b:.1f}%"


def h(t):
    print()
    print("=" * 74)
    print(t)
    print("=" * 74)


n = len(R)
h(f"0 · PHẠM VI — n = {n} người ngoài nhóm (chuẩn A yêu cầu ≥20)")
print("thời điểm thu   : 30/07/2026 10:40-13:32 (đợt 1: 10:40-10:55 giờ nghỉ · đợt 2: 11:12-13:32)")
print("hình thức       : Google Form, 6 câu, tự điền")
print(f"đợt 1 / đợt 2   : 25 / {n - 25}")
print(f"mã HV trùng lặp : {n - len({r[1] for r in R})}")

h("1 · Q6 · Ý ĐỊNH DÙNG  ⚠️ ĐỌC PHẦN CẢNH BÁO Ở CUỐI TRƯỚC KHI TRÍCH SỐ NÀY")
for k in ("Có", "Chưa chắc", "Không"):
    c = sum(1 for r in R if r[5] == k)
    print(f"  {k:12s} {pct(c, n)}")
print("\n  → Đây là câu hỏi Ý KIẾN về tính năng chưa tồn tại (guide §1.3 mục 4 cảnh báo")
print("    đúng dạng câu này). KHÔNG dùng làm bằng chứng chính. Xem mục 5.")

h("2 · Q5 · % THỜI GIAN THỰC SỰ TẬP TRUNG NGHE GIẢNG  ← số hành vi, mạnh nhất")
a = sorted(r[4] for r in R)
print(f"  mean {st.mean(a):.1f}%  ·  median {st.median(a)}%  ·  min {a[0]}%  ·  max {a[-1]}%")
print(f"  → trung bình học viên TỰ KHAI mất {100 - st.mean(a):.1f}% buổi lecture dù có mặt")
for th in (50, 60, 70):
    print(f"  tập trung ≤{th}% : {pct(sum(1 for x in a if x <= th), n)}")
print(f"  tập trung <50%  : {pct(sum(1 for x in a if x < 50), n)}")

h("3 · Q4 · THỜI GIAN TỰ ĐỌC SLIDE BUỔI CHIỀU  ← số hành vi")
for b in BUCKET:
    print(f"  {b:8s} {pct(sum(1 for r in R if r[3] == b), n)}")
ge30 = sum(1 for r in R if r[3] != "<30p")
ge1h = sum(1 for r in R if r[3] in ("1h-2h", "Hơn 2h"))
print(f"\n  ≥30 phút : {pct(ge30, n)}   ≥1 giờ : {pct(ge1h, n)}")
print("  → chi phí tự học SAU buổi đã tồn tại, trên SLIDE thôi, chưa tính bản ghi")

h("4 · Q3 · ĐỘ KHÓ NỘI DUNG (1-5)")
d = [r[2] for r in R]
for k in range(1, 6):
    print(f"  {k} điểm : {'█' * d.count(k):15s} {d.count(k)}")
print(f"\n  mean {st.mean(d):.2f}  ·  median {st.median(d)}  ·  ≥3 điểm: {pct(sum(1 for x in d if x >= 3), n)}")

h("5 · GIAO NHAU: KHÓ + MẤT TẬP TRUNG  ← nhóm cần recap nhất")
both = [r for r in R if r[2] >= 3 and r[4] <= 60]
print(f"  độ khó ≥3 VÀ tập trung ≤60%: {pct(len(both), n)}")
for r in both:
    print(f"    {r[0]:24s} khó {r[2]} · tập trung {r[4]}% · đọc slide {r[3]}")

h("6 · TỶ LỆ XÁC NHẬN — chuẩn A yêu cầu ≥50%")
print("""  ⚠️ Định nghĩa "xác nhận" dưới đây được đặt SAU khi đã thấy dữ liệu (post-hoc),
     vì form vòng 1 không có câu nào hỏi trực tiếp "bạn có từng bỏ dở việc ôn lại".
     Yếu hơn yêu cầu của guide (chốt định nghĩa TRƯỚC khi đếm). Vòng 2 có định
     nghĩa chốt trước — xem survey-instrument.md.

  Xác nhận = có dấu vết hành vi cho thấy việc ôn lại vừa cần vừa tốn:
     (a) tập trung ≤60% buổi giảng  → có phần chưa nghe rõ, cần ôn
     (b) dành ≥30 phút đọc lại slide → đã bỏ thời gian thật cho việc ôn""")
A = [r for r in R if r[4] <= 60]
B = [r for r in R if r[3] != "<30p"]
print()
print(f"  (a) tập trung ≤60%      : {pct(len(A), n)}")
print(f"  (b) đọc slide ≥30 phút  : {pct(len(B), n)}")
print(f"  (a) VÀ (b)              : {pct(sum(1 for r in R if r[4] <= 60 and r[3] != '<30p'), n)}")
u = sum(1 for r in R if r[4] <= 60 or r[3] != "<30p")
print(f"  (a) HOẶC (b) = XÁC NHẬN : {pct(u, n)}  → {'ĐẠT' if u / n >= .5 else 'CHƯA ĐẠT'} chuẩn ≥50%")
print(f"  không thoả cả (a) và (b): {pct(n - u, n)}")

h("7 · Q7 · COMMENT CÓ NỘI DUNG")
sub = [r for r in R if r[6] not in RỖNG]
print(f"  {pct(len(sub), n)} phản hồi có nội dung — phần còn lại để trống hoặc 'không'")
for r in sub:
    print(f'    [{r[0]}] "{r[6]}"')

h("8 · ĐỢT 1 vs ĐỢT 2 — mẫu 15 phút giờ nghỉ có thiên lệch không?")
d1, d2 = R[:25], R[25:]
print(f"{'':22} {'đợt 1 (n=25)':>14} {'đợt 2 (n=4)':>13}")
for nhan, f in (("độ khó (mean)", lambda g: st.mean(r[2] for r in g)),
                ("% tập trung (mean)", lambda g: st.mean(r[4] for r in g)),
                ("đọc slide ≥30p", lambda g: 100 * sum(1 for r in g if r[3] != "<30p") / len(g)),
                ('ý định "Có" (%)', lambda g: 100 * sum(1 for r in g if r[5] == "Có") / len(g))):
    print(f"  {nhan:20} {f(d1):14.1f} {f(d2):13.1f}")
print("""
  → Đợt 2 nhỏ (n=4) nên không kết luận thống kê được, nhưng hướng thì giống đợt 1:
    độ khó ~3, tập trung quanh 60-75%, vẫn có người đọc slide ≥30 phút. Không có
    dấu hiệu mẫu giờ nghỉ lệch hẳn so với người điền muộn hơn.""")

h("9 · BỐN Ô: MẤT TẬP TRUNG × CÓ ÔN LẠI  ← phân khúc cần sản phẩm nhất")
print("""  Trục dọc : tập trung trong buổi (≤60% = mất nhiều / >60% = nghe được)
  Trục ngang: thời gian tự đọc slide sau buổi (<30p = ít ôn / ≥30p = ôn thật)""")
o = {}
for r in R:
    key = ("mất" if r[4] <= 60 else "nghe được", "ít ôn" if r[3] == "<30p" else "ôn thật")
    o.setdefault(key, []).append(r[0])
print()
for tt in ("mất", "nghe được"):
    for on in ("ít ôn", "ôn thật"):
        g = o.get((tt, on), [])
        print(f"  tập trung {tt:9} × {on:7} : {len(g):2d}/{n} = {100*len(g)/n:4.1f}%")
mat_it = o.get(("mất", "ít ôn"), [])
print(f"""
  → Ô nguy hiểm nhất là **tập trung mất × ít ôn** ({len(mat_it)}/{n} = {100*len(mat_it)/n:.1f}%):
    nghe không vào mà cũng không đọc lại ⇒ nội dung buổi đó mất luôn. Đây là phân
    khúc recap phục vụ trực tiếp nhất — nó phải RẺ (≤15 phút), vì nhóm này đã cho
    thấy họ không bỏ ≥30 phút ra ôn.
    Tên: {', '.join(mat_it)}
  → Ô **mất × ôn thật** ({len(o.get(("mất","ôn thật"),[]))}/{n}) là nhóm đang TRẢ GIÁ bằng thời gian:
    họ bù bằng cách đọc lại slide ≥30 phút. Recap giúp nhóm này tiết kiệm, không
    phải giúp họ bắt đầu ôn.""")

h("10 · CHÂN DUNG NHÓM \"CHƯA CHẮC\" — người thử giá trị nhất cho CP5")
cc = [r for r in R if r[5] == "Chưa chắc"]
co = [r for r in R if r[5] == "Có"]
print(f"{'':24} {'Chưa chắc':>11} {'Có':>8}")
for nhan, f in (("n", len),
                ("độ khó (mean)", lambda g: st.mean(r[2] for r in g)),
                ("% tập trung (mean)", lambda g: st.mean(r[4] for r in g)),
                ("đọc slide ≥30p (%)", lambda g: 100 * sum(1 for r in g if r[3] != "<30p") / len(g))):
    v1, v2 = f(cc), f(co)
    print(f"  {nhan:22} {v1:11.1f} {v2:8.1f}" if isinstance(v1, float)
          else f"  {nhan:22} {v1:11d} {v2:8d}")
print(f"""
  → Nhóm "Chưa chắc" ({len(cc)} người) KHÔNG phải nhóm thấy nội dung dễ: độ khó
    trung bình xấp xỉ nhóm "Có", và họ tập trung CAO hơn + đọc slide nhiều hơn.
    Đọc ra: họ đang tự ôn được nên chưa thấy cần bot — chứ không phải họ không có
    pain. Đây đúng là người thử nên mời ở CP5: họ có tiêu chuẩn so sánh (cách ôn
    hiện tại của họ đang chạy tốt), nên feedback sẽ khắt khe chứ không phải lời khen.
    Tên: {', '.join(r[0] for r in cc)}""")

h("11 · TƯƠNG QUAN — độ khó có kéo thời gian ôn lên không?")
BUCKET_H = {"<30p": 15, "30p-1h": 45, "1h-2h": 90, "Hơn 2h": 150}   # phút, lấy trung điểm
for nhan, xs, ys in (("độ khó ↔ phút đọc slide", [r[2] for r in R], [BUCKET_H[r[3]] for r in R]),
                     ("độ khó ↔ % tập trung",    [r[2] for r in R], [r[4] for r in R]),
                     ("% tập trung ↔ phút đọc",  [r[4] for r in R], [BUCKET_H[r[3]] for r in R])):
    mx, my = st.mean(xs), st.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    r_ = cov / den if den else 0
    print(f"  {nhan:26} r = {r_:+.2f}")
print("""
  → n=29 nên đây là tín hiệu định hướng, KHÔNG phải kết luận thống kê (không tính
    p-value, không suy ra nhân quả).

  Điều đáng chú ý nhất là dấu của quan hệ thứ ba: **% tập trung ↔ thời gian đọc là
  CÙNG CHIỀU (r=+0.32), không phải ngược chiều.** Nếu học viên bù trừ — nghe không
  vào thì đọc lại nhiều hơn — thì dấu phải là ÂM. Ở đây người tập trung tốt lại
  cũng là người ôn nhiều, và ngược lại.

  ⇒ Khoảng cách KHÔNG tự thu hẹp, nó CỘNG DỒN. Nhóm mất tập trung phần lớn cũng là
    nhóm không ôn lại (khớp ô 27.6% ở mục 9). Hệ quả thiết kế: đừng trông vào việc
    học viên "cố hơn" để bù — recap phải rẻ đến mức nhóm này chịu dùng, chứ không
    phải hay đến mức họ chịu bỏ thêm thời gian.""")

h("12 · GIỚI HẠN CỦA VÒNG KHẢO SÁT NÀY — ghi để không tự lừa mình")
print("""  ① Q6 hỏi ý kiến về tính năng chưa tồn tại, KÈM mô tả sản phẩm ngay trong câu hỏi
     → 84% "Có" là con số được dự đoán trước bởi guide §1.3, KHÔNG chứng minh nhu cầu.
     Nhóm dùng nó đúng một việc: 0% trả lời "Không" ⇒ không ai phản đối hướng đi.
  ② Q3/Q4/Q5 là số hành vi tự khai → dùng được, và là phần có giá trị của vòng này.
  ③ Q5 là tự khai, không đo → có thể lệch cả hai chiều (khiêm tốn hoặc tự tin quá).
  ④ Không có câu nào hỏi "LẦN GẦN NHẤT bạn ôn lại một buổi — làm gì, mất bao lâu?"
     ⇒ chưa có số phút thật cho việc ôn lại, chưa đối chiếu được với mining B11 (85 phút).
  ⑤ Không có câu nào hỏi "bạn có đồng ý thử prototype không?" ⇒ 25 người này CHƯA
     phải willing user; vẫn phải đi xin riêng ≥3 người (spec §8).
  ⑥ Thu trong 15 phút giờ nghỉ, tự chọn tham gia → thiên lệch về người đang có mặt
     và chịu điền form.
  → Vòng 2 vá ①④⑤ bằng 3 câu hồi tưởng trong `survey-instrument.md`.""")
