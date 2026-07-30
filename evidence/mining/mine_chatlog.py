#!/usr/bin/env python3
"""
Mining evidence cho spec.md §1-§2 — Discord Lecture Recap.

Chạy:  python3 evidence/mining/mine_chatlog.py > evidence/mining/mining-log.txt

Nguồn (KHÔNG commit vào repo — theo quy định bảo mật data pack):
  data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv   (2.522 dòng)
  data/vlearn-pack/transcript/transcript-0*-clean.md                   (6 buổi, ~700 đoạn)

Mọi con số trong spec.md §1 đều do script này in ra. Sửa quy tắc đếm ở
QUY_TAC_PHAN_LOAI bên dưới rồi chạy lại là kiểm chứng được.
"""

import glob
import os
import re
import sys
import unicodedata

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHATLOG = os.path.join(ROOT, "data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv")
TRANSCRIPT_GLOB = os.path.join(ROOT, "data/vlearn-pack/transcript/transcript-0*-clean.md")

# Tiền tố VLearn tự chèn khi học viên bôi đen một đoạn slide rồi hỏi.
PREFIX_SELECTION = re.compile(r"^\(Trang \d+, đoạn được chọn: .*?\)\s*", re.S)
PAGE = re.compile(r"\(Trang (\d+)")

# ── QUY TAC PHAN LOAI ─────────────────────────────────────────────────────────
# Xét theo THỨ TỰ, dừng ở nhãn khớp đầu tiên. Đọc tay 40 mẫu trước khi chốt
# các regex này (guide §1.3 bước 1). Nhãn A + B = "việc ôn lại / hiểu nội dung
# buổi học" — đúng job mà lát cắt của nhóm nhắm tới.
RAC = re.compile(
    r"^[\s\W]*(hello|hi+|xin chào|hey|ok|d|đ|test|\?+|\.+)[\s\W]*$", re.I)
PROBE = re.compile(
    r"password|api key|guardrail|jailbreak|bỏ qua.*quy tắc|base64|prompt injection"
    r"|kiểm tra bảo mật|admin|pretrain|fine tune|model của bạn|bạn dùng api", re.I)
LOGISTICS = re.compile(
    r"tải|download|link|slide.*ở đâu|ở đâu.*slide|deadline|nộp bài|canvas"
    r"|lịch học|hôm nay học gì|mấy giờ|điểm danh|zoom", re.I)
QUIZ = re.compile(r"^\s*(a|b|c|d)\s|đáp án|chọn đáp án|câu nào đúng|quiz|trắc nghiệm", re.I)
TOMTAT = re.compile(
    r"tóm tắt|tóm lại|summar|khái quát|ý chính|nội dung chính|các phần chính"
    r"|keyword cần nhớ", re.I)
KHAINIEM = re.compile(
    r"là gì|giải thích|nói rõ|làm rõ|khác nhau|khác gì|so sánh|ví dụ|vì sao|tại sao"
    r"|như thế nào|cách hoạt động|nghĩa là", re.I)
TUTOR_KHONG_CAN_CU = re.compile(
    r"không tìm thấy|không có thông tin|không đủ thông tin|không được cung cấp"
    r"|không thể truy (?:cập|xuất)|không hiển thị", re.I)

MIN_LEN = 12  # dưới ngưỡng này coi là tin cụt, không tính là câu hỏi


def classify(q: str) -> str:
    raw = q.strip()
    if len(raw) < MIN_LEN or RAC.match(raw):
        return "E · rác / tin cụt"
    if PROBE.search(raw):
        return "D · probe / jailbreak"
    if LOGISTICS.search(raw):
        return "C · logistics"
    if QUIZ.search(raw):
        return "F · dán quiz vào hỏi"
    if TOMTAT.search(raw):
        return "A · xin tóm tắt / ôn lại"
    if KHAINIEM.search(raw):
        return "B · hỏi khái niệm trong bài"
    return "G · khác"


def norm(x: str) -> str:
    x = unicodedata.normalize("NFC", x.lower())
    return " ".join(re.sub(r"[^\w\s]", " ", x).split())


