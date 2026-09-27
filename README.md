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
- **Phase 3** *(this doc)* — LLM decides tool calls from natural language over MCP
