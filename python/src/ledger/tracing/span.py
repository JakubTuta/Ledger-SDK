import dataclasses
import enum
import time
import traceback
from typing import Any


class SpanKind(enum.Enum):
    SERVER = "server"
    CLIENT = "client"
    INTERNAL = "internal"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(enum.Enum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclasses.dataclass
class SpanEvent:
    name: str
    timestamp_ns: int
    attributes: dict[str, Any]


@dataclasses.dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind
    start_ns: int
    end_ns: int | None
    status: SpanStatus
    status_message: str | None
    attributes: dict[str, Any]
    events: list[SpanEvent]
    service_name: str

    def set_attr(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: SpanStatus, message: str | None = None) -> None:
        self.status = status
        if message is not None:
            self.status_message = message

    def record_exception(self, exc: Exception) -> None:
        event = SpanEvent(
            name="exception",
            timestamp_ns=time.time_ns(),
            attributes={
                "exception.type": exc.__class__.__name__,
                "exception.message": str(exc),
                "exception.stacktrace": "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ),
            },
        )
        self.events.append(event)

    def end(self) -> None:
        if self.end_ns is None:
            self.end_ns = time.time_ns()

    _KIND_TO_INT: dict[str, int] = {
        "internal": 0,
        "server": 1,
        "client": 2,
        "producer": 3,
        "consumer": 4,
    }
    _STATUS_TO_INT: dict[str, int] = {
        "unset": 0,
        "ok": 1,
        "error": 2,
    }

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id or "",
            "name": self.name,
            "kind": self._KIND_TO_INT[self.kind.value],
            "start_unix_nano": self.start_ns,
            "end_unix_nano": self.end_ns or self.start_ns,
            "status": self._STATUS_TO_INT[self.status.value],
            "status_message": self.status_message or "",
            "attributes": {k: str(v) for k, v in self.attributes.items()},
            "events": [
                {
                    "name": e.name,
                    "ts_unix_nano": e.timestamp_ns,
                    "attrs": {k: str(v) for k, v in e.attributes.items()},
                }
                for e in self.events
            ],
            "service_name": self.service_name,
        }
