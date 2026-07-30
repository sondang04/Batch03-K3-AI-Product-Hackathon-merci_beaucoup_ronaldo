#!/usr/bin/env python3
"""
Trích slide PDF → text neo theo TRANG, cho AI call 1/2 của `/recap`.

Hai chế độ:

  # 1. Trích: PDF → JSONL 1 record/trang + báo trang nào cần PNG bổ sung
  python3 codebase/ingest/extract_slides.py extract \\
      --pdf slides/day01-slide-blue-v1.pdf --deck day01-blue --out codebase/data/slides/

  # 2. Verify số trang khớp VLearn — CHẠY TRƯỚC KHI TIN BẤT KỲ `[slide tr.N]` NÀO
  python3 codebase/ingest/extract_slides.py verify \\
      --deck-jsonl codebase/data/slides/day01-blue.jsonl \\
      --day-code Lecture_material_ms2044ey_k6uor3

Vì sao verify là bước bắt buộc: 99,3% câu hỏi trong chatlog neo vào `(Trang N, …)`.
Nếu PDF export lệch 1 trang (thêm/bớt trang bìa) thì MỌI citation `[slide tr.N]`
trong recap đều sai — và sai một cách nghe rất hợp lý, không ai phát hiện.
Chiều C1 của quality bar sẽ fail toàn bộ. Bằng chứng chuyện này có thật:
`[T0229]` `[T0214]` `[T0157]`👎 — tutor hiện tại đã fail vì lệch dải trang.

Chỉ cần `pypdf` (đã có). Không gọi AI, không OCR → deterministic, 20ms/trang.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

from pypdf import PdfReader

# Ngưỡng phân loại trang — đọc tay vài deck rồi chỉnh nếu cần
NGUONG_TEXT = 120    # ≥ ngưỡng này: trang có nội dung chữ dùng được
NGUONG_SPARSE = 30   # trong khoảng: trang thưa chữ (title slide, 1 dòng)
# < NGUONG_SPARSE: coi là trang biểu đồ/ảnh → cần PNG để đọc bằng vision


def norm(s: str) -> str:
    """Chuẩn hoá để so khớp: NFC, lowercase, gộp khoảng trắng, bỏ dấu câu."""
    s = unicodedata.normalize("NFC", s.lower())
    return " ".join(re.sub(r"[^\w\s]", " ", s).split())


def phan_loai(n_chars: int) -> str:
    if n_chars >= NGUONG_TEXT:
        return "text"
    if n_chars >= NGUONG_SPARSE:
        return "sparse"
    return "diagram"


def doan_tieu_de(text: str) -> str:
    """Tiêu đề slide = dòng không rỗng đầu tiên, cắt 90 ký tự.
    Dùng làm gợi ý tiêu đề block cho AI call 1."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 3:
            return line[:90]
    return ""


def cmd_extract(args):
    reader = PdfReader(args.pdf)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"{args.deck}.jsonl")

    recs = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        try:
            n_img = len(page.images)
        except Exception:
            n_img = 0
        recs.append({
            "deck": args.deck,
            "page": i,                      # = "Trang N" của VLearn (phải verify!)
            "kind": phan_loai(len(text.strip())),
            "title": doan_tieu_de(text),
            "n_chars": len(text.strip()),
            "n_words": len(text.split()),
            "n_embedded_images": n_img,
            "text": text,
        })

    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(recs)
    by = {k: sum(1 for r in recs if r["kind"] == k) for k in ("text", "sparse", "diagram")}
    print(f"✓ {path}")
    print(f"  {n} trang · text {by['text']} · sparse {by['sparse']} · diagram {by['diagram']}")
    print(f"  trung bình {sum(r['n_chars'] for r in recs) // max(n, 1)} ký tự/trang")

    can_png = [r for r in recs if r["kind"] == "diagram"]
    if can_png:
        # Trang không có text layer: hoặc là slide vẽ bằng shape gốc, hoặc ảnh nhúng.
        # pypdf lấy được ảnh nhúng, nhưng KHÔNG rasterize được shape gốc
        # (cần pymupdf/poppler — môi trường này không cài được).
        co_anh = [r["page"] for r in can_png if r["n_embedded_images"] > 0]
        khong = [r["page"] for r in can_png if r["n_embedded_images"] == 0]
        print(f"\n⚠️  {len(can_png)} trang KHÔNG có text layer — recap sẽ mù ở các trang này:")
        if co_anh:
            print(f"     có ảnh nhúng (lấy được bằng pypdf): {co_anh}")
        if khong:
            print(f"     KHÔNG có ảnh nhúng → **cần export PNG thủ công**: {khong}")
        print("     → các trang này phải mang badge ⚠️ trong recap, không được im lặng bỏ (spec §5 #3)")
    else:
        print("\n✓ mọi trang đều có text layer — không cần PNG bổ sung")
    return 0


