"""Lớp LLM client — 4 backend sau cùng một interface:

- OpenAIClient    : `openai` SDK, model gpt-4o-mini (mặc định của nhóm từ 30/07).
                    Cùng lớp này phục vụ provider "openrouter" (OpenAI-compatible,
                    chỉ khác base_url + key) — xem make_client() ở cuối file.
- AnthropicClient : `anthropic` SDK, model claude-opus-5 (thinking adaptive mặc
                    định của model; cache system prompt).
- GeminiClient    : `google.genai` SDK, model theo env GEMINI_MODEL — free tier
                    của khoá (guide §3.4: chỉ đưa data pack, không data thật khác).
- MockClient      : kịch bản định sẵn, offline — test suite chạy không cần key.

Interface chung (neutral, không lộ kiểu SDK ra ngoài):
    client.create(system, history, tools) -> Turn
    client.subcall(system, user)          -> str      # AI call phụ (summarize)

`history` là list các entry neutral:
    {"role": "user", "text": ...}
    {"role": "assistant", "text": ..., "tool_calls": [{id,name,input}]}
    {"role": "tool_results", "results": [{id, name, content, is_error}]}
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from . import config


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict | None = None
    latency_s: float = 0.0


# ── OpenAI ───────────────────────────────────────────────────────────────────

class OpenAIClient:
    provider = "openai"

    def __init__(self, model: str = config.OPENAI_MODEL,
                 base_url: str | None = None, api_key: str | None = None):
        import json as _json
        from openai import OpenAI
        self._json = _json
        self.model = model
        # base_url/api_key để trống → SDK tự đọc OPENAI_BASE_URL / OPENAI_API_KEY.
        # Truyền vào khi đi qua cổng OpenAI-compatible (OpenRouter, proxy BTC).
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        self._client = OpenAI(**kwargs)

    def _to_messages(self, system: str, history: list[dict]) -> list[dict]:
        msgs = [{"role": "system", "content": system}]
        for h in history:
            if h["role"] == "user":
                msgs.append({"role": "user", "content": h["text"]})
            elif h["role"] == "assistant":
                m = {"role": "assistant", "content": h.get("text") or None}
                if h.get("tool_calls"):
                    m["tool_calls"] = [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.name,
                                      "arguments": self._json.dumps(tc.input,
                                                                    ensure_ascii=False)}}
                        for tc in h["tool_calls"]]
                msgs.append(m)
            elif h["role"] == "tool_results":
                # OpenAI: MỖI tool_result là một message role="tool" riêng
                for r in h["results"]:
                    msgs.append({"role": "tool", "tool_call_id": r["id"],
                                 "content": r["content"]})
        return msgs

    @staticmethod
    def _to_tools(tools: list[dict]) -> list[dict]:
        return [{"type": "function",
                 "function": {"name": d["name"], "description": d["description"],
                              "parameters": d["input_schema"]}}
                for d in tools]

    def create(self, system: str, history: list[dict], tools: list[dict]) -> Turn:
        t0 = time.time()
        resp = self._client.chat.completions.create(
            model=self.model, max_tokens=config.MAX_TOKENS,
            messages=self._to_messages(system, history),
            tools=self._to_tools(tools))
        msg = resp.choices[0].message
        calls = [ToolCall(id=c.id, name=c.function.name,
                          input=self._json.loads(c.function.arguments or "{}"))
                 for c in (msg.tool_calls or [])]
        usage = ({"in": resp.usage.prompt_tokens, "out": resp.usage.completion_tokens}
                 if resp.usage else None)
        return Turn(text=msg.content or "", tool_calls=calls,
                    stop_reason="tool_use" if calls else resp.choices[0].finish_reason,
                    usage=usage, latency_s=time.time() - t0)

    def subcall(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model, max_tokens=1024,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        return resp.choices[0].message.content or ""


# ── Anthropic ────────────────────────────────────────────────────────────────

class AnthropicClient:
    provider = "anthropic"

    def __init__(self, model: str = config.ANTHROPIC_MODEL):
        import anthropic
        self.model = model
        self._client = anthropic.Anthropic()

    @staticmethod
    def _to_messages(history: list[dict]) -> list[dict]:
        msgs = []
        for h in history:
            if h["role"] == "user":
                msgs.append({"role": "user", "content": h["text"]})
            elif h["role"] == "assistant":
                content = []
                if h.get("text"):
                    content.append({"type": "text", "text": h["text"]})
                for tc in h.get("tool_calls", []):
                    content.append({"type": "tool_use", "id": tc.id,
                                    "name": tc.name, "input": tc.input})
                msgs.append({"role": "assistant", "content": content})
            elif h["role"] == "tool_results":
                # mọi tool_result của một lượt đi trong MỘT user message
                msgs.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r["id"],
                     "content": r["content"],
                     **({"is_error": True} if r.get("is_error") else {})}
                    for r in h["results"]]})
        return msgs

    def create(self, system: str, history: list[dict], tools: list[dict]) -> Turn:
        t0 = time.time()
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=config.MAX_TOKENS,
            # system ổn định → cache prefix (tools render trước system nên
            # breakpoint ở block system cuối phủ luôn tools)
            system=[{"type": "text", "text": system,
                     "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=self._to_messages(history),
        )
        text, calls = "", []
        if resp.stop_reason != "refusal":          # refusal: content có thể rỗng
            for block in resp.content:
                if block.type == "text":
                    text += block.text
                elif block.type == "tool_use":
                    calls.append(ToolCall(id=block.id, name=block.name,
                                          input=dict(block.input)))
        usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens,
                 "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0)}
        return Turn(text=text, tool_calls=calls, stop_reason=resp.stop_reason,
                    usage=usage, latency_s=time.time() - t0)

    def subcall(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model, max_tokens=1024,
            system=[{"type": "text", "text": system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            return "(model từ chối tóm tắt đoạn này)"
        return "".join(b.text for b in resp.content if b.type == "text")


# ── Gemini ───────────────────────────────────────────────────────────────────

class GeminiClient:
    provider = "gemini"

    def __init__(self, model: str = config.GEMINI_MODEL):
        from google import genai
        self.model = model
        self._genai = genai
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def _cfg(self, system: str, tools: list[dict] | None):
        t = self._genai.types
        cfg = dict(system_instruction=system, max_output_tokens=config.MAX_TOKENS)
        if tools:
            decls = [t.FunctionDeclaration(
                        name=d["name"], description=d["description"],
                        parameters_json_schema=d["input_schema"])
                     for d in tools]
            cfg["tools"] = [t.Tool(function_declarations=decls)]
            cfg["automatic_function_calling"] = \
                t.AutomaticFunctionCallingConfig(disable=True)
        return t.GenerateContentConfig(**cfg)

    def _to_contents(self, history: list[dict]):
        t = self._genai.types
        contents = []
        for h in history:
            if h["role"] == "user":
                contents.append(t.Content(role="user",
                                          parts=[t.Part.from_text(text=h["text"])]))
            elif h["role"] == "assistant":
                parts = []
                if h.get("text"):
                    parts.append(t.Part.from_text(text=h["text"]))
                for tc in h.get("tool_calls", []):
                    parts.append(t.Part.from_function_call(name=tc.name,
                                                           args=tc.input))
                contents.append(t.Content(role="model", parts=parts))
            elif h["role"] == "tool_results":
                contents.append(t.Content(role="user", parts=[
                    t.Part.from_function_response(name=r["name"],
                                                  response={"result": r["content"]})
                    for r in h["results"]]))
        return contents

    def create(self, system: str, history: list[dict], tools: list[dict]) -> Turn:
        t0 = time.time()
        resp = self._client.models.generate_content(
            model=self.model, contents=self._to_contents(history),
            config=self._cfg(system, tools))
        calls = [ToolCall(id=f"g{i}", name=fc.name, input=dict(fc.args or {}))
                 for i, fc in enumerate(resp.function_calls or [])]
        um = getattr(resp, "usage_metadata", None)
        usage = ({"in": um.prompt_token_count, "out": um.candidates_token_count}
                 if um else None)
        return Turn(text=resp.text or "", tool_calls=calls,
                    stop_reason="tool_use" if calls else "end_turn",
                    usage=usage, latency_s=time.time() - t0)

    def subcall(self, system: str, user: str) -> str:
        resp = self._client.models.generate_content(
            model=self.model, contents=user, config=self._cfg(system, None))
        return resp.text or ""


# ── Mock (offline) ───────────────────────────────────────────────────────────

class MockClient:
    """Kịch bản định sẵn: list các Turn-spec, mỗi lần create() trả một turn.
    spec: {"tool_calls": [{"name","input"}]} hoặc {"text": "..."}."""
    provider = "mock"
    model = "mock"

    def __init__(self, script: list[dict], summary_stub: str = ""):
        self._script = list(script)
        self._i = 0
        self.summary_stub = summary_stub or (
            "- LLM đoán token tiếp theo từ context [T04-046]\n"
            "🔑 Keyword: token · context · Transformer")
        self.subcalls: list[tuple[str, str]] = []     # test soi được

    def create(self, system, history, tools) -> Turn:
        if self._i >= len(self._script):
            return Turn(text="(mock: hết kịch bản)", stop_reason="end_turn")
        spec = self._script[self._i]
        self._i += 1
        calls = [ToolCall(id=f"m{self._i}-{j}", name=c["name"], input=c["input"])
                 for j, c in enumerate(spec.get("tool_calls", []))]
        return Turn(text=spec.get("text", ""), tool_calls=calls,
                    stop_reason="tool_use" if calls else "end_turn",
                    usage={"in": 0, "out": 0}, latency_s=0.0)

    def subcall(self, system: str, user: str) -> str:
        self.subcalls.append((system, user))
        return self.summary_stub


def make_client(provider: str | None = None):
    p = provider or config.PROVIDER
    if p == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError(
                "Thiếu OPENROUTER_API_KEY — đặt trong .env ở gốc repo "
                "(xem codebase/DISCORD-SETUP.md).")
        c = OpenAIClient(model=config.OPENROUTER_MODEL,
                         base_url=config.OPENROUTER_BASE_URL, api_key=key)
        c.provider = "openrouter"
        return c
    if p == "openai":
        return OpenAIClient()
    if p == "anthropic":
        return AnthropicClient()
    if p == "gemini":
        return GeminiClient()
    raise ValueError(f"provider '{p}' cần script — dùng MockClient(script) trực tiếp")
