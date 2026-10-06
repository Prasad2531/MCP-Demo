import asyncio
import json
import time

from supervisor import route, ask, AGENTS
from tracing import new_trace_id

TRACE_LOG = "trace.log"


def read_trace_entries(trace_id: str) -> list:
    entries = []
    with open(TRACE_LOG) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("trace_id") == trace_id:
                entries.append(event)
    return entries


async def run_scenario(scenario: dict) -> dict:
    text = scenario["input"]
    trace_id = new_trace_id()

    actual_target = route(text)
    routed_ok = actual_target == scenario["expected_target"]

    answer = await ask(AGENTS[actual_target], text, trace_id)
    time.sleep(0.3)  # let logging flush before reading trace.log

    entries = read_trace_entries(trace_id)
    tool_call_entries = [e for e in entries if e.get("span") == "mcp.tool_call"]

    actual_tool = tool_call_entries[0]["tool"] if tool_call_entries else None
    actual_args = tool_call_entries[0]["args"] if tool_call_entries else {}

    expected_tool = scenario.get("expected_tool")
    tool_ok = (expected_tool is None) or (actual_tool == expected_tool)

    expected_args = scenario.get("expected_args") or {}
    args_ok = all(actual_args.get(k) == v for k, v in expected_args.items())

    return {
        "id": scenario["id"],
        "input": text,
        "expected_target": scenario["expected_target"],
        "actual_target": actual_target,
        "routed_ok": routed_ok,
        "expected_tool": expected_tool,
        "actual_tool": actual_tool,
        "tool_ok": tool_ok,
        "expected_args": expected_args,
        "actual_args": actual_args,
        "args_ok": args_ok,
    }


async def main():
    with open("eval_scenarios.json") as f:
        scenarios = json.load(f)

    results = []
    for s in scenarios:
        print(f"Running: {s['id']}...")
        result = await run_scenario(s)
        results.append(result)
        status = "PASS" if (result["routed_ok"] and result["tool_ok"] and result["args_ok"]) else "FAIL"
        print(f"  [{status}] routing={result['routed_ok']} tool={result['actual_tool']} (expected {result['expected_tool']}) tool_ok={result['tool_ok']} args_ok={result['args_ok']}")

    routed_passed = sum(1 for r in results if r["routed_ok"])
    tool_passed = sum(1 for r in results if r["tool_ok"])
    args_passed = sum(1 for r in results if r["args_ok"])
    full_passed = sum(1 for r in results if r["routed_ok"] and r["tool_ok"] and r["args_ok"])
    total = len(results)

    print(f"\nRouting: {routed_passed}/{total}")
    print(f"Tool selection: {tool_passed}/{total}")
    print(f"Args match: {args_passed}/{total}")
    print(f"Full pass: {full_passed}/{total}")

    with open("eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Full results written to eval_results.json")


if __name__ == "__main__":
    asyncio.run(main())