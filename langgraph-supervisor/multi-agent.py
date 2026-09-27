import asyncio
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

llm = ChatOllama(model="qwen2.5:7b", temperature=0.2)

async def main():
    client = MultiServerMCPClient({
        "ecommerce": {
            "transport": "sse",
            "url": "http://localhost:8080/sse",
        }
    })
    tools = await client.get_tools()

    # --- Specialized sub-agents ---
    order_agent = create_agent(
        llm, tools,
        name="order_agent",
        system_prompt="You handle order status questions only. Use getOrderStatus."
    )
    inventory_agent = create_agent(
        llm, tools,
        name="inventory_agent",
        system_prompt="You handle product search and stock questions only. Use searchProducts and checkInventory."
    )

    # --- Supervisor: routes based on intent ---
    def route(user_input: str) -> str:
        routing_prompt = f"""Classify this request into exactly one word: 'order' or 'inventory'.
Request: {user_input}
Answer with one word only."""
        decision = llm.invoke(routing_prompt).content.strip().lower()
        return "order" if "order" in decision else "inventory"

    print("=== Multi-Agent E-commerce System (LangGraph + MCP) ===\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break

        target = route(user_input)
        agent = order_agent if target == "order" else inventory_agent
        print(f"[routed to: {target}_agent]")

        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_input}]})
        print("Bot:", result["messages"][-1].content, "\n")

if __name__ == "__main__":
    asyncio.run(main())