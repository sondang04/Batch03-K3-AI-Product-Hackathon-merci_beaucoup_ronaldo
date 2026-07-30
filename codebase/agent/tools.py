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
            "Tìm từ khoá trong CẢ transcript VÀ slide (không phân biệt dấu, khớp "
            "theo token nên không cần đúng nguyên cụm). Trả mã đoạn [Txx-NNN] cho "
            "transcript và số trang cho slide. "
            "Dùng khi: học viên hỏi về một khái niệm và bạn chưa biết nó nằm ở đâu — "
            "LUÔN tìm trước khi kết luận 'không có'. "
            "**Nếu câu hỏi KHÔNG nêu rõ buổi nào, đặt session_id='all' để quét mọi "
            "buổi — TUYỆT ĐỐI không tự đoán một buổi rồi kết luận 'không có'.** "
            "Kết quả rỗng ở mọi buổi = khái niệm thật sự không có; khi đó không được "
            "tự giải thích từ kiến thức nền."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS + ["all"],
                               "description": "Buổi cụ thể, hoặc 'all' khi câu hỏi "
                                              "không nêu buổi nào"},
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
            "có tool này — nó áp đúng luật citation của spec. "
            "**KHÔNG đoán block_idx.** Hoặc gọi `list_blocks` trước, hoặc truyền "
            "`title_query` để tool tự tìm đúng block. Kết quả luôn kèm `tieu_de` — "
            "PHẢI đối chiếu tiêu đề đó với điều học viên hỏi; nếu lệch thì gọi lại, "
            "đừng gán nhãn tiêu đề học viên hỏi lên nội dung block khác."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "enum": SESSION_IDS},
                "block_idx": {"type": "integer",
                              "description": "Số block (dùng khi đã biết chắc từ list_blocks)"},
                "title_query": {"type": "string",
                                "description": "HOẶC tên/từ khoá của block, vd 'attention "
                                               "multi-head' — an toàn hơn đoán số"},
            },
            "required": ["session_id"],
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
            sid, q = args.get("session_id", "all"), args["query"]
            if sid == "all":
                found = sources.search_all_sessions(q)
                if found:
                    return json.dumps({"tim_xuyen_moi_buoi": found}, ensure_ascii=False)
                t_hits = s_hits = []
            else:
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
            blk = None
            if args.get("title_query"):                     # ưu tiên tìm theo tên
                blk = sources.find_block(args["session_id"], args["title_query"])
                if blk is None:
                    return json.dumps(
                        {"loi": f"không tìm thấy block khớp '{args['title_query']}'",
                         "goi_y": "gọi list_blocks để xem danh sách block"},
                        ensure_ascii=False)
            elif args.get("block_idx") is not None:
                blk = tr.block_by_idx(args["block_idx"])
            if blk is None:
                return json.dumps({"loi": "cần block_idx hoặc title_query"},
                                  ensure_ascii=False)
            if blk.non_core:
                return json.dumps({"bo_qua": f"'{blk.title}' là phần chào lớp/bên lề "
                                             "— không tóm tắt, khai báo đã loại"},
                                  ensure_ascii=False)
            body = "\n\n".join(f"[{c}] {tr.paragraphs[c]}" for c in blk.codes)
            tom_tat = subcall(SUMMARIZE_SYSTEM,
                              f"Block: {blk.title}\n\n{body}\n\nTóm tắt theo luật trên.")
            # Echo block_idx + tieu_de để model TỰ ĐỐI CHIẾU đã tóm tắt đúng block
            # chưa (bug 30/07: model đoán index sai rồi dán nhãn tiêu đề học viên hỏi
            # lên nội dung block khác — không có cách nào tự phát hiện).
            return json.dumps({"block_idx": blk.idx, "tieu_de": blk.title,
                               "dai_ma": f"{blk.codes[0]}..{blk.codes[-1]}" if blk.codes else "",
                               "tom_tat": tom_tat,
                               "nhac": "Nếu tiêu đề này KHÔNG khớp điều học viên hỏi, "
                                       "gọi lại với title_query đúng — đừng dùng nội "
                                       "dung này dưới nhãn khác."},
                              ensure_ascii=False)

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
