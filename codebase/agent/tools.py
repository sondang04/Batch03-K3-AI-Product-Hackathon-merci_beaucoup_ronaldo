"""Bộ tool của agent `/recap`.

Mỗi tool: schema JSON (đưa cho model) + hàm thực thi (dispatch). Description
viết PRESCRIPTIVE — nói rõ KHI NÀO gọi, không chỉ nó làm gì (điều này tăng
đáng kể tỉ lệ gọi đúng tool trên các model Opus gần đây).

6 tool deterministic + 1 tool AI (summarize_block = AI call 2 trong spec §4).
"""

from __future__ import annotations

import json
import re
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


def _clean_slide_title(text: str) -> str:
    """Làm sạch tiêu đề slide: tìm dòng có chữ đầu tiên dài hơn và không phải là header lặp."""
    title = sources.slide_title(text)
    if title == "(không có tiêu đề)" or len(title.strip()) < 3:
        for line in text.splitlines():
            line = line.strip()
            if len(line) >= 3 and not re.match(r"^\d+$", line) and not line.startswith("AI IN ACTION"):
                return line[:100]
    return title


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
            sid = args.get("session_id")
            if sid not in config.SESSIONS:
                valid_sessions = ", ".join(config.SESSIONS.keys())
                return json.dumps({"loi": f"Buổi học '{sid}' không hợp lệ. Các buổi học hỗ trợ gồm: {valid_sessions}."}, ensure_ascii=False)
            tr = sources.load_transcript(sid)
            rows = [{"idx": b.idx, "tieu_de": b.title,
                     "dai_ma": f"{b.codes[0]}..{b.codes[-1]}" if b.codes else "",
                     "so_doan": len(b.codes), "non_core": b.non_core}
                    for b in tr.blocks]
            return json.dumps({"buoi": tr.ten, "blocks": rows}, ensure_ascii=False)

        if name == "read_transcript":
            sid = args.get("session_id")
            if sid not in config.SESSIONS:
                valid_sessions = ", ".join(config.SESSIONS.keys())
                return json.dumps({"loi": f"Buổi học '{sid}' không hợp lệ. Các buổi học hỗ trợ gồm: {valid_sessions}."}, ensure_ascii=False)
            tr = sources.load_transcript(sid)
            codes = args.get("codes")
            if not codes and args.get("block_idx") is not None:
                try:
                    b_idx = int(args["block_idx"])
                except (ValueError, TypeError):
                    return json.dumps({"loi": f"Chỉ số block '{args.get('block_idx')}' phải là số nguyên."}, ensure_ascii=False)
                blk = tr.block_by_idx(b_idx)
                if blk is None:
                    return json.dumps({"loi": f"Không tìm thấy block {b_idx} trong buổi học này. Vui lòng kiểm tra lại chỉ số block."},
                                      ensure_ascii=False)
                codes = blk.codes
            
            out_lines = []
            for c in (codes or [])[:40]:
                noi_dung = tr.paragraphs.get(c, "").strip()
                if noi_dung:
                    out_lines.append(f"**[{c}]** {noi_dung}")
                else:
                    out_lines.append(f"**[{c}]** (không tìm thấy đoạn mã này trong transcript)")
            
            if not out_lines:
                return "Không tìm thấy đoạn hội thoại nào phù hợp với yêu cầu."
            return "\n\n".join(out_lines)

        if name == "search_sources":
            sid = args.get("session_id", "all")
            if sid != "all" and sid not in config.SESSIONS:
                valid_sessions = ", ".join(config.SESSIONS.keys())
                return json.dumps({"loi": f"Buổi học '{sid}' không hợp lệ. Các buổi học hỗ trợ gồm: {valid_sessions}."}, ensure_ascii=False)
            q = args.get("query", "")
            
            # 1. Kiểm tra khái niệm ngoài nguồn trước tiên để tránh việc khớp một phần gây nhiễu
            note = ""
            key = sources._norm(q)
            for k, v in config.NGOAI_NGUON.items():
                k_norm = sources._norm(k)
                if k_norm in key or key in k_norm:
                    note = (f"KHÔNG có trong buổi này. Khái niệm thuộc {v} — "
                            "chỉ đúng chỗ đó, không tự giải thích.")
                    return json.dumps({"transcript": [], "slide": [], "ghi_chu": note}, ensure_ascii=False)

            try:
                if sid == "all":
                    found = sources.search_all_sessions(q)
                    if found:
                        return json.dumps({"tim_xuyen_moi_buoi": found}, ensure_ascii=False)
                    t_hits = s_hits = []
                else:
                    t_hits = sources.search_transcript(sid, q)
                    s_hits = sources.search_slides(sid, q)
            except Exception as e:
                return json.dumps({"loi": f"Gặp lỗi khi tìm kiếm dữ liệu: {type(e).__name__}: {e}. Vui lòng thử lại với từ khóa khác."}, ensure_ascii=False)
                
            if not t_hits and not s_hits:
                note = ("KHÔNG có trong transcript lẫn slide của buổi này — "
                        "không được tự giải thích từ kiến thức nền.")
            return json.dumps({"transcript": t_hits, "slide": s_hits,
                               "ghi_chu": note}, ensure_ascii=False)

        if name == "summarize_block":
            sid = args.get("session_id")
            if sid not in config.SESSIONS:
                valid_sessions = ", ".join(config.SESSIONS.keys())
                return json.dumps({"loi": f"Buổi học '{sid}' không hợp lệ. Các buổi học hỗ trợ gồm: {valid_sessions}."}, ensure_ascii=False)
            tr = sources.load_transcript(sid)
            blk = None
            if args.get("title_query"):
                blk = sources.find_block(sid, args["title_query"])
                if blk is None:
                    return json.dumps(
                        {"loi": f"Không tìm thấy block khớp với tên '{args['title_query']}'.",
                         "goi_y": "Gọi list_blocks để xem danh sách block và chọn từ khóa chính xác."},
                        ensure_ascii=False)
            elif args.get("block_idx") is not None:
                try:
                    b_idx = int(args["block_idx"])
                except (ValueError, TypeError):
                    return json.dumps({"loi": f"Chỉ số block '{args.get('block_idx')}' phải là số nguyên."}, ensure_ascii=False)
                blk = tr.block_by_idx(b_idx)
                
            if blk is None:
                return json.dumps({"loi": "Cần cung cấp block_idx hoặc title_query hợp lệ."}, ensure_ascii=False)
            if blk.non_core:
                return json.dumps({"bo_qua": f"'{blk.title}' là phần chào lớp/bên lề "
                                             "— không tóm tắt, khai báo đã loại"},
                                  ensure_ascii=False)
            
            body = "\n\n".join(f"[{c}] {tr.paragraphs[c]}" for c in blk.codes)
            
            # Tìm kiếm thông tin slide liên quan dựa trên tiêu đề block để làm giàu ngữ cảnh
            slide_context = []
            try:
                slides = sources.load_slides(sid)
                if slides:
                    # Loại bỏ các từ nối tiếng Việt ngắn
                    stop_words = {"và", "của", "cho", "các", "nhưng", "để", "thì", "được", "là", "hay", "với", "tại", "trong", "ngoài", "phần", "mục"}
                    # Tách tiêu đề block thành các từ khóa
                    words = [w.strip().lower() for w in re.split(r"[,.&·\s\-–()]+", blk.title) if w.strip()]
                    words = [w for w in words if len(w) >= 3 and w not in stop_words]
                    
                    matching_pages = set()
                    for p, tx in slides.items():
                        tx_norm = sources._norm(tx)
                        for w in words:
                            w_norm = sources._norm(w)
                            if w_norm in tx_norm:
                                matching_pages.add(p)
                                break
                    
                    # Lấy tối đa 3 trang slide khớp nhất để tránh phình to context
                    for p in sorted(list(matching_pages))[:3]:
                        title = _clean_slide_title(slides[p])
                        slide_context.append(f"--- [Slide Trang {p} - {title}] ---\n{slides[p]}")
            except Exception:
                pass # Nếu lỗi đọc slide thì bỏ qua và chỉ tóm tắt theo transcript
            
            prompt_user = f"Block: {blk.title}\n\n[Transcript liên quan]\n{body}"
            if slide_context:
                slide_body = "\n\n".join(slide_context)
                prompt_user += f"\n\n[Slide liên quan để tham chiếu nội dung]\n{slide_body}"
            prompt_user += "\n\nTóm tắt theo luật trên."
            
            tom_tat = subcall(SUMMARIZE_SYSTEM, prompt_user)
            return json.dumps({"block_idx": blk.idx, "tieu_de": blk.title,
                               "dai_ma": f"{blk.codes[0]}..{blk.codes[-1]}" if blk.codes else "",
                               "tom_tat": tom_tat,
                               "nhac": "Nếu tiêu đề này KHÔNG khớp điều học viên hỏi, "
                                       "gọi lại với title_query đúng — đừng dùng nội "
                                       "dung này dưới nhãn khác."},
                              ensure_ascii=False)

        if name == "peer_questions":
            topic = args.get("topic", "").strip()
            if not topic:
                return json.dumps({"loi": "Chủ đề cần tìm kiếm thắc mắc không được trống."}, ensure_ascii=False)
            try:
                res = sources.peer_questions(topic)
                return json.dumps(res, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"loi": f"Lỗi khi truy xuất thắc mắc của lớp: {type(e).__name__}: {e}."}, ensure_ascii=False)

        if name == "read_slide":
            sid = args.get("session_id")
            if sid not in config.SESSIONS:
                valid_sessions = ", ".join(config.SESSIONS.keys())
                return json.dumps({"loi": f"Buổi học '{sid}' không hợp lệ. Các buổi học hỗ trợ gồm: {valid_sessions}."}, ensure_ascii=False)
            try:
                page = int(args["page"])
            except (ValueError, TypeError):
                return json.dumps({"loi": "Số trang slide cần xem phải là số nguyên."}, ensure_ascii=False)
                
            try:
                slides = sources.load_slides(sid)
            except Exception as e:
                return json.dumps({"loi": f"Không thể đọc tệp slide PDF của buổi này. Chi tiết: {type(e).__name__}."}, ensure_ascii=False)
                
            if not slides:
                return json.dumps({"loi": f"Buổi học '{sid}' hiện chưa có tệp deck slide trên hệ thống hoặc tệp slide bị hỏng."},
                                  ensure_ascii=False)
            text = slides.get(page)
            if text is None:
                return json.dumps(
                    {"loi": f"Trang slide {page} không tồn tại. Bản deck hackathon của buổi này chỉ có {len(slides)} trang (từ trang 1 đến {len(slides)}). Vui lòng đề xuất học viên dùng đúng số trang bản hackathon."},
                    ensure_ascii=False)
            return json.dumps(
                {"deck": config.SESSIONS[sid]["deck_ten"], "trang": page,
                 "tieu_de": _clean_slide_title(text), "noi_dung": text,
                 "cach_trich_dan": f"[slide tr.{page} · bản hackathon]"},
                ensure_ascii=False)

        if name == "list_slides":
            sid = args.get("session_id")
            if sid not in config.SESSIONS:
                valid_sessions = ", ".join(config.SESSIONS.keys())
                return json.dumps({"loi": f"Buổi học '{sid}' không hợp lệ. Các buổi học hỗ trợ gồm: {valid_sessions}."}, ensure_ascii=False)
            try:
                slides = sources.load_slides(sid)
            except Exception as e:
                return json.dumps({"loi": f"Không thể đọc tệp slide PDF của buổi này. Chi tiết: {type(e).__name__}."}, ensure_ascii=False)
                
            if not slides:
                return json.dumps({"loi": f"Buổi học '{sid}' hiện chưa có tệp deck slide trên hệ thống hoặc tệp slide bị hỏng."},
                                  ensure_ascii=False)
            return json.dumps(
                {"deck": config.SESSIONS[sid]["deck_ten"],
                 "trang": [{"trang": p, "tieu_de": _clean_slide_title(tx)}
                           for p, tx in slides.items()]}, ensure_ascii=False)

        return json.dumps({"loi": f"tool không tồn tại: {name}"}, ensure_ascii=False)

    return dispatch
