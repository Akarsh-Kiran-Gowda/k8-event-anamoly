def parse_event(event):
    involved_object_name = "unknown"
    if event.involved_object and event.involved_object.name:
        involved_object_name = str(event.involved_object.name)

    return {
        "timestamp": str(event.event_time or event.last_timestamp or event.first_timestamp),
        "type": str(event.type or ""),
        "reason": str(event.reason or ""),
        "message": str(event.message or ""),
        "object": involved_object_name,
    }
