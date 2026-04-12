def parse_event(event):
    return {
        "timestamp": str(event.event_time or event.last_timestamp or event.first_timestamp),
        "type": event.type,
        "reason": event.reason,
        "message": event.message,
        "object": event.involved_object.name if event.involved_object else "unknown"
    }
