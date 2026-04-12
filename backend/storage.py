from threading import Lock
from typing import Any

_MAX_EVENTS = 100
_MAX_ANOMALIES = 50

_events: list[dict[str, Any]] = []
_anomalies: list[dict[str, Any]] = []
_store_lock = Lock()


def _trim(items: list[dict[str, Any]], limit: int) -> None:
    overflow = len(items) - limit
    if overflow > 0:
        del items[:overflow]


def add_event(event: dict[str, Any]) -> None:
    with _store_lock:
        _events.append(event)
        _trim(_events, _MAX_EVENTS)


def get_events() -> list[dict[str, Any]]:
    with _store_lock:
        return list(_events)


def add_anomaly(anomaly: dict[str, Any]) -> None:
    with _store_lock:
        _anomalies.append(anomaly)
        _trim(_anomalies, _MAX_ANOMALIES)


def get_anomalies() -> list[dict[str, Any]]:
    with _store_lock:
        return list(_anomalies)
