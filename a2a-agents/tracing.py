import json
import time
import uuid
import logging

logger = logging.getLogger("trace")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("trace.log")
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


def new_trace_id() -> str:
    return str(uuid.uuid4())[:8]


def log_event(trace_id: str, span: str, **fields):
    """One structured JSON line per event, correlated by trace_id."""
    event = {
        "trace_id": trace_id,
        "span": span,
        "ts": time.time(),
        **fields,
    }
    logger.info(json.dumps(event))