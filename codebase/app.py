#!/usr/bin/env python3
"""Web app `/recap` — WORKING prototype, chạy end-to-end trên data pack thật.

    python3 codebase/app.py            # rồi mở http://localhost:8000

Vì sao web mà không phải Discord: `discord.py` cần cài từ mạng, môi trường dev
này không có. Lõi agent đã transport-agnostic (`run_agent` / `build_recap` không
biết gì về UI), nên Discord chỉ là một adapter mỏng thêm sau. Web app cho phép
đưa cho **người thật** dùng ngay (tiêu chí nghiệm thu #5, rubric R6).

Chỉ dùng stdlib — không thêm dependency.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import config                      # noqa: E402
from agent.agent import run_agent             # noqa: E402
from agent.llm import make_client             # noqa: E402
from agent.recap import build_recap, render   # noqa: E402

CLIENT = make_client()
LOCK = threading.Lock()          # gpt-4o-mini call: tuần tự hoá cho dễ đọc trace

HTML = """<!doctype html><html lang=vi><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>/recap — ôn tập buổi học</title><style>
*{box-sizing:border-box;margin:0}
body{font-family:"gg sans","Segoe UI",Roboto,system-ui,sans-serif;background:#313338;
 color:#dbdee1;height:100vh;display:flex;flex-direction:column}
header{background:#2b2d31;border-bottom:1px solid #1f2023;padding:10px 16px;display:flex;
 align-items:center;gap:12px;flex-shrink:0}
header b{font-size:15px} header select{background:#1e1f22;color:#dbdee1;border:1px solid #3f4147;
 border-radius:4px;padding:5px 8px;font-family:inherit;font-size:13px}
header .st{color:#949ba4;font-size:12px;margin-left:auto}
#feed{flex:1;overflow-y:auto;padding:16px}
.msg{display:flex;gap:12px;margin-bottom:15px;max-width:900px}
.av{width:38px;height:38px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;
 justify-content:center;font-size:19px;background:#23a55a}
.av.u{background:#5865f2}
.who{font-weight:600;font-size:15px;margin-bottom:3px}
.who .tag{background:#5865f2;color:#fff;font-size:10px;padding:1px 5px;border-radius:4px;
 vertical-align:2px;margin-left:5px}
.bd{font-size:14.5px;line-height:1.5;white-space:pre-wrap;min-width:0}
.bd b,.bd strong{color:#f2f3f5} .bd code{background:#1e1f22;color:#00a8fc;padding:1px 5px;
 border-radius:3px;font-size:12.5px}
.tools{color:#949ba4;font-size:12px;font-family:Consolas,monospace;margin-bottom:5px}
.card{background:#2b2d31;border-left:3px solid #23a55a;border-radius:6px;padding:11px 13px;
 margin-bottom:9px;max-width:900px}
.card.warn{border-left-color:#f0b232} .card.head{border-left-color:#5865f2}
.spin{color:#949ba4;font-size:13px;padding:4px 0 10px 50px}
#bar{background:#313338;padding:0 16px 18px;flex-shrink:0}
#box{display:flex;gap:9px;background:#383a40;border-radius:8px;padding:11px 14px;max-width:900px}
#box input{flex:1;background:none;border:0;outline:0;color:#dbdee1;font-size:14.5px;
 font-family:inherit}
#box button{background:#5865f2;color:#fff;border:0;border-radius:4px;padding:5px 14px;
 cursor:pointer;font-family:inherit;font-size:13px}
#box button:disabled{opacity:.5;cursor:default}
.hint{color:#6d6f78;font-size:11.5px;margin:6px 0 0 2px;max-width:900px}
</style></head><body>
<header><b>📚 /recap</b>
<select id=ses><option value=day01>Day 1 — AI &amp; LLM Foundation</option>
<option value=day02-sang>Day 2 sáng — Xác định bài toán cho AI</option></select>
<button onclick=loadRecap() style="background:#4e5058;color:#fff;border:0;border-radius:4px;
 padding:5px 11px;cursor:pointer;font-family:inherit;font-size:13px">Recap buổi này</button>
<span class=st id=st></span></header>
<div id=feed></div>
<div id=bar><div id=box>
  <input id=q placeholder="Hỏi về buổi học… (vd: hai mùa đông AI là gì?)"
   onkeydown="if(event.key==='Enter')ask()">
  <button id=send onclick=ask()>Gửi</button>
</div>
<div class=hint>Trả lời luôn kèm mã đoạn <code>[T04-053]</code> hoặc <code>[slide tr.N]</code>
 — bấm vào để đối chiếu. Bot không biết deadline và không trả lời ngoài nguồn buổi học.</div>
</div>
<script>
const feed=document.getElementById('feed'), st=document.getElementById('st');
const fmt=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>').replace(/\\*(.+?)\\*/g,'<i>$1</i>')
  .replace(/`([^`]+)`/g,'<code>$1</code>')
  .replace(/\\[(T\\d{2}-\\d{3})\\]/g,'<code>[$1]</code>');
function bot(html,cls,tools){feed.insertAdjacentHTML('beforeend',
  cls?`<div class="card ${cls}">${html}</div>`
    :`<div class=msg><div class=av>📚</div><div><div class=who>VLearn Recap<span class=tag>BOT</span></div>
      ${tools?`<div class=tools>⚙️ ${tools}</div>`:''}<div class=bd>${html}</div></div></div>`);
  feed.scrollTop=feed.scrollHeight;}
function me(t){feed.insertAdjacentHTML('beforeend',
  `<div class=msg><div class="av u">🧑‍🎓</div><div><div class=who>bạn</div>
   <div class=bd>${fmt(t)}</div></div></div>`);feed.scrollTop=feed.scrollHeight;}
function spin(t){const d=document.createElement('div');d.className='spin';d.textContent=t;
  feed.appendChild(d);feed.scrollTop=feed.scrollHeight;return d;}

async function loadRecap(){
  const s=document.getElementById('ses').value;
  feed.innerHTML=''; const sp=spin('đang dựng recap…');
  try{
    const r=await(await fetch('/api/recap?session='+s)).json();
    sp.remove();
    st.textContent=`${r.n_block} block · ${r.n_ai} lời gọi AI · ${r.giay}s${r.cache?' (cache)':''}`;
    r.messages.forEach((m,i)=>bot(fmt(m), i===0?'head':(i===r.messages.length-1?'warn':'')));
  }catch(e){sp.remove();bot('Lỗi dựng recap: '+e);}
}
async function ask(){
  const inp=document.getElementById('q'), btn=document.getElementById('send');
  const t=inp.value.trim(); if(!t)return; inp.value=''; me(t);
  btn.disabled=true; const sp=spin('đang tra nguồn buổi học…');
  try{
    const r=await(await fetch('/api/chat',{method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify({q:t,session:document.getElementById('ses').value})})).json();
    sp.remove(); bot(fmt(r.answer), '', r.tools.join(' → '));
    st.textContent=`${r.n_turns} lượt LLM · trace ${r.trace}`;
  }catch(e){sp.remove();bot('Lỗi: '+e);}
  btn.disabled=false; inp.focus();
}
bot('Chào bạn 👋 Chọn buổi rồi bấm <b>Recap buổi này</b>, hoặc hỏi thẳng một câu.'
  +' Mình chỉ trả lời khi có căn cứ trong bản ghi/slide của buổi — và luôn dẫn mã đoạn.');
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def log_message(self, *a):                      # bớt ồn
        pass

    def do_GET(self):
        if self.path == "/":
            return self._send(200, HTML.encode(), "text/html; charset=utf-8")
        if self.path.startswith("/api/recap"):
            from urllib.parse import parse_qs, urlparse
            sid = (parse_qs(urlparse(self.path).query).get("session") or ["day01"])[0]
            if sid not in config.SESSIONS:
                return self._json({"loi": f"buổi không hợp lệ: {sid}"}, 400)
            from agent.recap import CACHE_DIR
            cached = (CACHE_DIR / f"{sid}-{CLIENT.model}.json").exists()
            with LOCK:
                r = build_recap(sid, CLIENT)
            return self._json({"messages": render(r), "n_block": len(r.blocks),
                               "n_ai": r.n_ai_calls, "giay": r.giay, "cache": cached})
        self._json({"loi": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/chat":
            return self._json({"loi": "not found"}, 404)
        n = int(self.headers.get("Content-Length", 0))
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json({"loi": "body không phải JSON"}, 400)
        q = (d.get("q") or "").strip()
        if not q:
            return self._json({"loi": "thiếu câu hỏi"}, 400)
        with LOCK:
            res = run_agent(q, CLIENT, label="web")
        return self._json({"answer": res.text, "tools": res.tool_calls,
                           "n_turns": res.n_turns,
                           "trace": Path(res.trace_path).name})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"provider={CLIENT.provider} · model={CLIENT.model}")
    print(f"→ mở http://localhost:{port}   (Ctrl-C để dừng)")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
