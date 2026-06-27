"""Request-scoped logging utilities.

A ``contextvars.ContextVar`` carries the current request's ID through every
log call on the same async task, without any explicit passing.

Usage
─────
  1. Middleware sets ``request_id_var.set(request_id)`` at the start of each
     request.
  2. ``RequestIdFilter`` reads the var and injects ``request_id`` into every
     ``LogRecord`` emitted on that task's context.
  3. The log format string references ``%(request_id)s`` to include the ID.

Outside request context (startup, background threads) the var returns ``"-"``
so the field is always present and the format string never raises.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar

# Holds the current request's short ID (8 hex chars) for the lifetime of the
# async task that is handling the request.  The default "-" marks log lines
# that originate outside any HTTP request (startup, background tasks, tests).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject ``request_id`` into every LogRecord.

    Install on the root logger once at startup so all child loggers inherit it:

        logging.getLogger().addFilter(RequestIdFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = request_id_var.get()
        return True