def cmd_verify(args):
    """So đoạn text học viên đã bôi đen trong chatlog với text của trang tương ứng."""
    import pandas as pd

    recs = [json.loads(l) for l in open(args.deck_jsonl, encoding="utf-8")]
    trang = {r["page"]: norm(r["text"]) for r in recs}

    df = pd.read_csv(args.chatlog)
    s = df[df.role == "student"]
    if args.day_code:
        s = s[s.day_code == args.day_code]
    ex = s.content.astype(str).str.extract(
        r'\(Trang (\d+), đoạn được chọn: "(.{25,200}?)"', flags=re.S)
    cases = [(int(p), sel, mid) for p, sel, mid
             in zip(ex[0], ex[1], s.message_id) if isinstance(sel, str) and p == p]

    if not cases:
        print("Không có case nào có cả số trang + đoạn bôi đen. Không verify được.")
        return 1

    khop = lech = thieu = 0
    bao_cao = []
    for pg, sel, mid in cases:
        needle = norm(sel)[:60]
        if len(needle) < 20:
            continue
        if pg not in trang:
            thieu += 1
            bao_cao.append(("NGOÀI DẢI", mid, pg, None, sel))
        elif needle in trang[pg]:
            khop += 1
        else:
            # tìm xem đoạn đó nằm ở trang nào khác → suy ra độ lệch
            thay = [p for p, t in trang.items() if needle in t]
            lech += 1
            bao_cao.append(("LỆCH", mid, pg, thay, sel))

    tong = khop + lech + thieu
    print(f"=== VERIFY SỐ TRANG · deck={recs[0]['deck']} · {tong} case ===")
    print(f"  khớp đúng trang : {khop}/{tong} = {100 * khop / tong:.1f}%")
    print(f"  lệch trang      : {lech}/{tong}")
    print(f"  trang ngoài dải : {thieu}/{tong}")

    offsets = [t[0] - c[2] for c in bao_cao if c[0] == "LỆCH" and c[3] for t in [c[3]]]
    if offsets:
        from collections import Counter
        print(f"\n  độ lệch hay gặp nhất: {Counter(offsets).most_common(3)}")
        print("  → nếu độ lệch là một hằng số, sửa bằng cách cộng offset vào 'page' khi trích")

    for kind, mid, pg, thay, sel in bao_cao[:10]:
        print(f'\n  [{kind}] {mid} · chatlog nói Trang {pg}'
              + (f' · text thực ở trang {thay}' if thay else ''))
        print(f'      "{" ".join(sel.split())[:90]}"')

    if khop / tong >= 0.9:
        print(f"\n✓ ĐẠT — số trang khớp VLearn, `[slide tr.N]` dùng được")
        return 0
    print(f"\n✗ CHƯA ĐẠT — KHÔNG dùng `[slide tr.N]` làm citation cho tới khi sửa xong offset")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="PDF → JSONL neo theo trang")
    e.add_argument("--pdf", required=True)
    e.add_argument("--deck", required=True, help="mã deck, vd day01-blue")
    e.add_argument("--out", default="codebase/data/slides/")

    v = sub.add_parser("verify", help="verify số trang khớp VLearn")
    v.add_argument("--deck-jsonl", required=True)
    v.add_argument("--day-code", default=None, help="lọc theo day_code trong chatlog")
    v.add_argument("--chatlog",
                   default="data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv")

    args = ap.parse_args()
    sys.exit(cmd_extract(args) if args.cmd == "extract" else cmd_verify(args))


if __name__ == "__main__":
    main()
