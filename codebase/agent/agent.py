"""Vòng lặp agent — provider-agnostic.

Vòng lặp tự viết (thay vì tool-runner của SDK) vì phải chạy y hệt trên 3
backend Anthropic / Gemini / Mock với cùng một dispatch + trace; logic vẫn theo
đúng pattern manual-loop của Anthropic docs: chạy tới khi hết tool_use, mọi
tool_result của một lượt trả về trong MỘT message, tool lỗi trả is_error.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config, tools as tools_mod
from .trace import Trace


@dataclass
class AgentResult:
    text: str
    tool_calls: list[str] = field(default_factory=list)   # tên tool theo thứ tự
    n_turns: int = 0
    stop_reason: str | None = None
    trace_path: str = ""


def load_system_prompt() -> str:
    return (config.PROMPT_DIR / "system.md").read_text(encoding="utf-8")


def run_agent(question: str, client, label: str = "chat",
              max_turns: int = config.MAX_TURNS) -> AgentResult:
    system = load_system_prompt()
    dispatch = tools_mod.make_dispatch(subcall=client.subcall)
    trace = Trace(label=label, provider=client.provider, model=client.model)
    trace.event("user_message", text=question)

    history: list[dict] = [{"role": "user", "text": question}]
    result = AgentResult(text="", trace_path=str(trace.path))

    for _ in range(max_turns):
        turn = client.create(system, history, tools_mod.TOOLS)
        result.n_turns += 1
        result.stop_reason = turn.stop_reason
        trace.llm_call(client.provider, client.model, len(history),
                       turn.stop_reason, turn.usage, turn.latency_s)

        if turn.stop_reason == "refusal":
            result.text = ("Mình không hỗ trợ được yêu cầu này. Bạn thử hỏi TA "
                           "hoặc VLearn Tutor nhé.")
            break

        history.append({"role": "assistant", "text": turn.text,
                        "tool_calls": turn.tool_calls})

        if not turn.tool_calls:                      # end_turn — xong
            result.text = turn.text
            break

        results = []
        for tc in turn.tool_calls:
            result.tool_calls.append(tc.name)
            t0 = time.time()
            try:
                out = dispatch(tc.name, tc.input)
                is_err = False
            except Exception as e:                   # tool hỏng ≠ agent hỏng
                out = f"Lỗi tool {tc.name}: {type(e).__name__}: {e}"
                is_err = True
            trace.tool_call(tc.name, tc.input, out, time.time() - t0)
            results.append({"id": tc.id, "name": tc.name,
                            "content": out, "is_error": is_err})
        history.append({"role": "tool_results", "results": results})
    else:
        result.text = turn.text or "(đạt giới hạn vòng lặp — trả lời dở dang)"
        trace.event("max_turns_reached", max_turns=max_turns)

    trace.finish(result.text)
    return result
