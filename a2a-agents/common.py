from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import a2a_pb2
from tracing import log_event
import time
from failures import classify_exception, FailureReason

MCP_URL = "http://localhost:8080/sse"
llm = ChatOllama(model="qwen2.5:7b", temperature=0.2)

# in common.py, near the top
_mcp_failure_count = 0
_mcp_circuit_open_until = 0
MCP_FAILURE_THRESHOLD = 2
MCP_COOLDOWN_SECONDS = 15

def _mcp_circuit_is_open() -> bool:
    return time.time() < _mcp_circuit_open_until

def _record_mcp_failure():
    global _mcp_failure_count, _mcp_circuit_open_until
    _mcp_failure_count += 1
    if _mcp_failure_count >= MCP_FAILURE_THRESHOLD:
        _mcp_circuit_open_until = time.time() + MCP_COOLDOWN_SECONDS

def _record_mcp_success():
    global _mcp_failure_count
    _mcp_failure_count = 0

async def build_agent(tool_names: list[str], system_prompt: str, trace_id_holder: dict):
    client = MultiServerMCPClient({"ecommerce": {"transport": "sse", "url": MCP_URL}})
    raw_tools = [t for t in await client.get_tools() if t.name in tool_names]
    wrapped_tools = [wrap_tool_with_tracing(t, trace_id_holder) for t in raw_tools]
    return create_agent(llm, wrapped_tools, system_prompt=system_prompt)

def wrap_tool_with_tracing(tool, trace_id_holder: dict):
    original_coroutine = tool.coroutine

    async def traced_coroutine(*args, **kwargs):
        if _mcp_circuit_is_open():
                trace_id = trace_id_holder.get("current", "unknown")
                log_event(trace_id, "mcp.tool_call_error", tool=tool.name, args=kwargs,
                          error="circuit open, skipping call", reason=FailureReason.MCP_TOOL_ERROR.value, latency_ms=0)
                raise RuntimeError("MCP circuit breaker open — server recently failed")

        t0 = time.time()
        trace_id = trace_id_holder.get("current", "unknown")
        try:
            result = await original_coroutine(*args, **kwargs)
            _record_mcp_success()
            latency_ms = (time.time() - t0) * 1000
            log_event(trace_id, "mcp.tool_call", tool=tool.name, args=kwargs, latency_ms=latency_ms)
            return result
        except Exception as e:
            _record_mcp_failure()
            latency_ms = (time.time() - t0) * 1000
            reason = classify_exception(e)
            log_event(trace_id, "mcp.tool_call_error", tool=tool.name, args=kwargs,error=str(e), reason=reason.value, latency_ms=latency_ms)
            raise

    tool.coroutine = traced_coroutine
    return tool

class LangChainAgentExecutor(AgentExecutor):
    """Bridges A2A requests to a LangChain agent."""

    def __init__(self, agent, trace_id_holder: dict):
            self.agent = agent
            self.trace_id_holder = trace_id_holder

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
        try:
            trace_id = context.message.metadata["trace_id"]
        except (KeyError, TypeError):
            trace_id = "unknown"

        self.trace_id_holder["current"] = trace_id

        if context.current_task is None:
            await event_queue.enqueue_event(a2a_pb2.Task(
                id=context.task_id,
                context_id=context.context_id,
                status=a2a_pb2.TaskStatus(state=a2a_pb2.TASK_STATE_SUBMITTED),
            ))

        await self._status(context, event_queue, a2a_pb2.TASK_STATE_WORKING)

        # Check the circuit BEFORE spending any LLM reasoning time
        if _mcp_circuit_is_open():
            log_event(trace_id, "agent.tool_call_error", input=user_text,
                      error="MCP circuit breaker open — skipping LLM call entirely",
                      reason=FailureReason.MCP_TOOL_ERROR.value, latency_ms=0)
            await self._status(context, event_queue, a2a_pb2.TASK_STATE_FAILED,
                               "The order/inventory service is currently unavailable. Please try again shortly.")
            return

        t0 = time.time()
        try:
            result = await self.agent.ainvoke({"messages": [{"role": "user", "content": user_text}]})
            answer = result["messages"][-1].content
            latency_ms = (time.time() - t0) * 1000
            log_event(trace_id, "agent.tool_call", input=user_text, output=answer, latency_ms=latency_ms)
            await self._status(context, event_queue, a2a_pb2.TASK_STATE_COMPLETED, answer)
        except Exception as e:
            latency_ms = (time.time() - t0) * 1000
            reason = classify_exception(e)
            log_event(trace_id, "agent.tool_call_error", input=user_text, error=str(e), reason=reason.value, latency_ms=latency_ms)
            await self._status(context, event_queue, a2a_pb2.TASK_STATE_FAILED, str(e))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await self._status(context, event_queue, a2a_pb2.TASK_STATE_CANCELED)