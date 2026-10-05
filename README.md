# MCP Demo — E-commerce Model Context Protocol Server & Client

A minimal demo of the **Model Context Protocol (MCP)** applied to an e-commerce domain, built with Spring Boot and Spring AI.

## What this is

- **Mcp-Server**: Exposes e-commerce tools (`searchProducts`, `checkInventory`, `getOrderStatus`) over MCP using an H2 in-memory database. Any MCP-compatible client (Claude Desktop, custom agents, IDEs) can discover and invoke these tools.
- **Mcp-Client**: A minimal Java MCP client that connects to the server, lists available tools, and invokes them — demonstrating real tool discovery and execution over the protocol.

## Why MCP (not just a REST API)

MCP standardizes how AI agents discover and call external tools, decoupling tool *providers* (this server) from tool *consumers* (any LLM-based client). This mirrors how production agentic systems expose internal services to AI assistants.

## Tech Stack

- Java 21, Spring Boot 3.5
- Spring AI 1.1.8 (`spring-ai-starter-mcp-server-webmvc`, `spring-ai-starter-mcp-client`)
- H2 in-memory database + Spring Data JPA
- Transport: SSE (Server-Sent Events)

## Running it

**1. Start the server**
```bash
cd Mcp-Server
mvn spring-boot:run
```
Server starts on `http://localhost:8080`, MCP SSE endpoint at `/sse`.

**2. Run the client**
```bash
cd Mcp-Client
mvn spring-boot:run
```
Connects to the server, lists tools, and calls `searchProducts` as a demo.
Terminal A: brew services start ollama  
Terminal B:  
cd MCPServer-ClientDemo/a2a-agents  
source venv/bin/activate  
python order_agent.py  
Terminal C:  
cd ~/Documents/Projects/MCPServer-ClientDemo/a2a-agents
source venv/bin/activate
python inventory_agent.py
Terminal D:
cd ~/Documents/Projects/MCPServer-ClientDemo/a2a-agents
source venv/bin/activate
python supervisor.py
## Example Output
=== Available Tools ===

Server exposes these tools:

- getOrderStatus: Get the status and total amount of an order by order ID
- searchProducts: Search products by name keyword
- checkInventory: Check current stock quantity for a product by its ID

=== Calling searchProducts(query=mouse) ===
- [{"id":1,"name":"Wireless Mouse","category":"Electronics","price":19.99,"stockQuantity":150}]

##Diagram
<img width="1472" height="1252" alt="image" src="https://github.com/user-attachments/assets/f450073d-01c0-4ec0-bbf0-2bad8a42e909" />

## Verifying the LLM is actually driving tool selection

**Option A — debug logging.** Add to `application.properties`:
```properties
logging.level.org.springframework.ai=DEBUG
logging.level.org.springframework.ai.mcp=DEBUG
```
Shows the exact prompt sent to Qwen, the tool it chose, its arguments, the tool's raw response, and the final generated answer.

**Option B — kill the LLM dependency.**
```bash
brew services stop ollama
```
Send a message — expect a connection-refused error, proving there's no hardcoded fallback logic; the app genuinely needs the local LLM to respond.
```bash
brew services start ollama   # restart after testing
```

## Roadmap Context

- **Phase 1** — in-process function calling, no protocol
- **Phase 2** — MCP server + bare client, protocol mechanics proven
- **Phase 3** — LLM decides tool calls from natural language over MCP
## Phase 4 — Multi-Agent Supervisor (LangGraph)

Adds a second, Python-based client (`langgraph-supervisor/`) that connects to the **same unmodified Java MCP server**, proving MCP's cross-language interoperability. Introduces a supervisor pattern: one LLM call classifies user intent, then routes to a specialized sub-agent (order vs. inventory) that has its own scoped system prompt and tool access.

### Why a separate language here

Spring AI doesn't yet have a mature multi-agent orchestration abstraction; **LangGraph** (Python) is currently the most established framework for this pattern. The Java MCP server required zero changes — MCP's protocol-based design means any client, in any language, can connect identically.

### Tech Stack

- Python 3.12, `langgraph`, `langchain`, `langchain-ollama`, `langchain-mcp-adapters`
- Same local Qwen2.5:7b via Ollama — no new API keys, no new cost
- Connects to the existing `Mcp-Server` over SSE — no server changes required

