"""Bộ tool của agent `/recap`.

Mỗi tool: schema JSON (đưa cho model) + hàm thực thi (dispatch). Description
viết PRESCRIPTIVE — nói rõ KHI NÀO gọi, không chỉ nó làm gì (điều này tăng
đáng kể tỉ lệ gọi đúng tool trên các model Opus gần đây).

6 tool deterministic + 1 tool AI (summarize_block = AI call 2 trong spec §4).
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
            "Tìm từ khoá trong CẢ transcript VÀ slide của một buổi (không phân biệt "
            "dấu). Trả mã đoạn [Txx-NNN] cho transcript và số trang cho slide. "
            "Dùng khi: học viên hỏi về một khái niệm và bạn chưa biết nó nằm ở đâu — "
            "LUÔN tìm trước khi kết luận 'buổi này không có'. Cả hai danh sách rỗng = "
            "khái niệm KHÔNG có trong buổi; khi đó tuyệt đối không tự giải thích từ "
            "kiến thức nền."
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
        "name": "read_slide",
        "description": (
            "Đọc NGUYÊN VĂN text của một trang slide (bản hackathon trong data pack, "
            "29 trang/buổi, có text layer đầy đủ). Dùng khi: học viên hỏi đích danh "
            "'slide/trang N', hoặc bạn cần đối chiếu điều giảng viên NÓI (transcript) "
            "với điều slide VIẾT. Trích dẫn dạng [slide tr.N] — luôn ghi rõ là trang "
            "của bản hackathon, vì số trang này KHÁC deck gốc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS},
                "page": {"type": "integer",
                         "description": "Số trang trong bản hackathon (1-29)"},
            },
            "required": ["session_id", "page"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_slides",
        "description": (
            "Liệt kê tiêu đề toàn bộ 29 trang slide của một buổi. Dùng khi: học viên "
            "muốn xem buổi học có những slide gì, hoặc bạn cần định vị nhanh một chủ "
            "đề nằm ở trang nào trước khi đọc sâu."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"session_id": {"type": "string", "enum": SESSION_IDS}},
            "required": ["session_id"],
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
            sid, q = args["session_id"], args["query"]
            t_hits = sources.search_transcript(sid, q)
            s_hits = sources.search_slides(sid, q)
            note = ""
            if not t_hits and not s_hits:
                key = q.strip().lower()
                for k, v in config.NGOAI_NGUON.items():
                    if k in key:
                        note = (f"KHÔNG có trong buổi này. Khái niệm thuộc {v} — "
                                "chỉ đúng chỗ đó, không tự giải thích.")
                        break
                else:
                    note = ("KHÔNG có trong transcript lẫn slide của buổi này — "
                            "không được tự giải thích từ kiến thức nền.")
            return json.dumps({"transcript": t_hits, "slide": s_hits,
                               "ghi_chu": note}, ensure_ascii=False)

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

        if name == "read_slide":
            sid = args["session_id"]
            slides = sources.load_slides(sid)
            if not slides:
                return json.dumps({"loi": "buổi này chưa có deck slide"},
                                  ensure_ascii=False)
            text = slides.get(args["page"])
            if text is None:
                return json.dumps(
                    {"loi": f"trang {args['page']} không có — deck có {len(slides)} trang"},
                    ensure_ascii=False)
            return json.dumps(
                {"deck": config.SESSIONS[sid]["deck_ten"], "trang": args["page"],
                 "tieu_de": sources.slide_title(text), "noi_dung": text,
                 "cach_trich_dan": f"[slide tr.{args['page']} · bản hackathon]"},
                ensure_ascii=False)

        if name == "list_slides":
            sid = args["session_id"]
            slides = sources.load_slides(sid)
            if not slides:
                return json.dumps({"loi": "buổi này chưa có deck slide"},
                                  ensure_ascii=False)
            return json.dumps(
                {"deck": config.SESSIONS[sid]["deck_ten"],
                 "trang": [{"trang": p, "tieu_de": sources.slide_title(tx)}
                           for p, tx in slides.items()]}, ensure_ascii=False)

        return json.dumps({"loi": f"tool không tồn tại: {name}"}, ensure_ascii=False)

    return dispatch
