import asyncio
from langchain_ollama import ChatOllama
from a2a.client import create_client
from a2a.types import a2a_pb2

llm = ChatOllama(model="qwen2.5:7b", temperature=0)
AGENTS = {"order": "http://localhost:9101", "inventory": "http://localhost:9102"}


def route(text: str) -> str:
    d = llm.invoke(
        f"Classify into one word, 'order' or 'inventory'.\nRequest: {text}\nOne word only."
    ).content.strip().lower()
    return "order" if "order" in d else "inventory"


async def ask(url: str, text: str) -> str:
    client = await create_client(url)
    msg = a2a_pb2.Message(
        message_id="m1", role=a2a_pb2.ROLE_USER, parts=[a2a_pb2.Part(text=text)])
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
        target = route(text)
        print(f"[routed to {target}_agent via A2A]")
        print("Bot:", await ask(AGENTS[target], text), "\n")

asyncio.run(main())