"""Bộ tool của agent `/recap`.

Mỗi tool: schema JSON (đưa cho model) + hàm thực thi (dispatch). Description
viết PRESCRIPTIVE — nói rõ KHI NÀO gọi, không chỉ nó làm gì (điều này tăng
đáng kể tỉ lệ gọi đúng tool trên các model Opus gần đây).

5 tool deterministic + 1 tool AI (summarize_block = AI call 2 trong spec §4).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from . import config, sources

SESSION_IDS = list(config.SESSIONS)

TOOLS: list[dict] = [
    {
        "name": "list_blocks",
        "description": (
            "Liệt kê các block (phần) của một buổi học kèm dải mã đoạn và cờ "
            "non_core (chào lớp/bên lề — không phải nội dung học). "
            "Dùng khi: học viên hỏi buổi học gồm những gì, muốn recap toàn buổi, "
            "hoặc bạn cần định vị một chủ đề thuộc block nào trước khi đọc sâu."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS,
                               "description": "Buổi học cần liệt kê"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_transcript",
        "description": (
            "Đọc nguyên văn các đoạn transcript theo mã (vd T04-053) hoặc theo "
            "block_idx. Đây là NGUỒN SỰ THẬT duy nhất về lời giảng viên nói. "
            "Dùng khi: cần căn cứ để trả lời/tóm tắt — mọi ý trong câu trả lời "
            "phải trace được về đoạn đã đọc bằng tool này. Không bao giờ phát "
            "biểu nội dung bài học mà chưa đọc đoạn tương ứng."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS},
                "codes": {"type": "array", "items": {"type": "string"},
                          "description": "Danh sách mã đoạn, vd ['T04-053','T04-054']"},
                "block_idx": {"type": "integer",
                              "description": "Hoặc: đọc trọn một block theo số thứ tự"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_sources",
        "description": (
            "Tìm từ khoá trong transcript của một buổi (không phân biệt dấu), trả "
            "mã đoạn + trích đoạn ngắn. Dùng khi: học viên hỏi về một khái niệm và "
            "bạn chưa biết nó nằm ở đoạn nào — LUÔN tìm trước khi kết luận "
            "'buổi này không có'. Kết quả rỗng = khái niệm KHÔNG có trong buổi; "
            "khi đó tuyệt đối không tự giải thích từ kiến thức nền."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS},
                "query": {"type": "string", "description": "Từ khoá, vd 'mùa đông'"},
            },
            "required": ["session_id", "query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "summarize_block",
        "description": (
            "Tóm tắt MỘT block thành 4-6 gạch đầu dòng, mỗi gạch kèm mã đoạn "
            "[Txx-NNN], cộng dòng '🔑 Keyword' (3-5 thuật ngữ nguyên văn của "
            "giảng viên). Dùng khi: học viên xin tóm tắt/recap một phần hoặc cả "
            "buổi (gọi lần lượt cho từng block). Đừng tự tóm tắt bằng tay khi đã "
            "có tool này — nó áp đúng luật citation của spec."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS},
                "block_idx": {"type": "integer", "description": "Block cần tóm tắt"},
            },
            "required": ["session_id", "block_idx"],
            "additionalProperties": False,
        },
    },
    {
        "name": "peer_questions",
        "description": (
            "Thắc mắc THẬT của học viên trong lớp (từ chatlog VLearn ẩn danh) khớp "
            "một chủ đề. Chỉ trả cụm khi ≥2 học viên khác nhau cùng hỏi; output có "
            "số người + mã M, không bao giờ có danh tính. Dùng khi: học viên muốn "
            "biết 'lớp vướng gì ở phần này' hoặc bạn đang dựng mục 'Bạn học từng "
            "vướng gì ở đây' của recap."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Chủ đề, vd 'attention'"},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_slide",
        "description": (
            "Metadata một trang slide đã tách từ capture (đường dẫn PNG, cờ partial "
            "nếu slide bị cắt cụt). LƯU Ý: slide KHÔNG có text layer — tool này "
            "không trả chữ; nguồn text duy nhất là transcript. Dùng khi: học viên "
            "hỏi đích danh 'slide/trang N' hoặc cần đính kèm ảnh slide vào trả lời."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS},
                "page": {"type": "integer", "description": "Số trang (khớp 'Trang N' của VLearn)"},
            },
            "required": ["session_id", "page"],
            "additionalProperties": False,
        },
    },
]


# ── Thực thi ─────────────────────────────────────────────────────────────────

SUMMARIZE_SYSTEM = (
    "Bạn tóm tắt một phần bài giảng cho học viên ôn tập. Luật cứng:\n"
    "1. CHỈ dùng thông tin trong các đoạn được cung cấp — không thêm kiến thức ngoài.\n"
    "2. 4-6 gạch đầu dòng; mỗi gạch kết thúc bằng ≥1 mã đoạn dạng [Txx-NNN].\n"
    "3. Giữ nguyên ví dụ/ẩn dụ giảng viên đã dùng; không thay bằng thuật ngữ mới.\n"
    "4. Chỗ nào bản ghi ghi [không nghe rõ] thì ghi chú 'bản ghi mất tiếng', không đoán.\n"
    "5. Dòng cuối: '🔑 Keyword: ...' — 3-5 thuật ngữ xuất hiện NGUYÊN VĂN trong đoạn."
)


def make_dispatch(subcall: Callable[[str, str], str]) -> Callable[[str, dict], str]:
    """Tạo hàm dispatch. `subcall(system, user) -> str` là lời gọi AI phụ
    (client thật hoặc mock) — chỉ summarize_block dùng nó."""

    def dispatch(name: str, args: dict[str, Any]) -> str:
        if name == "list_blocks":
            tr = sources.load_transcript(args["session_id"])
            rows = [{"idx": b.idx, "tieu_de": b.title,
                     "dai_ma": f"{b.codes[0]}..{b.codes[-1]}" if b.codes else "",
                     "so_doan": len(b.codes), "non_core": b.non_core}
                    for b in tr.blocks]
            return json.dumps({"buoi": tr.ten, "blocks": rows}, ensure_ascii=False)

        if name == "read_transcript":
            tr = sources.load_transcript(args["session_id"])
            codes = args.get("codes")
            if not codes and args.get("block_idx") is not None:
                blk = tr.block_by_idx(args["block_idx"])
                if blk is None:
                    return json.dumps({"loi": f"không có block {args['block_idx']}"},
                                      ensure_ascii=False)
                codes = blk.codes
            out = [{"ma_doan": c, "noi_dung": tr.paragraphs.get(c, "(không có mã này)")}
                   for c in (codes or [])[:40]]
            return json.dumps(out, ensure_ascii=False)

        if name == "search_sources":
            hits = sources.search_transcript(args["session_id"], args["query"])
            note = ""
            if not hits:
                key = args["query"].strip().lower()
                for k, v in config.NGOAI_NGUON.items():
                    if k in key:
                        note = f"Khái niệm này thuộc {v} — không nằm trong buổi đang hỏi."
            return json.dumps({"ket_qua": hits, "ghi_chu": note}, ensure_ascii=False)

        if name == "summarize_block":
            tr = sources.load_transcript(args["session_id"])
            blk = tr.block_by_idx(args["block_idx"])
            if blk is None:
                return json.dumps({"loi": f"không có block {args['block_idx']}"},
                                  ensure_ascii=False)
            if blk.non_core:
                return json.dumps({"bo_qua": f"'{blk.title}' là phần chào lớp/bên lề "
                                             "— không tóm tắt, khai báo đã loại"},
                                  ensure_ascii=False)
            body = "\n\n".join(f"[{c}] {tr.paragraphs[c]}" for c in blk.codes)
            return subcall(SUMMARIZE_SYSTEM,
                           f"Block: {blk.title}\n\n{body}\n\nTóm tắt theo luật trên.")

        if name == "peer_questions":
            return json.dumps(sources.peer_questions(args["topic"]), ensure_ascii=False)

        if name == "get_slide":
            deck = config.SESSIONS[args["session_id"]].get("deck")
            if not deck:
                return json.dumps({"loi": "buổi này chưa có deck slide đã tách"},
                                  ensure_ascii=False)
            man = sources.slide_manifest(deck)
            rec = man.get(args["page"])
            if not rec:
                return json.dumps(
                    {"loi": f"trang {args['page']} không có trong capture "
                            f"(deck {deck} có {len(man)} trang)"}, ensure_ascii=False)
            return json.dumps({"deck": deck, "trang": rec["page"], "png": rec["png"],
                               "partial": rec.get("partial", False),
                               "luu_y": "slide là ảnh, không có text — căn cứ chữ "
                                        "lấy từ transcript"}, ensure_ascii=False)

        return json.dumps({"loi": f"tool không tồn tại: {name}"}, ensure_ascii=False)

    return dispatch
