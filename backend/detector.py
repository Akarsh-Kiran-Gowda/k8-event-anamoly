from collections import deque
from threading import Lock
from time import monotonic
from typing import Any

from storage import add_anomaly

_recent_events: deque[dict[str, Any]] = deque(maxlen=50)
_last_alert_time: dict[tuple[str, str], float] = {}
_state_lock = Lock()
_DUPLICATE_SUPPRESSION_SECONDS = 10.0


def _should_emit(alert_type: str, message: str) -> bool:
    now = monotonic()
    key = (alert_type, message)
    previous = _last_alert_time.get(key)
    _last_alert_time[key] = now

    stale_after = _DUPLICATE_SUPPRESSION_SECONDS * 3
    stale_keys = [k for k, seen_at in _last_alert_time.items() if now - seen_at > stale_after]
    for stale_key in stale_keys:
        _last_alert_time.pop(stale_key, None)

    if previous is None:
        return True
    return now - previous >= _DUPLICATE_SUPPRESSION_SECONDS


def _emit(alert_type: str, message: str, event_time: str) -> None:
    if not _should_emit(alert_type, message):
        return

    add_anomaly(
        {
            "type": alert_type,
            "message": message,
            "time": event_time,
        }
    )


def detect(event: dict[str, Any]) -> None:
    with _state_lock:
        _recent_events.append(event)

        message = str(event.get("message", ""))
        reason = str(event.get("reason", ""))
        obj = str(event.get("object", "unknown"))
        event_time = str(event.get("timestamp", ""))

        if "BackOff" in message or "Failed" in reason:
            _emit(
                "CRITICAL",
                f"Crash detected in {obj}",
                event_time,
            )

        deploy_events = [e for e in _recent_events if "ScalingReplicaSet" in str(e.get("reason", ""))]
        if len(deploy_events) > 5:
            _emit(
                "WARNING",
                "Deployment spike detected",
                event_time,
            )

        if len(_recent_events) > 30:
            _emit(
                "INFO",
                "High event rate anomaly",
                event_time,
            )
