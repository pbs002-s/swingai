"""A request ID on every request: returned in X-Request-ID and printed on every log line of that request,
so one complaint ("it failed at 10:42") can be matched to its log lines."""

import contextvars
import logging
import re
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_SAFE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")  # a client may send its own, but never anything that could forge a log line


def new_request_id(incoming: str | None) -> str:
    return incoming if incoming and _SAFE.match(incoming) else uuid.uuid4().hex


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def install_log_filter() -> None:
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdFilter())
