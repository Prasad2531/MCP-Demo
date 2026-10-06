import asyncio
import re
from langchain_ollama import ChatOllama
from a2a.client import create_client
from a2a.types import a2a_pb2
from tracing import new_trace_id, log_event
import time
import httpx
from a2a.client import ClientConfig

llm = ChatOllama(model="qwen2.5:7b", temperature=0)
AGENTS = {"order": "http://localhost:9101", "inventory": "http://localhost:9102"}


def route(text: str) -> str:
    has_order_signal = bool(re.search(r'\border\s*#?\s*\d+\b', text, re.IGNORECASE) or
                             re.search(r'\b(status|shipped|delivered|cancelled|refund)\b', text, re.IGNORECASE))
    has_inventory_signal = bool(re.search(r'\b(stock|inventory|how many|available|in stock)\b', text, re.IGNORECASE))

    if has_order_signal and has_inventory_signal:
        return "both"
    if has_order_signal:
        return "order"
    if has_inventory_signal:
        return "inventory"

    return route_with_llm(text)

def route_with_llm(text: str) -> str:
    decision = llm.invoke(
        f"Classify into one word, 'order' or 'inventory'.\nRequest: {text}\nOne word only."
    ).content.strip().lower()
    return "order" if "order" in decision else "inventory"

async def ask(url: str, text: str, trace_id: str) -> str:
    custom_httpx_client = httpx.AsyncClient(timeout=30.0)
    config = ClientConfig(httpx_client=custom_httpx_client)
    client = await create_client(url,client_config=config)
    msg = a2a_pb2.Message(
        message_id="m1", role=a2a_pb2.ROLE_USER, parts=[a2a_pb2.Part(text=text)],metadata={"trace_id": trace_id})
    last = ""
    async for event in client.send_message(a2a_pb2.SendMessageRequest(message=msg)):
        print("  [event]", type(event).__name__)   # remove once verified
        last = event
    return str(last)

async def ask_both(text: str, trace_id: str) -> str:
    t0 = time.time()

    order_text, inventory_text = split_compound_request(text)

    order_task = ask(AGENTS["order"], order_text, trace_id)
    inventory_task = ask(AGENTS["inventory"], inventory_text, trace_id)
    order_answer, inventory_answer = await asyncio.gather(order_task, inventory_task)

    fanout_ms = (time.time() - t0) * 1000
    log_event(trace_id, "supervisor.fanout_join", latency_ms=fanout_ms)

    return (
        f"Order info: {order_answer}\n\n"
        f"Inventory info: {inventory_answer}"
    )

def split_compound_request(text: str) -> tuple[str, str]:
    """Split a compound request into the order-relevant and inventory-relevant parts.
    Naive sentence/clause split using 'and' as the separator, falling back to
    sending the full text to both if no clean split is found."""
    parts = re.split(r'\band\b', text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) < 2:
        # Couldn't cleanly split — fall back to sending the full text to both
        return text, text

    order_part = next((p for p in parts if re.search(r'\border\s*#?\s*\d+\b|status|shipped|delivered|refund', p, re.IGNORECASE)), text)
    inventory_part = next((p for p in parts if re.search(r'\bstock|inventory|available\b', p, re.IGNORECASE)), text)

    return order_part, inventory_part

async def main():
    while True:
        text = input("You: ")
        if text.lower() == "exit":
            break

        trace_id = new_trace_id()
        t0 = time.time()

        target = route(text)
        route_ms = (time.time() - t0) * 1000
        log_event(trace_id, "supervisor.route", input=text, target=target, latency_ms=route_ms)

        print(f"[routed to {target}_agent via A2A]  trace_id={trace_id}")
        if target == "both":
            print("[fan-out: order_agent + inventory_agent in parallel via A2A]")
            result = await ask_both(text, trace_id)
        else:
            print(f"[routed to {target}_agent via A2A]  trace_id={trace_id}")
            result = await ask(AGENTS[target], text, trace_id)

        print("Bot:", result, "\n")
        #t1 = time.time()
        #result = await ask(AGENTS[target], text,trace_id)
        #a2a_ms = (time.time() - t1) * 1000
        #log_event(trace_id, "supervisor.a2a_call", target=target, latency_ms=a2a_callms)


if __name__ == "__main__":
    asyncio.run(main())