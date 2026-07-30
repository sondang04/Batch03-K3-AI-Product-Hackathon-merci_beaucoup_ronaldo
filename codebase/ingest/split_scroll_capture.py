#!/usr/bin/env python3
"""
Cắt scroll-capture của VLearn reader thành TỪNG SLIDE RIÊNG.

Bài toán: bản capture cuộn là MỘT ảnh rất cao, bị chia thành N tile và mỗi tile
đặt lên một trang PDF. Ranh giới trang PDF **không** trùng ranh giới slide → slide
bị cắt rời ngang giữa. Không có text layer (0 ký tự) → pypdf không trích được chữ.

Cách làm (không cần OCR, không cần AI, deterministic):
  1. Lấy tile từ resources, **xếp theo thứ tự vẽ trong content stream** (không theo tên).
  2. Ghép logic thành một dải cao H = Σ chiều cao tile (không load hết vào RAM).
  3. Trong reader, mỗi slide là một **thẻ trắng trên nền xanh nhạt**; giữa hai thẻ là
     một dải nền thuần. Với mỗi hàng, đếm tỉ lệ pixel = màu nền trong cột nội dung
     → hàng "gap" là hàng có tỉ lệ cao. Run gap liên tiếp = khoảng giữa hai slide.
  4. Vùng giữa hai gap = một slide → crop xuyên tile → PNG.

Chạy:
  python3 codebase/ingest/split_scroll_capture.py \\
      --pdf ~/Downloads/screencapture-....pdf --deck day01_302 --expect 83 \\
      --out codebase/data/slides/day01_302/

⚠️  BẢO MẬT: ảnh slide mang **watermark chéo chứa email cá nhân** của người mở
reader, cộng nội dung bài giảng thuộc quy định bảo mật data pack. KHÔNG commit
thư mục --out, KHÔNG đăng ra ngoài, và khi đưa vào vision model thì chỉ đưa số
slide tối thiểu cần cho demo (guide §3.4).
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

import numpy as np
from PIL import Image
from pypdf import PdfReader

Image.MAX_IMAGE_PIXELS = None

BG_MAC_DINH = (240, 245, 249)   # nền xanh nhạt của reader, đo được từ capture thật
DUNG_SAI_MAU = 10               # sai số cho phép khi so màu nền
NGUONG_GAP = 0.70               # tỉ lệ pixel nền tối thiểu để coi hàng là "gap"
GAP_TOI_THIEU = 10              # run gap ngắn hơn thì bỏ (viền thẻ, đường kẻ)


def lay_tile_theo_thu_tu_ve(reader):
    """Trả [(tên, bytes)] theo đúng thứ tự slide dọc.

    Mỗi trang PDF vẽ đúng một tile; thứ tự trang = thứ tự dọc. Đọc content stream
    để biết trang nào vẽ tile nào — an toàn hơn sort theo tên I0..I16.
    """
    ten_theo_trang = []
    for page in reader.pages:
        data = page.get_contents().get_data().decode("latin-1", "replace")
        ve = re.findall(r"/(\w+)\s+Do\b", data)
        if ve:
            ten_theo_trang.append(ve[0])

    kho = {}
    for page in reader.pages:
        for im in page.images:
            kho.setdefault(im.name, im.data)

    # tên trong content stream là `/I0`, còn im.name là `I0.jpg` → so theo phần gốc
    goc = {os.path.splitext(n)[0]: n for n in kho}
    if ten_theo_trang and all(t in goc for t in ten_theo_trang):
        return [(goc[t], kho[goc[t]]) for t in ten_theo_trang]

    # fallback: sort theo số trong tên
    print("  ⚠️  không đọc được thứ tự từ content stream → sort theo tên", file=sys.stderr)
    def key(n):
        m = re.search(r"(\d+)", n)
        return int(m.group(1)) if m else 0
    return [(n, kho[n]) for n in sorted(kho, key=key)]


class DaiAnh:
    """Dải ảnh ghép từ các tile, crop xuyên tile mà không load hết vào RAM."""

    def __init__(self, duong_dan_tile):
        self.paths = duong_dan_tile
        self.cao = []
        for p in duong_dan_tile:
            with Image.open(p) as im:
                self.cao.append(im.height)
                self.rong = im.width
        self.moc = np.cumsum([0] + self.cao)       # moc[i] = y toàn cục đầu tile i
        self.H = int(self.moc[-1])
        self._cache = {}

    def tile(self, i):
        if i not in self._cache:
            if len(self._cache) > 3:
                self._cache.pop(next(iter(self._cache)))
            self._cache[i] = np.asarray(Image.open(self.paths[i]).convert("RGB"))
        return self._cache[i]

    def crop(self, y0, y1, x0, x1):
        """Ghép các phần tile nằm trong [y0,y1) → ndarray."""
        phan = []
        for i in range(len(self.paths)):
            a, b = int(self.moc[i]), int(self.moc[i + 1])
            if b <= y0 or a >= y1:
                continue
            phan.append(self.tile(i)[max(y0, a) - a: min(y1, b) - a, x0:x1])
        return np.vstack(phan) if phan else np.zeros((0, x1 - x0, 3), np.uint8)


def do_profile(dai, bg, x0=None, x1=None):
    """Trả (profile tỉ lệ pixel nền theo hàng, x0, x1 của cột nội dung)."""
    bg = np.array(bg, dtype=np.int16)

    if x0 is None:
        # cột nội dung = dải x mà màu nền xuất hiện đáng kể; đo trên tile giữa
        # (tile đầu có sidebar + panel tutor nên không đại diện)
        giua = dai.tile(len(dai.paths) // 2).astype(np.int16)
        cf = (np.abs(giua - bg).max(axis=2) <= DUNG_SAI_MAU).mean(axis=0)
        ins = np.where(cf > 0.05)[0]
        if len(ins) < 50:
            sys.exit("Không tìm được cột nội dung — kiểm tra lại --bg (màu nền).")
        x0, x1 = int(ins.min()), int(ins.max()) + 1

    lat = 400  # xử lý theo lát để không ngốn RAM
    prof = np.empty(dai.H, dtype=np.float32)
    for y in range(0, dai.H, lat):
        y2 = min(y + lat, dai.H)
        a = dai.crop(y, y2, x0, x1).astype(np.int16)
        prof[y:y2] = (np.abs(a - bg).max(axis=2) <= DUNG_SAI_MAU).mean(axis=1)
    return prof, x0, x1


def tim_gap(prof, nguong, toi_thieu):
    la_gap = prof > nguong
    runs, i, n = [], 0, len(la_gap)
    while i < n:
        if la_gap[i]:
            j = i
            while j < n and la_gap[j]:
                j += 1
            if j - i >= toi_thieu:
                runs.append((i, j - i))
            i = j
        else:
            i += 1
    return runs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--deck", required=True, help="mã deck, vd day01_302")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect", type=int, default=None,
                    help="số slide mong đợi (in trên header thẻ: 'Trang N / 83')")
    ap.add_argument("--first-page", type=int, default=1,
                    help="số trang của slide đầu tiên trong capture")
    ap.add_argument("--bg", default=",".join(map(str, BG_MAC_DINH)))
    ap.add_argument("--nguong", type=float, default=NGUONG_GAP)
    ap.add_argument("--x0", type=int, default=None)
    ap.add_argument("--x1", type=int, default=None)
    a = ap.parse_args()

    bg = tuple(int(v) for v in a.bg.split(","))
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_tiles")
    os.makedirs(tmp, exist_ok=True)

    print(f"[1/4] đọc {os.path.basename(a.pdf)}")
    reader = PdfReader(a.pdf)
    tiles = lay_tile_theo_thu_tu_ve(reader)
    paths = []
    for n, data in tiles:
        p = os.path.join(tmp, n if "." in n else n + ".jpg")
        open(p, "wb").write(data)
        paths.append(p)
    dai = DaiAnh(paths)
    print(f"      {len(paths)} tile · dải {dai.rong} x {dai.H} px")

    print(f"[2/4] đo profile nền (bg={bg})")
    prof, x0, x1 = do_profile(dai, bg, a.x0, a.x1)
    print(f"      cột nội dung x {x0}..{x1} (rộng {x1 - x0})")

    print(f"[3/4] tìm ranh giới slide (ngưỡng {a.nguong})")
    gaps = tim_gap(prof, a.nguong, GAP_TOI_THIEU)
    print(f"      {len(gaps)} dải gap")
    if len(gaps) < 2:
        sys.exit("Quá ít gap — thử hạ --nguong hoặc kiểm tra --bg.")

    # vùng slide = giữa hai gap liên tiếp; cắt ở GIỮA gap để giữ lại viền thẻ
    tam = [g[0] + g[1] // 2 for g in gaps]
    vung = [(tam[i], tam[i + 1]) for i in range(len(tam) - 1)]
    cao = np.array([b - t for t, b in vung])
    trung_vi = float(np.median(cao))

    # Slide ĐẦU chỉ có gap ở dưới, slide CUỐI chỉ có gap ở trên → cả hai bị lọt.
    # Bù bằng một pitch về mỗi phía, kẹp trong [0, H]; bộ lọc chiều cao bên dưới
    # vẫn loại nếu phần bù không phải slide thật (capture cắt cụt).
    # Chỉ bù nếu phần dư đủ cao để là slide thật (≥60% pitch). Một sliver mỏng ở
    # đầu dải là vùng toolbar/header của reader, KHÔNG phải slide — nếu đem số hoá
    # nó thì toàn bộ số trang phía sau lệch 1, và `--expect` sẽ pass giả.
    TOI_THIEU_LA_SLIDE = 0.60 * trung_vi
    dau = max(0, int(round(tam[0] - trung_vi)))
    if tam[0] - dau >= TOI_THIEU_LA_SLIDE:
        vung.insert(0, (dau, tam[0]))
    elif tam[0] > 0:
        print(f"      bỏ {tam[0] - dau}px đầu dải (<60% pitch → header reader, "
              f"không phải slide)")
    cuoi = min(dai.H, int(round(tam[-1] + trung_vi)))
    if cuoi - tam[-1] >= TOI_THIEU_LA_SLIDE:
        vung.append((tam[-1], cuoi))
    elif cuoi > tam[-1]:
        print(f"      bỏ {cuoi - tam[-1]}px cuối dải (<60% pitch)")
    cao = np.array([b - t for t, b in vung])

    # KHÔNG âm thầm bỏ vùng lệch — đánh dấu `partial` và báo ra. Bỏ im lặng đúng
    # là kiểu lỗi lớp ① mà spec §5 #5 cấm: thiếu slide thì recap phải nói, không ẩn.
    ok = [abs(h - trung_vi) <= 0.15 * trung_vi for h in cao]
    n_part = sum(1 for v in ok if not v)
    print(f"      pitch trung vị {trung_vi:.0f}px · {len(vung)} vùng "
          f"({n_part} vùng cắt cụt → đánh dấu partial, không bỏ)")

    print(f"[4/4] xuất PNG → {a.out}")
    man = []
    for k, ((t, b), tron_ven) in enumerate(zip(vung, ok)):
        so = a.first_page + k
        img = Image.fromarray(dai.crop(t, b, x0, x1))
        ten = f"page-{so:03d}.png"
        img.save(os.path.join(a.out, ten), optimize=True)
        r = {"deck": a.deck, "page": so, "kind": "image", "png": ten,
             "w": img.width, "h": img.height, "y0": t, "y1": b,
             "partial": not tron_ven}
        if not tron_ven:
            r["ghi_chu"] = (f"chiều cao {b - t}px lệch so với pitch {trung_vi:.0f}px — "
                            "slide có thể bị cắt cụt hoặc bị toolbar che, PHẢI kiểm tay")
        man.append(r)

    with open(os.path.join(a.out, "manifest.jsonl"), "w", encoding="utf-8") as f:
        for r in man:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n✓ {len(man)} slide → {a.out}")
    print(f"  chiều cao: min {cao.min()} · trung vị {trung_vi:.0f} · max {cao.max()}")
    hc = Counter(r["h"] for r in man)
    print(f"  {len(hc)} chiều cao khác nhau · hay gặp nhất {hc.most_common(3)}")
    part = [r for r in man if r["partial"]]
    if part:
        print(f"  ⚠️  {len(part)} slide cần kiểm tay: "
              + ", ".join(f"trang {r['page']} ({r['h']}px)" for r in part))

    if a.expect:
        if len(man) == a.expect:
            print(f"  ✓ KHỚP số slide mong đợi ({a.expect})")
        else:
            print(f"  ✗ LỆCH: ra {len(man)}, mong đợi {a.expect} "
                  f"(chênh {len(man) - a.expect:+d})")
            print("    → xem lại: capture có bị thiếu slide đầu/cuối không, "
                  "hoặc slide nào cao bất thường bị lọc oan (nới ngưỡng 25%)")
    print("\n⚠️  KHÔNG commit thư mục này: ảnh mang watermark email cá nhân "
          "+ nội dung bài giảng thuộc quy định bảo mật.")


if __name__ == "__main__":
    main()
