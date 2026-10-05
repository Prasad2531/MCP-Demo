import asyncio
import json
import time

from supervisor import route, ask, AGENTS
from tracing import new_trace_id, log_event


async def run_scenario(scenario: dict) -> dict:
    text = scenario["input"]
    trace_id = new_trace_id()
    t0 = time.time()

    actual_target = route(text)
    routed_ok = actual_target == scenario["expected_target"]

    answer = await ask(AGENTS[actual_target], text, trace_id)
    total_ms = (time.time() - t0) * 1000

    return {
        "id": scenario["id"],
        "input": text,
        "expected_target": scenario["expected_target"],
        "actual_target": actual_target,
        "routed_ok": routed_ok,
        "answer": answer,
        "latency_ms": round(total_ms, 1),
    }


async def main():
    with open("eval_scenarios.json") as f:
        scenarios = json.load(f)

    results = []
    for s in scenarios:
        print(f"Running: {s['id']}...")
        result = await run_scenario(s)
        results.append(result)
        status = "PASS" if result["routed_ok"] else "FAIL"
        print(f"  [{status}] routed to '{result['actual_target']}' (expected '{result['expected_target']}') — {result['latency_ms']}ms")

    passed = sum(1 for r in results if r["routed_ok"])
    total = len(results)
    print(f"\n{passed}/{total} scenarios routed correctly")

    with open("eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Full results written to eval_results.json")


if __name__ == "__main__":
    asyncio.run(main())