### Architecture
User input  
│  
▼  
Supervisor (LLM call #1) — classifies intent: "order" or "inventory"  
│  
├── order_agent (LLM call #2, scoped tools: getOrderStatus)  
│  
└── inventory_agent (LLM call #2, scoped tools: searchProducts, checkInventory)  


### Running it

```bash
cd langgraph-supervisor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
With `Mcp-Server` and Ollama already running:
```bash
python multi-agent.py
```

### Example
You: what's the status of order 1  
[routed to: order_agent]  
Bot: Order #1 for Alice Smith is SHIPPED, total $99.98  

You: search for mouse  
[routed to: inventory_agent]  
Bot: Found Wireless Mouse — Electronics category, $19.99, 150 units in stock  

## Phase 5: A2A Agent Services

Phase 4's sub-agents ran in-process, so the supervisor called them as Python functions. In Phase 5 each agent becomes an independent network service that publishes an **Agent Card**, and the supervisor discovers and delegates to them over **A2A (Agent2Agent)**. The Java MCP server is unchanged: MCP handles agent-to-tool calls, A2A handles agent-to-agent calls.

### Architecture
supervisor.py  
│ 1. classify intent (LLM call)  
│ 2. A2A JSON-RPC over HTTP  
├──▶ order_agent :9101 ──MCP──▶ Java Mcp-Server ──▶ H2  
│ tools: getOrderStatus  
└──▶ inventory_agent :9102 ──MCP──▶ Java Mcp-Server ──▶ H2  
tools: searchProducts, checkInventory  

### What each piece does

| Component | Role |
|---|---|
| `common.py` | Builds a LangChain agent from a subset of MCP tools; `LangChainAgentExecutor` bridges A2A requests to that agent |
| `order_agent.py` | A2A server on port 9101, exposes the order-status skill |
| `inventory_agent.py` | A2A server on port 9102, exposes the product search and stock skill |
| `supervisor.py` | Classifies the request, resolves the target agent, sends the task over A2A |

Each agent publishes its capabilities at `/.well-known/agent-card.json`:
```bash
curl http://localhost:9101/.well-known/agent-card.json
curl http://localhost:9102/.well-known/agent-card.json
```

### A2A task lifecycle

The executor follows the protocol's long-running task pattern:
1. Enqueue a `Task` (state `SUBMITTED`)
2. Publish `TASK_STATE_WORKING`
3. Run the LangChain agent (which calls MCP tools)
4. Publish `TASK_STATE_COMPLETED` with the answer, or `TASK_STATE_FAILED` on error

The server rejects status updates sent before the initial `Task` is enqueued, so step 1 is required.

### Running it

Prerequisites: Ollama running Qwen2.5, and the Java `Mcp-Server` on port 8080.

```bash
cd a2a-agents
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Start each process in its own terminal (venv active in each):
```bash
python order_agent.py       # terminal 1
python inventory_agent.py   # terminal 2
python supervisor.py        # terminal 3
```

Example:  
((venv) ) prasad@Mac a2a-agents % python supervisor.py
You: what's the status of order 1  
[routed to order_agent via A2A]  
[event] StreamResponse
Bot: task {
id: "9407b35c-b9ea-4a9c-9f47-674c40638234"  
context_id: "69dd70a2-a2e4-439c-9b96-3809919f47e0"  
status {
state: TASK_STATE_COMPLETED
message {
message_id: "9407b35c-b9ea-4a9c-9f47-674c40638234-msg"
role: ROLE_AGENT
parts {
text: "The status of order #1 is SHIPPED and the total amount is $99.98."
}
}
}
}
You: how much stock of mouse do we have  
[routed to inventory_agent via A2A]  
[event] StreamResponse
Bot: task {
id: "b7385951-29e2-4aad-8e03-86cb1f9fac95"
context_id: "588ea691-f9e0-47dc-bebd-543757d0231a"
status {
state: TASK_STATE_COMPLETED
message {
message_id: "b7385951-29e2-4aad-8e03-86cb1f9fac95-msg"
role: ROLE_AGENT
parts {
text: "We have 150 units of the Wireless Mouse in stock."
}
}
}
## Phase 6: Deterministic Routing and Structured Tracing

Two additions aimed at production reliability rather than new features: a deterministic pre-check that skips the LLM for obvious routing decisions, and structured, trace-correlated logging across the whole request path.

### 6a — Deterministic router

The supervisor's routing was 100% LLM-based, even for unambiguous input like "status of order 1." A regex pre-check now catches obvious cases before spending a model call:

```python
def route(text: str) -> str:
    if re.search(r'\border\s*#?\s*\d+\b', text, re.IGNORECASE) or \
       re.search(r'\b(status|shipped|delivered|cancelled|refund)\b', text, re.IGNORECASE):
        return "order"
    if re.search(r'\b(stock|inventory|how many|available|in stock)\b', text, re.IGNORECASE):
        return "inventory"
    return route_with_llm(text)  # only ambiguous phrasing reaches the model
```

Traced latency confirms the router itself costs well under 1ms, against ~2 seconds for the rest of the request — a real, measured savings for every request it catches, not just an assumption.

### 6b — Structured tracing

Every hop of a request now logs a JSON line to `trace.log`, correlated by a shared `trace_id` generated once per user request and threaded through the A2A message's `metadata` field:
supervisor.route → routing decision + latency
supervisor.a2a_call → full round trip to the chosen agent
agent.tool_call → the agent's LangChain loop (LLM + tool call)
mcp.tool_call → the underlying MCP/database round-trip

### What the trace revealed

Breaking down a ~2 second request:

| Span | Latency | Share |
|---|---|---|
| Routing (regex) | 0.17 ms | ~0% |
| MCP tool call (DB round-trip) | 26 ms | ~1.3% |
| Agent's LLM reasoning (2 passes) | ~1982 ms | ~97.9% |
| A2A network overhead | ~18 ms | ~0.9% |  

The database and network layers are fast and not the bottleneck. 
Nearly all latency is the local LLM's own inference time — deciding to call a tool, then composing the final answer. 
No amount of MCP or A2A optimization would meaningfully improve response time here; only a faster/smaller model, fewer LLM calls per request, or better hardware utilization would.

## Phase 6 (continued): Structured Failure Semantics

Failures were previously logged as raw exception strings — useful for a human reading one log line, but not groupable or queryable across many requests. Failures are now classified into a fixed set of structured reasons, logged alongside the raw error, so failure types can be counted, filtered, and eventually used to tune prompts or add targeted retry/fallback logic.

### Failure taxonomy

```python
class FailureReason(str, Enum):
    MCP_TIMEOUT = "mcp_timeout"
    MCP_TOOL_ERROR = "mcp_tool_error"
    A2A_TASK_FAILURE = "a2a_task_failure"
    AGENT_CARD_STALE = "agent_card_stale"
    LLM_MALFORMED_OUTPUT = "llm_malformed_output"
    UNKNOWN = "unknown"
```

`classify_exception()` inspects the raised exception and returns one of these. Every failure logged by the agent (`agent.tool_call_error`) and the MCP tool wrapper (`mcp.tool_call_error`) now carries a `reason` field, not just a free-text `error` string.

### The ExceptionGroup gotcha

The MCP Python SDK's SSE client uses `anyio.create_task_group()` internally. When the underlying connection fails, `anyio` wraps the real cause in an `ExceptionGroup`, whose own `str()` is a generic `"unhandled errors in a TaskGroup (1 sub-exception)"` — the actual cause (e.g. `httpcore.ConnectError`) lives inside `.exceptions`, not in the outer message. A naive `str(exc)` check missed this entirely and classified every MCP outage as `unknown`. `classify_exception()` unwraps `ExceptionGroup`s before inspecting message text:

```python
exceptions_to_check = [exc]
if hasattr(exc, "exceptions"):
    exceptions_to_check = list(exc.exceptions)
```

### Verified against a real outage

Stopping the Java `Mcp-Server` mid-session and sending requests through the live stack produced consistent, correctly classified results across repeated up/down cycles:

```json
{"trace_id": "f9e19df4", "span": "mcp.tool_call", "latency_ms": 110.0}
{"trace_id": "f9e19df4", "span": "agent.tool_call", "output": "Order #1 for Alice Smith is SHIPPED, total $99.98.", "latency_ms": 4771.5}
```
```json
{"trace_id": "cee78616", "span": "mcp.tool_call_error", "error": "unhandled errors in a TaskGroup (1 sub-exception)", "reason": "mcp_tool_error", "latency_ms": 0}
{"trace_id": "cee78616", "span": "agent.tool_call_error", "reason": "mcp_tool_error", "latency_ms": 920.0}
```

The failure-facing message shown to the end user (`Bot: ...`) still surfaces the generic `ExceptionGroup` text, since that path wasn't changed — only the structured log gained the classified reason. Surfacing a friendlier, classified message to the user is a natural follow-up, not yet done.

### A real debugging note from building this

Mid-testing, failures intermittently showed `"reason": "unknown"` with the error `"name 'FailureReason' is not defined"`, even though the code was correct. The cause was a **stale background process**: an earlier, pre-fix run of `order_agent.py` was still alive and listening on the same port, so some requests landed on the old process and some on the new one. `lsof -i :9101` showed two PIDs; killing both and restarting cleanly resolved it. Same root cause as an earlier Phase 5 issue — editing a shared module (`common.py`/`failures.py`) only takes effect in processes started *after* the edit, and Python doesn't warn you if an old process is still running alongside a new one.

### Circuit breaker

Without this, every request made a fresh, full-length attempt to reach MCP even when it was already known to be down — each failed attempt still cost close to a second (the `ExceptionGroup`'s connection-timeout behavior) before failing. A simple circuit breaker now tracks consecutive MCP failures per agent process and, once a threshold is hit, short-circuits further attempts for a cooldown window instead of repeating a doomed connection attempt:

The tool wrapper checks the circuit before attempting a call; if open, it fails instantly (logged as a `mcp.tool_call_error` with a dedicated reason) rather than waiting out a real connection attempt. A successful call resets the failure count, so the breaker re-opens automatically once MCP recovers rather than needing a manual reset.

This is scoped intentionally narrow: it protects *future* requests from repeating a known-bad attempt, not the request that originally discovered the failure — there's no way to know MCP is down before trying it at least once.
### Roadmap update

- **6a/6b/6c** (this + previous sections): deterministic routing, structured tracing, failure semantics — all done and verified against a real induced failure
- **6d**: a minimal eval harness (10 scenarios, routing-only) now exists; expanding it to check tool-call accuracy and args, not just routing, is the natural next step
- **Next**: circuit-breaker behavior (stop retrying a known-down MCP server on every request) was discussed but not yet implemented