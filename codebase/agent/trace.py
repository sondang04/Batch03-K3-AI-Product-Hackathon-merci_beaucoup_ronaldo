"""Trace logger — mỗi phiên một file JSONL trong codebase/logs/traces/.

Trace giữ trong repo (rubric R5: 'log/trace trong repo'), nên nội dung nguồn
bị cắt còn config.TRUNCATE ký tự — mã đoạn/mã M giữ nguyên để đối chiếu lại
từ data pack, không dán nguyên văn dài (quy định bảo mật data pack).
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config


def _clip(x, limit: int = config.TRUNCATE):
    if isinstance(x, str):
        return x if len(x) <= limit else x[:limit] + f"…(+{len(x) - limit} ký tự)"
    if isinstance(x, dict):
        return {k: _clip(v, limit) for k, v in x.items()}
    if isinstance(x, list):
        return [_clip(v, limit) for v in x[:20]]
    return x


class Trace:
    def __init__(self, label: str, provider: str, model: str):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.id = f"{ts}-{label}-{uuid.uuid4().hex[:6]}"
        dir_ = config.LOGS_DIR / "traces"
        dir_.mkdir(parents=True, exist_ok=True)
        self.path: Path = dir_ / f"{self.id}.jsonl"
        self.t0 = time.time()
        self.n_llm_calls = 0
        self.n_tool_calls = 0
        self.event("session_start", label=label, provider=provider, model=model)

    def event(self, kind: str, **fields):
        rec = {"t": round(time.time() - self.t0, 3), "kind": kind, **_clip(fields)}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def llm_call(self, provider: str, model: str, n_messages: int,
                 stop_reason: str | None, usage: dict | None, latency_s: float):
        self.n_llm_calls += 1
        self.event("llm_call", provider=provider, model=model,
                   n_messages=n_messages, stop_reason=stop_reason,
                   usage=usage or {}, latency_s=round(latency_s, 2))

    def tool_call(self, name: str, args: dict, result: str, latency_s: float):
        self.n_tool_calls += 1
        self.event("tool_call", name=name, args=args, result=result,
                   latency_s=round(latency_s, 3))

    def finish(self, final_text: str):
        self.event("session_end", final_text=final_text,
                   n_llm_calls=self.n_llm_calls, n_tool_calls=self.n_tool_calls,
                   total_s=round(time.time() - self.t0, 2))
