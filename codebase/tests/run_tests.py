#!/usr/bin/env python3
"""Test suite cho agent `/recap`.

  python3 codebase/tests/run_tests.py                    # offline (mock) + static
  python3 codebase/tests/run_tests.py --live             # thêm vòng model thật
  python3 codebase/tests/run_tests.py --live --provider anthropic
  python3 codebase/tests/run_tests.py --only S1,O3

Offline kiểm: dispatch tool chạy đúng trên DATA THẬT, vòng lặp agent nối tool
đúng thứ tự, trace ghi đủ và có cắt nội dung. KHÔNG kiểm trí tuệ model.
Live kiểm: hành vi model thật qua regex require/forbid. Kết quả mọi lượt live
ghi vào codebase/logs/eval-runs/ để so sánh giữa các lần sửa prompt.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import config, tools as tools_mod          # noqa: E402
from agent.agent import load_system_prompt, run_agent  # noqa: E402
from agent.llm import MockClient, make_client          # noqa: E402
from tests import cases                                # noqa: E402

G, R, Y, N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def check(ok: bool, msg: str, fails: list):
    print(f"  {G+'✓'+N if ok else R+'✗'+N} {msg}")
    if not ok:
        fails.append(msg)


# ── Static: system prompt + tool descriptions ────────────────────────────────

def run_static(fails: list):
    print(f"\n{Y}── STATIC: system prompt & tool descriptions ──{N}")
    sp = load_system_prompt()
    for name, pat in cases.SYSTEM_PROMPT_MUST_HAVE:
        check(bool(re.search(pat, sp)), f"system prompt có mục '{name}'", fails)

    names = set()
    for t in tools_mod.TOOLS:
        nm = t["name"]
        names.add(nm)
        check(bool(re.fullmatch(r"[a-z][a-z0-9_]{1,63}", nm)),
              f"tool '{nm}': tên snake_case hợp lệ", fails)
        check(re.search(cases.TOOL_DESC_MUST_HAVE, t["description"]) is not None,
              f"tool '{nm}': description nói rõ KHI NÀO dùng", fails)
        sch = t["input_schema"]
        check(sch.get("type") == "object"
              and sch.get("additionalProperties") is False
              and isinstance(sch.get("required"), list),
              f"tool '{nm}': schema object + additionalProperties:false + required", fails)
    check(len(names) == len(tools_mod.TOOLS), "không có tool trùng tên", fails)


# ── Offline: mock qua vòng lặp thật + dispatch trên data thật ────────────────

def run_offline(selected, fails: list):
    print(f"\n{Y}── OFFLINE: mock client, dispatch trên data thật ──{N}")
    for case in selected:
        print(f"[{case['id']}] {case['question'][:64]}…")
        client = MockClient(script=case["mock_script"])
        res = run_agent(case["question"], client, label=f"test-{case['id']}")

        check(res.tool_calls == case["expect_tools"],
              f"gọi đúng dãy tool {case['expect_tools']} (thực tế: {res.tool_calls})",
              fails)
        check(res.stop_reason == "end_turn" and bool(res.text),
              "kết thúc end_turn và có câu trả lời", fails)

        trace_text = Path(res.trace_path).read_text(encoding="utf-8")
        for expected in case["offline_expect"]:
            check(expected in trace_text,
                  f"kết quả tool chứa '{expected}'", fails)
        # trace phải đủ sự kiện và tôn trọng giới hạn cắt
        kinds = [json.loads(l)["kind"] for l in trace_text.splitlines()]
        check(kinds[0] == "session_start" and kinds[-1] == "session_end"
              and kinds.count("llm_call") == res.n_turns
              and kinds.count("tool_call") == len(res.tool_calls),
              "trace đủ session_start/llm_call/tool_call/session_end", fails)
        over = [l for l in trace_text.splitlines()
                if any(len(v) > config.TRUNCATE + 40
                       for v in json.loads(l).values() if isinstance(v, str))]
        check(not over, f"mọi chuỗi trong trace bị cắt ≤{config.TRUNCATE} ký tự", fails)


# ── Live: model thật, chấm bằng regex ────────────────────────────────────────

def run_live(selected, provider: str, fails: list):
    print(f"\n{Y}── LIVE: provider={provider} ──{N}")
    client = make_client(provider)
    out_dir = config.LOGS_DIR / "eval-runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = {"stamp": stamp, "provider": provider, "model": client.model, "cases": []}

    for case in selected:
        print(f"[{case['id']}] {case['question'][:64]}…")
        res = run_agent(case["question"], client, label=f"live-{case['id']}")
        row = {"id": case["id"], "tools": res.tool_calls, "answer": res.text,
               "trace": res.trace_path, "pass": True}
        for pat in case["live_require"]:
            ok = re.search(pat, res.text) is not None
            row["pass"] &= ok
            check(ok, f"trả lời khớp /{pat}/", fails)
        for pat in case["live_forbid"]:
            ok = re.search(pat, res.text) is None
            row["pass"] &= ok
            check(ok, f"trả lời KHÔNG chứa /{pat}/", fails)
        report["cases"].append(row)

    n_pass = sum(1 for c in report["cases"] if c["pass"])
    report["tong"] = f"{n_pass}/{len(report['cases'])}"
    out = out_dir / f"live-{stamp}-{provider}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  báo cáo: {out}  ·  pass {report['tong']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--provider", default=None,
                    help="anthropic | gemini (mặc định: env AGENT_PROVIDER)")
    ap.add_argument("--only", default="",
                    help="lọc case theo tiền tố id, vd 'S1,O3'")
    args = ap.parse_args()

    selected = cases.CASES
    if args.only:
        pre = tuple(x.strip() for x in args.only.split(","))
        selected = [c for c in cases.CASES if c["id"].startswith(pre)]

    fails: list[str] = []
    run_static(fails)
    run_offline(selected, fails)
    if args.live:
        provider = args.provider or config.PROVIDER
        if provider == "mock":
            sys.exit("--live cần --provider anthropic|gemini (hoặc env AGENT_PROVIDER)")
        run_live(selected, provider, fails)

    print(f"\n{'='*60}")
    if fails:
        print(f"{R}FAIL {len(fails)} kiểm{N}")
        for f in fails:
            print(f"  ✗ {f}")
        sys.exit(1)
    print(f"{G}PASS toàn bộ{N}")


if __name__ == "__main__":
    main()
