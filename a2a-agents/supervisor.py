import asyncio
import re
from langchain_ollama import ChatOllama
from a2a.client import create_client
from a2a.types import a2a_pb2
from tracing import new_trace_id, log_event
import time

llm = ChatOllama(model="qwen2.5:7b", temperature=0)
AGENTS = {"order": "http://localhost:9101", "inventory": "http://localhost:9102"}


def route(text: str) -> str:
    # Deterministic router: catch obvious cases before spending an LLM call
    if re.search(r'\border\s*#?\s*\d+\b', text, re.IGNORECASE) or \
       re.search(r'\b(status|shipped|delivered|cancelled|refund)\b', text, re.IGNORECASE):
        print("[deterministic router: order]")
        return "order"

    if re.search(r'\b(stock|inventory|how many|available|in stock)\b', text, re.IGNORECASE):
        print("[deterministic router: inventory]")
        return "inventory"

    # Fallback: ambiguous phrasing, let the LLM decide
    return route_with_llm(text)

def route_with_llm(text: str) -> str:
    decision = llm.invoke(
        f"Classify into one word, 'order' or 'inventory'.\nRequest: {text}\nOne word only."
    ).content.strip().lower()
    return "order" if "order" in decision else "inventory"

async def ask(url: str, text: str, trace_id: str) -> str:
    client = await create_client(url)
    msg = a2a_pb2.Message(
        message_id="m1", role=a2a_pb2.ROLE_USER, parts=[a2a_pb2.Part(text=text)],metadata={"trace_id": trace_id})
    last = ""
    async for event in client.send_message(a2a_pb2.SendMessageRequest(message=msg)):
        print("  [event]", type(event).__name__)   # remove once verified
        last = event
    return str(last)


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

        t1 = time.time()
        result = await ask(AGENTS[target], text,trace_id)
        a2a_ms = (time.time() - t1) * 1000
        log_event(trace_id, "supervisor.a2a_call", target=target, latency_ms=a2a_ms)

        print("Bot:", result, "\n")

if __name__ == "__main__":
    asyncio.run(main())