import asyncio
import uvicorn
from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes, create_agent_card_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import a2a_pb2

from common import build_agent, LangChainAgentExecutor

PORT = 9101

card = a2a_pb2.AgentCard(
    name="Order Agent",
    description="Answers order status questions.",
    version="1.0.0",
    supported_interfaces=[a2a_pb2.AgentInterface(
        url=f"http://localhost:{PORT}/rpc",
        protocol_binding="JSONRPC",
        protocol_version="1.0",
    )],
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=a2a_pb2.AgentCapabilities(streaming=False),
    skills=[a2a_pb2.AgentSkill(
        id="order_status", name="Order status",
        description="Look up order status and total by order ID.",
        tags=["orders"], examples=["What's the status of order 1?"])],
)


async def make_app():
    agent = await build_agent(
        ["getOrderStatus"],
        "You handle order status questions only. Use getOrderStatus.")
    handler = DefaultRequestHandler(
        agent_executor=LangChainAgentExecutor(agent),
        task_store=InMemoryTaskStore(),
        agent_card=card)
    routes = create_jsonrpc_routes(handler, rpc_url="/rpc") + create_agent_card_routes(card)
    return Starlette(routes=routes)


if __name__ == "__main__":
    app = asyncio.run(make_app())
    uvicorn.run(app, host="0.0.0.0", port=PORT)