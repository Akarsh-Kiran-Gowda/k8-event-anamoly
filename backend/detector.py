from collections import deque
from threading import Lock
from time import monotonic
from typing import Any

from storage import add_anomaly
from ml.runtime import get_scorer

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


def _emit(alert_type: str, message: str, event_time: str, source_event: str) -> None:
    if not _should_emit(alert_type, message):
        return

    add_anomaly(
        {
            "type": alert_type,
            "message": message,
            "time": event_time,
            "source_event": source_event,
        }
    )


def detect(event: dict[str, Any]) -> None:
    with _state_lock:
        _recent_events.append(event)

        message = str(event.get("message", ""))
        reason = str(event.get("reason", ""))
        message_lower = message.lower()
        reason_lower = reason.lower()
        obj = str(event.get("object", "unknown"))
        event_time = str(event.get("timestamp", ""))
        source_event = str(event.get("event_id", "unknown"))

        is_oom_event = (
            reason_lower == "oomkilled"
            or "oomkilled" in message_lower
            or "oom kill" in message_lower
            or "out of memory" in message_lower
            or "oom" in message_lower
        )
        if is_oom_event:
            _emit(
                "CRITICAL",
                f"OOM Kill detected in {obj}",
                event_time,
                source_event,
            )

        # Catch common crash/restart patterns in event reason/message.
        if (
            "back-off" in message_lower
            or "backoff" in message_lower
            or "crashloop" in message_lower
            or "failed" in reason_lower
        ):
            _emit(
                "CRITICAL",
                f"CrashLoop detected in {obj}",
                event_time,
                source_event,
            )
        elif "unhealthy" in reason_lower or "probe failed" in message_lower:
            _emit(
                "WARNING",
                f"Health check failing in {obj}",
                event_time,
                source_event,
            )

        deploy_events = [
            e for e in _recent_events if "scalingreplicaset" in str(e.get("reason", "")).lower()
        ]
        if len(deploy_events) > 5:
            _emit(
                "WARNING",
                "Deployment spike detected",
                event_time,
                source_event,
            )

        if len(_recent_events) > 40:
            _emit(
                "INFO",
                "Unusual high event activity",
                event_time,
                source_event,
            )

        scorer = get_scorer()
        if scorer is not None:
            scorer.enqueue(event)
