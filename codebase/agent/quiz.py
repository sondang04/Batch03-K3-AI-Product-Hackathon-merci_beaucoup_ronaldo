"""Pipeline `/quiz` — sinh quiz từ recap đã có (phương án A).

TỪ RECAP ĐÃ CÓ → sinh quiz kiểm tra hiểu
- Dùng lại nội dung block đã tóm tắt với citation
- Quiz luôn kèm nguồn để học viên tự kiểm tra
- Chỉ sinh từ nội dung có citation → giảm cost-of-error

Cấu trúc quiz (6 câu):
  ├── 3 câu Recall (fact-based, từ ý chính block)
  ├── 2 câu Keyword (từ dòng 🔑 Keyword)
  └── 1 câu Application (từ thắc mắc thật của lớp)

Kết quả cache xuống đĩa để demo không phải chờ và để chạy lại rẻ.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict

from . import config, sources


# Quiz settings
CACHE_DIR = config.REPO / "codebase" / "data" / "quiz-cache"
CAU_TOI_DA = 6              # tổng số câu hỏi/quiz
RECALL_TOI_DA = 3           # câu recall
KEYWORD_TOI_DA = 2          # câu keyword
APPLICATION_TOI_DA = 1      # câu application


# ── AI call: sinh câu hỏi quiz từ nội dung recap ───────────────────────────────

QUIZ_SYSTEM = (
    "Bạn sinh câu hỏi quiz TRẮC NGHIỆM từ nội dung bài giảng đã tóm tắt.\n"
    "Luật BẮT BUỘC:\n"
    "1. Câu hỏi phải kiểm tra HIỂU, không phải HỌC THUỘC.\n"
    "2. Mỗi câu có ĐÚNG 4 lựa chọn A/B/C/D, chỉ có 1 đáp án đúng.\n"
    "3. Đáp án đúng phải có căn cứ trong nội dung — KHÔNG bịa.\n"
    "4. Các lựa chọn sai (distractor) phải hợp lý, dễ gây nhầm lẫn — không quá lố bịch.\n"
    "5. Mỗi câu kèm GIẢI THÍCH ngắn tại sao đáp án đó đúng (1-2 câu).\n"
    "6. Đánh dấu loại: [RECALL] | [KEYWORD] | [APPLICATION]\n"
    "7. Câu [APPLICATION] dựa trên thắc mắc THẬT của học viên (nếu có).\n"
    '\nTrả DUY NHẤT JSON: {"cau_hoi":[{"loai":"RECALL|KEYWORD|APPLICATION",'
    '"cau":"...","lua_chon":["A. ...","B. ...","C. ...","D. ..."],'
    '"dap_an_dung":0,"dap_an_text":"...","giai_thich":"...","nguon":"[Txx-NNN]"}]}\n'
    "Trong đó dap_an_dung là INDEX 0-3 (0=A, 1=B, 2=C, 3=D),"
    "dap_an_text là nội dung đáp án đúng (copy từ lua_chon[dap_an_dung])"
)


def _goi_json(client, system: str, user: str, fallback):
    """Gọi AI và parse JSON, chịu được ```json fence. Lỗi thì trả fallback."""
    raw = client.subcall(system, user)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return fallback, f"không tìm thấy JSON trong output ({len(raw)} ký tự)"
    try:
        return json.loads(m.group(0)), None
    except json.JSONDecodeError as e:
        return fallback, f"JSON lỗi: {e}"


def _parse_cau_hoi(raw_text: str) -> list[dict]:
    """Parse câu hỏi trắc nghiệm từ text thuần (khi JSON parse thất bại)."""
    cau_hoi = []
    current = None
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if "[RECALL]" in line.upper():
            current = {"loai": "RECALL", "cau": line, "lua_chon": [], "dap_an_dung": 0, "dap_an_text": "", "giai_thich": "", "nguon": ""}
        elif "[KEYWORD]" in line.upper():
            current = {"loai": "KEYWORD", "cau": line, "lua_chon": [], "dap_an_dung": 0, "dap_an_text": "", "giai_thich": "", "nguon": ""}
        elif "[APPLICATION]" in line.upper():
            current = {"loai": "APPLICATION", "cau": line, "lua_chon": [], "dap_an_dung": 0, "dap_an_text": "", "giai_thich": "", "nguon": ""}
        elif current:
            ul = line.upper()
            if ul.startswith(("A.", "B.", "C.", "D.", "A)", "B)", "C)", "D)")):
                current["lua_chon"].append(line)
            elif not current["dap_an_text"]:
                current["dap_an_text"] = line
            elif not current["giai_thich"]:
                current["giai_thich"] = line
            elif not current["nguon"]:
                current["nguon"] = line
    if current and len(current["lua_chon"]) == 4:
        cau_hoi.append(current)
    return cau_hoi


def _sinh_cau_hoi(client, blocks_data: list[dict], peer_data: dict | None = None) -> tuple[list[dict], str | None]:
    """Sinh câu hỏi quiz từ nội dung các block."""
    # Chuẩn bị context từ blocks
    blocks_context = []
    for b in blocks_data:
        blocks_context.append(
            f"Block {b['idx']}: {b['tieu_de']}\n"
            f"Nội dung tóm tắt:\n{b['tom_tat']}\n"
            f"Mã đoạn: [{b['ma_dau']}]..[{b['ma_cuoi']}]"
        )
    
    context = "\n\n---\n\n".join(blocks_context)
    
    # Thêm thắc mắc thật của lớp nếu có
    peer_context = ""
    if peer_data and peer_data.get("cum"):
        peer_context = "\n\nThắc mắc THẬT của học viên trong lớp:\n"
        for c in peer_data.get("cum", [])[:3]:
            peer_context += f"- {c.get('cau_hoi', '')} [{c.get('ma', '')}]\n"
    
    user_prompt = (
        f"Sinh quiz kiểm tra hiểu từ nội dung bài giảng sau:\n\n"
        f"{context}"
        f"{peer_context}\n\n"
        f"Yêu cầu:\n"
        f"- Tạo tối đa {CAU_TOI_DA} câu hỏi\n"
        f"- Tối đa {RECALL_TOI_DA} câu [RECALL] (dựa trên ý chính block)\n"
        f"- Tối đa {KEYWORD_TOI_DA} câu [KEYWORD] (dựa trên thuật ngữ giảng viên)\n"
        f"- Tối đa {APPLICATION_TOI_DA} câu [APPLICATION] (dựa trên thắc mắc thật)\n"
        f"- Mỗi câu phải có đáp án và giải thích\n"
        f"- Luôn kèm citation (mã đoạn hoặc slide)\n"
    )
    
    fallback = {"cau_hoi": []}
    data, err = _goi_json(client, QUIZ_SYSTEM, user_prompt, fallback)
    
    if err or not data.get("cau_hoi"):
        # Thử parse text thuần nếu JSON fail
        parsed = _parse_cau_hoi(client.subcall(QUIZ_SYSTEM, user_prompt))
        if parsed:
            return parsed, None
        return [], err
    
    return data.get("cau_hoi", []), None


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class Question:
    """Một câu hỏi quiz trắc nghiệm 4 lựa chọn A/B/C/D."""
    loai: str                              # RECALL | KEYWORD | APPLICATION
    cau: str                                # Câu hỏi
    lua_chon: list[str] = field(default_factory=list)  # ["A. ...", "B. ...", "C. ...", "D. ..."]
    dap_an_dung: int = 0                    # index 0-3
    dap_an_text: str = ""                   # Nội dung đáp án đúng (hiển thị tóm tắt)
    giai_thich: str = ""
    nguon: str = ""


@dataclass
class Quiz:
    """Quiz cho một buổi học."""
    session_id: str
    buoi: str
    cau_hoi: list[Question]
    muc_da_bo: list[str]   # block không có nội dung để sinh quiz
    so_recall: int = 0
    so_keyword: int = 0
    so_application: int = 0
    n_ai_calls: int = 0
    giay: float = 0.0

    @property
    def tong_cau(self) -> int:
        return len(self.cau_hoi)

    @property
    def trac_nghiem_text(self) -> str:
        """Render quiz dạng câu hỏi trắc nghiệm cho Discord."""
        if not self.cau_hoi:
            return "⚠️ Không có đủ nội dung để sinh quiz cho buổi này."
        
        out = [
            f"**📝 Quiz — {self.buoi}**\n"
            f"Self-test kiểm tra hiểu · {self.tong_cau} câu\n"
            f"_Quiz không thay recap — kiểm tra với bản ghi nếu cần._\n"
        ]
        
        for i, q in enumerate(self.cau_hoi, 1):
            loai_icon = {"RECALL": "📖", "KEYWORD": "🔑", "APPLICATION": "💬"}.get(q.loai, "❓")
            chu_thich = {0: "A", 1: "B", 2: "C", 3: "D"}.get(q.dap_an_dung, "?")
            out.append(
                f"\n**Câu {i}.** [{q.loai}] {loai_icon}\n"
                f"{q.cau}\n"
                f"📌 Đáp án ({chu_thich}): {q.dap_an_text}\n"
                f"💡 Giải thích: {q.giai_thich}\n"
                f"📎 Nguồn: {q.nguon}"
            )
        
        # Thống kê
        stats = f"\n📊 Thống kê: {self.so_recall} recall · {self.so_keyword} keyword · {self.so_application} application"
        out.append(stats)
        return "\n".join(out)


# ── Build quiz ────────────────────────────────────────────────────────────────

def build_quiz(session_id: str, client, dung_cache: bool = True) -> Quiz:
    """Build quiz từ recap đã có cho một buổi học."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"quiz-{session_id}-{client.model}.json"
    
    # Đọc recap cache nếu có
    recap_cache = config.REPO / "codebase" / "data" / "recap-cache" / f"{session_id}-{client.model}.json"
    
    t0 = time.time()
    n_ai = 0
    cau_hoi: list[Question] = []
    muc_da_bo: list[str] = []
    
    # Đọc recap từ cache hoặc build mới
    if recap_cache.exists() and dung_cache:
        recap_data = json.loads(recap_cache.read_text(encoding="utf-8"))
        blocks_data = recap_data.get("blocks", [])
        muc_da_bo = recap_data.get("muc_da_bo", [])
    else:
        # Import và gọi recap nếu chưa có cache
        from .recap import build_recap as _build_recap
        recap = _build_recap(session_id, client, dung_cache=True)
        blocks_data = [asdict(b) for b in recap.blocks]
        muc_da_bo = recap.muc_da_bo
    
    # Lấy thắc mắc thật của lớp (từ peer_questions tool)
    peer_data = sources.peer_questions("buổi học này", limit=10)
    
    # Sinh câu hỏi
    raw_cau_hoi, err = _sinh_cau_hoi(client, blocks_data, peer_data)
    n_ai += 1
    
    if err:
        cau_hoi = []
    else:
        for q in raw_cau_hoi[:CAU_TOI_DA]:
            lc = q.get("lua_chon", [])
            lc_chuan: list[str] = []
            for i, opt in enumerate(lc[:4]):
                opt = str(opt).strip()
                if not opt:
                    continue
                # Bỏ mọi prefix A./A)/1./-/<space> để giữ text thuần — bot.py sẽ tự thêm prefix khi hiển thị
                opt = re.sub(r"^\s*[\(\[]?[A-Da-d1-4][\.\)\]\-\s]+", "", opt).strip()
                if not opt:
                    continue
                lc_chuan.append(opt)
            # Pad đủ 4 lựa chọn
            while len(lc_chuan) < 4:
                lc_chuan.append("(thiếu)")
            dap_an_dung = int(q.get("dap_an_dung", 0))
            if not (0 <= dap_an_dung <= 3):
                dap_an_dung = 0
            cau_hoi.append(Question(
                loai=q.get("loai", "RECALL"),
                cau=q.get("cau", ""),
                lua_chon=lc_chuan,
                dap_an_dung=dap_an_dung,
                dap_an_text=q.get("dap_an_text", "") or (lc_chuan[dap_an_dung] if 0 <= dap_an_dung < len(lc_chuan) else ""),
                giai_thich=q.get("giai_thich", ""),
                nguon=q.get("nguon", "")
            ))
    
    # Đếm theo loại
    so_recall = sum(1 for q in cau_hoi if q.loai == "RECALL")
    so_keyword = sum(1 for q in cau_hoi if q.loai == "KEYWORD")
    so_application = sum(1 for q in cau_hoi if q.loai == "APPLICATION")
    
    tr = sources.load_transcript(session_id)
    
    quiz = Quiz(
        session_id=session_id,
        buoi=tr.ten,
        cau_hoi=cau_hoi,
        muc_da_bo=muc_da_bo,
        so_recall=so_recall,
        so_keyword=so_keyword,
        so_application=so_application,
        n_ai_calls=n_ai,
        giay=round(time.time() - t0, 1)
    )
    
    # Cache quiz
    d = {
        "session_id": quiz.session_id,
        "buoi": quiz.buoi,
        "cau_hoi": [asdict(q) for q in quiz.cau_hoi],
        "muc_da_bo": quiz.muc_da_bo,
        "so_recall": quiz.so_recall,
        "so_keyword": quiz.so_keyword,
        "so_application": quiz.so_application,
        "n_ai_calls": quiz.n_ai_calls,
        "giay": quiz.giay,
    }
    cache.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    
    return quiz


def render(quiz: Quiz) -> str:
    """Render quiz ra text cho Discord."""
    return quiz.trac_nghiem_text
