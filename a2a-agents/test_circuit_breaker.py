import asyncio
import json
import time

from supervisor import ask, AGENTS
from tracing import new_trace_id

TRACE_LOG = "trace.log"


async def send_request(text: str) -> str:
    trace_id = new_trace_id()
    answer = await ask(AGENTS["order"], text, trace_id)
    return trace_id, answer


def read_trace_entries(trace_ids: set) -> list:
    entries = []
    with open(TRACE_LOG) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("trace_id") in trace_ids:
                entries.append(event)
    return entries


async def main():
    print("MAKE SURE Mcp-Server IS CURRENTLY STOPPED before running this.")
    input("Press Enter once Mcp-Server is stopped...")

    trace_ids = []
    for i in range(4):
        print(f"\nRequest {i+1}:")
        trace_id, answer = await send_request("status of order 1")
        trace_ids.append(trace_id)
        print(f"  trace_id={trace_id}")
        await asyncio.sleep(1)

    time.sleep(0.5)  # let logging flush
    entries = read_trace_entries(set(trace_ids))
    error_entries = [e for e in entries if e.get("span") == "agent.tool_call_error"]

    real_failures = [e for e in error_entries if "circuit breaker" not in e.get("error", "").lower()]
    circuit_shortcuts = [e for e in error_entries if "circuit breaker" in e.get("error", "").lower()]

    print("\n--- Summary ---")
    print(f"Real MCP failures logged: {len(real_failures)}")
    print(f"Circuit breaker short-circuits logged: {len(circuit_shortcuts)}")
    for e in circuit_shortcuts:
        print(f"  trace_id={e['trace_id']}  latency_ms={e['latency_ms']}")

    if real_failures and circuit_shortcuts:
        print("\nPASS: circuit breaker engaged after repeated failures.")
    else:
        print("\nFAIL: circuit breaker did not engage as expected.")

    print("\nNow restart Mcp-Server and re-run run_evals.py to confirm the happy path still works.")


if __name__ == "__main__":
    asyncio.run(main())