def h(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    if not os.path.exists(CHATLOG):
        sys.exit(f"Không thấy data pack tại {CHATLOG} — data pack không được commit vào repo.")

    df = pd.read_csv(CHATLOG)
    df["date"] = pd.to_datetime(df.message_created_at, format="mixed", utc=True).dt.date
    stu = df[df.role == "student"].copy()
    tut = df[df.role == "tutor"].copy()
    stu["q"] = stu.content.str.replace(PREFIX_SELECTION, "", regex=True).fillna("")
    stu["page"] = stu.content.str.extract(PAGE, expand=False)

    h("0 · PHẠM VI DỮ LIỆU")
    print(f"dòng                 : {len(df):,}")
    print(f"học viên (mã ẩn danh): {df.user_id.nunique()}")
    print(f"hội thoại            : {df.conversation_id.nunique()}")
    print(f"turn (1 hỏi + 1 đáp) : {df.turn_id.nunique()}")
    print(f"khoảng thời gian     : {df.date.min()} → {df.date.max()}")
    print(f"conversation_mode    : {df.conversation_mode.value_counts().to_dict()}")

    h("1 · CÂU HỎI NEO VÀO TRANG TÀI LIỆU  (nền tảng cho việc gán thắc mắc vào block)")
    sel = stu.content.str.contains("đoạn được chọn", na=False)
    print(f"tin học viên có tiền tố '(Trang N, đoạn được chọn: …)': "
          f"{sel.sum()}/{len(stu)} = {100 * sel.mean():.1f}%")
    print(f"trích được số trang: {stu.page.notna().sum()}/{len(stu)}")

    h("2 · PHÂN LOẠI Ý ĐỊNH CỦA 1.261 CÂU HỎI  (quy tắc: xem QUY_TAC_PHAN_LOAI)")
    stu["cls"] = stu.q.map(classify)
    for label, n in stu.cls.value_counts().items():
        u = stu[stu.cls == label].user_id.nunique()
        print(f"  {label:26s} {n:5d}  {100 * n / len(stu):5.1f}%   {u:3d} học viên")
    ab = stu[stu.cls.str.startswith(("A", "B"))]
    print(f"\n  → A+B (ôn lại / hiểu nội dung buổi học): {len(ab)} câu "
          f"= {100 * len(ab) / len(stu):.1f}%  ·  {ab.user_id.nunique()}/{df.user_id.nunique()} "
          f"học viên = {100 * ab.user_id.nunique() / df.user_id.nunique():.1f}%")

    h("3 · TUTOR HIỆN TẠI LÀM ĐƯỢC ĐẾN ĐÂU VỚI YÊU CẦU TÓM TẮT")
    piv = df.pivot_table(index="turn_id", columns="role", values="content", aggfunc="first")
    meta = tut.set_index("turn_id")[["citations", "rating", "day_code"]]
    uid = stu.set_index("turn_id")[["user_id"]]
    trn = piv.join(meta).join(uid)
    trn["sq"] = trn.student.str.replace(PREFIX_SELECTION, "", regex=True).fillna("")

    ask = trn[trn.sq.str.contains(TOMTAT, na=False)]
    fail = ask.tutor.str.contains(TUTOR_KHONG_CAN_CU, na=False)
    nocit_ask = ask.citations.fillna("[]").isin(["[]", ""])
    print(f"turn có yêu cầu tóm tắt                    : {len(ask)}")
    print(f"  tutor trả 'không tìm thấy / không truy cập được': "
          f"{fail.sum()} = {100 * fail.mean():.1f}%")
    print(f"  tutor trả lời KHÔNG kèm citation          : "
          f"{nocit_ask.sum()} = {100 * nocit_ask.mean():.1f}%")

    nocit_all = tut.citations.fillna("[]").isin(["[]", ""])
    print(f"\ntrên TOÀN BỘ {len(tut)} câu trả lời tutor:")
    print(f"  không kèm citation                       : "
          f"{nocit_all.sum()} = {100 * nocit_all.mean():.1f}%")
    allfail = trn.tutor.str.contains(TUTOR_KHONG_CAN_CU, na=False)
    print(f"  nói không tìm thấy / không truy cập được : "
          f"{allfail.sum()} = {100 * allfail.mean():.1f}%")

    down = trn[trn.rating == "down"]
    dn = down.citations.fillna("[]").isin(["[]", ""])
    print(f"\nhọc viên chấm 👎: {len(down)} câu (👍 {(df.rating == 'up').sum()})")
    print(f"  trong đó không có citation: {dn.sum()} = {100 * dn.mean():.1f}%")

    h("4 · THẮC MẮC BỊ TRÙNG — 'BẠN HỌC ĐÃ VƯỚNG CHỖ NÀY'")
    sp = stu[stu.page.notna()].copy()
    grp = (sp.groupby(["day_code", "page"])
             .agg(n_cau=("message_id", "count"), n_hv=("user_id", "nunique"))
             .reset_index())
    tot = grp.n_cau.sum()
    print(f"cặp (tài liệu, trang) có câu hỏi           : {len(grp)}")
    for k in (2, 3, 5):
        sub = grp[grp.n_hv >= k]
        print(f"  cặp có ≥{k} học viên KHÁC NHAU cùng hỏi   : {len(sub):3d}  "
              f"→ chứa {sub.n_cau.sum():4d} câu = {100 * sub.n_cau.sum() / tot:.1f}% tổng câu hỏi")

    stu["nq"] = stu.q.map(norm)
    dup = (stu[stu.nq.str.len() >= MIN_LEN]
             .groupby("nq").agg(n=("message_id", "count"), u=("user_id", "nunique"))
             .reset_index())
    dm = dup[dup.u >= 2].sort_values(["u", "n"], ascending=False)
    print(f"\nnhóm câu hỏi TRÙNG NGUYÊN VĂN do ≥2 học viên khác nhau hỏi: "
          f"{len(dm)} nhóm / {dm.n.sum()} tin")
    for _, r in dm.head(8).iterrows():
        print(f"  {r.u:2d} học viên × {r.n:2d} lần: {r.nq[:70]}")

    h("5 · KHÁI NIỆM BỊ NHIỀU HỌC VIÊN HỎI LẠI")
    low = stu.q.str.lower()
    rows = []
    for kw in ["llm", "agent", "prompt", "react", "token", "context", "transformer",
               "attention", "deep learning", "rlhf", "mùa đông", "temperature"]:
        m = stu[low.str.contains(kw, na=False, regex=False)]
        if len(m) >= 3:
            rows.append((kw, len(m), m.user_id.nunique()))
    for kw, n, u in sorted(rows, key=lambda x: -x[2]):
        print(f"  {kw:14s} {n:4d} câu / {u:3d} học viên khác nhau")

    h("6 · TRANSCRIPT: CHI PHÍ ÔN LẠI MỘT BUỔI + ĐỘ MỊN BLOCK TỰ NHIÊN")
    # Ước lượng: đọc tiếng Việt ~200 từ/phút · nghe lại bản ghi ~130 từ/phút.
    noncore = re.compile(
        r"chào lớp|giới thiệu giảng viên|làm quen|bên lề|tương tác cuối|trò chuyện"
        r"|nghỉ|hành chính|phát thẻ|kết phần chia sẻ|K12|trao đổi về hệ thống", re.I)
    print(f"{'file':26s} {'block':>6s} {'đoạn':>5s} {'từ':>7s} {'phút đọc':>9s} "
          f"{'phút nghe':>10s} {'phi-ND':>7s}")
    T = dict(block=0, doan=0, tu=0, non=0)
    for f in sorted(glob.glob(TRANSCRIPT_GLOB)):
        txt = open(f, encoding="utf-8").read()
        secs = re.split(r"^## ", txt, flags=re.M)[1:]
        doan = len(re.findall(r"\*\*\[T\d\d-\d\d\d\]\*\*", txt))
        tu = sum(len(s.split()) for s in secs)
        non = sum(len(s.split()) for s in secs if noncore.search(s.split("\n")[0]))
        for k, v in zip(T, (len(secs), doan, tu, non)):
            T[k] += v
        print(f"{os.path.basename(f):26s} {len(secs):6d} {doan:5d} {tu:7d} "
              f"{tu / 200:9.0f} {tu / 130:10.0f} {100 * non / tu:6.1f}%")
    print(f"{'TỔNG 6 buổi':26s} {T['block']:6d} {T['doan']:5d} {T['tu']:7d} "
          f"{T['tu'] / 200:9.0f} {T['tu'] / 130:10.0f} {100 * T['non'] / T['tu']:6.1f}%")
    print(f"\ntrung bình: {T['block'] / 6:.0f} block/buổi · "
          f"{T['tu'] / T['doan']:.0f} từ/đoạn · {T['tu'] / 6 / 200:.0f} phút đọc/buổi")

    h("7 · GIỚI HẠN NGUỒN SỰ THẬT — khái niệm được hỏi nhưng KHÔNG có trong transcript")
    allt = " ".join(open(f, encoding="utf-8").read().lower()
                    for f in glob.glob(TRANSCRIPT_GLOB))
    for kw in ["react", "function calling", "mcp", "rag", "attention", "transformer"]:
        m = stu[low.str.contains(kw, na=False, regex=False)]
        print(f"  {kw:18s} chatlog: {len(m):3d} câu / {m.user_id.nunique():3d} HV   "
              f"| transcript: {allt.count(kw):3d} lần "
              f"{'← KHÔNG CÓ CĂN CỨ' if allt.count(kw) == 0 else ''}")

    h("8 · ĐỘ SÂU HỘI THOẠI — thắc mắc hỏi một lần rồi tắt")
    tpc = df.groupby("conversation_id").turn_id.nunique()
    print(f"turn/hội thoại: median {tpc.median():.0f} · mean {tpc.mean():.2f} · max {tpc.max()}")
    print(f"hội thoại chỉ có 1 turn : {(tpc == 1).sum()}/{len(tpc)} = {100 * (tpc == 1).mean():.1f}%")
    print(f"hội thoại ≤2 turn       : {(tpc <= 2).sum()}/{len(tpc)} = {100 * (tpc <= 2).mean():.1f}%")


if __name__ == "__main__":
    main()
