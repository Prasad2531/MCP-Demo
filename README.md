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