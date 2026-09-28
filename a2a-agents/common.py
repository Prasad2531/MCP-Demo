from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import a2a_pb2

MCP_URL = "http://localhost:8080/sse"
llm = ChatOllama(model="qwen2.5:7b", temperature=0.2)


async def build_agent(tool_names: list[str], system_prompt: str):
    client = MultiServerMCPClient({"ecommerce": {"transport": "sse", "url": MCP_URL}})
    tools = [t for t in await client.get_tools() if t.name in tool_names]
    return create_agent(llm, tools, system_prompt=system_prompt)


class LangChainAgentExecutor(AgentExecutor):
    """Bridges A2A requests to a LangChain agent."""

    def __init__(self, agent):
        self.agent = agent

    async def _status(self, ctx, queue, state, text=None):
        status = a2a_pb2.TaskStatus(state=state)
        if text:
            status.message.CopyFrom(a2a_pb2.Message(
                message_id=f"{ctx.task_id}-msg",
                role=a2a_pb2.ROLE_AGENT,
                parts=[a2a_pb2.Part(text=text)],
            ))
        await queue.enqueue_event(a2a_pb2.TaskStatusUpdateEvent(
            task_id=ctx.task_id, context_id=ctx.context_id, status=status))

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input()

        # A2A rule: enqueue the Task before any status updates
        if context.current_task is None:
            await event_queue.enqueue_event(a2a_pb2.Task(
                id=context.task_id,
                context_id=context.context_id,
                status=a2a_pb2.TaskStatus(state=a2a_pb2.TASK_STATE_SUBMITTED),
            ))

        await self._status(context, event_queue, a2a_pb2.TASK_STATE_WORKING)
        try:
            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": user_text}]})
            answer = result["messages"][-1].content
            await self._status(context, event_queue, a2a_pb2.TASK_STATE_COMPLETED, answer)
        except Exception as e:
            await self._status(context, event_queue, a2a_pb2.TASK_STATE_FAILED, str(e))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await self._status(context, event_queue, a2a_pb2.TASK_STATE_CANCELED)