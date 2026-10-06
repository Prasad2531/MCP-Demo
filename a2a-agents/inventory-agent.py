import asyncio
import uvicorn
from starlette.applications import Starlette

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_jsonrpc_routes, create_agent_card_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import a2a_pb2

from common import build_agent, LangChainAgentExecutor

PORT = 9102

card = a2a_pb2.AgentCard(
    name="Inventory Agent",
    description="Product search and stock questions.",
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
        id="inventory", name="Inventory",
        description="Search products by name and check stock levels.",
        tags=["inventory"], examples=["Do you have wireless mice?"])],
)


async def make_app():
    trace_id_holder = {}
    agent = await build_agent(
        ["searchProducts", "checkInventory"],
        "You handle product search and stock questions. When the user names a product "
        "(e.g. 'mouse', 'keyboard', 'wireless mouse'), immediately call searchProducts "
        "with that product name as the query — do not ask for a product ID, the user "
        "won't have one. Only ask for clarification if no product name was mentioned at all.",
        trace_id_holder)
    handler = DefaultRequestHandler(
        agent_executor=LangChainAgentExecutor(agent,trace_id_holder),
        task_store=InMemoryTaskStore(),
        agent_card=card)
    routes = create_jsonrpc_routes(handler, rpc_url="/rpc") + create_agent_card_routes(card)
    return Starlette(routes=routes)


if __name__ == "__main__":
    app = asyncio.run(make_app())
    uvicorn.run(app, host="0.0.0.0", port=PORT)