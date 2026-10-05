from enum import Enum


class FailureReason(str, Enum):
    MCP_TIMEOUT = "mcp_timeout"
    MCP_TOOL_ERROR = "mcp_tool_error"
    A2A_TASK_FAILURE = "a2a_task_failure"
    AGENT_CARD_STALE = "agent_card_stale"
    LLM_MALFORMED_OUTPUT = "llm_malformed_output"
    UNKNOWN = "unknown"


def classify_exception(exc: Exception) -> FailureReason:
    """Map a raw exception to a structured failure reason, looking inside
    ExceptionGroups since anyio/asyncio TaskGroups wrap the real cause."""

    # Unwrap ExceptionGroup (Python 3.11+) to inspect the actual sub-exceptions
    exceptions_to_check = [exc]
    if hasattr(exc, "exceptions"):  # BaseExceptionGroup / ExceptionGroup
        exceptions_to_check = list(exc.exceptions)

    for e in exceptions_to_check:
        name = type(e).__name__
        message = str(e).lower()

        if "timeout" in name.lower() or "timeout" in message:
            return FailureReason.MCP_TIMEOUT
        if "connect" in message or "connection" in message or "refused" in message:
            return FailureReason.MCP_TOOL_ERROR
        if "jsonrpc" in message or "invalidagentresponse" in name.lower():
            return FailureReason.A2A_TASK_FAILURE
        if "card" in message and ("stale" in message or "resolution" in name.lower()):
            return FailureReason.AGENT_CARD_STALE
        if "json" in message and ("parse" in message or "decode" in message):
            return FailureReason.LLM_MALFORMED_OUTPUT

    return FailureReason.UNKNOWN
