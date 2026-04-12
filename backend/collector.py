import hashlib
from collections import deque
from threading import Lock
from typing import Any

from kubernetes import client, config, watch
from parser import parse_event
from storage import add_event
from detector import detect

_PROCESSED_EVENT_WINDOW = 1000
_processed_queue: deque[str] = deque(maxlen=_PROCESSED_EVENT_WINDOW)
_processed_set: set[str] = set()
_processed_lock = Lock()


def generate_event_id(event: dict[str, Any]) -> str:
    raw = (
        f"{str(event.get('timestamp', ''))}-"
        f"{str(event.get('object', ''))}-"
        f"{str(event.get('reason', ''))}-"
        f"{str(event.get('message', ''))}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_new_event(event_id: str) -> bool:
    with _processed_lock:
        if event_id in _processed_set:
            return False

        if len(_processed_queue) == _PROCESSED_EVENT_WINDOW:
            old_event_id = _processed_queue.popleft()
            _processed_set.discard(old_event_id)

        _processed_queue.append(event_id)
        _processed_set.add(event_id)
        return True


def clear_processed_events() -> None:
    with _processed_lock:
        _processed_queue.clear()
        _processed_set.clear()


def _handle_event(parsed: dict[str, Any], prefix: str) -> None:
    event_id = generate_event_id(parsed)
    if not is_new_event(event_id):
        print(f"{prefix} DUPLICATE SKIPPED:", event_id)
        return

    event_with_id = dict(parsed)
    event_with_id["event_id"] = event_id

    print(f"{prefix} EVENT:", event_with_id)
    add_event(event_with_id)
    detect(event_with_id)

def start_collector():
    config.load_kube_config()

    v1 = client.CoreV1Api()

    print("🚀 Fetching existing events...")

    # ✅ STEP 1: Initial fetch (VERY IMPORTANT)
    try:
        events = v1.list_event_for_all_namespaces().items
        for e in events:
            parsed = parse_event(e)
            _handle_event(parsed, "INIT")

    except Exception as e:
        print("Initial fetch error:", e)

    print("🚀 Starting live event stream...")

    # ✅ STEP 2: Live stream
    w = watch.Watch()

    for event in w.stream(v1.list_event_for_all_namespaces):
        try:
            raw_event = event['object']
            parsed = parse_event(raw_event)
            _handle_event(parsed, "LIVE")

        except Exception as e:
            print("Stream error:", e)