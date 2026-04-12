from kubernetes import client, config, watch
from parser import parse_event
from storage import add_event
from detector import detect

def start_collector():
    config.load_kube_config()

    v1 = client.CoreV1Api()

    print("🚀 Fetching existing events...")

    # ✅ STEP 1: Initial fetch (VERY IMPORTANT)
    try:
        events = v1.list_event_for_all_namespaces().items
        for e in events:
            parsed = parse_event(e)
            print("INIT EVENT:", parsed)

            add_event(parsed)
            detect(parsed)

    except Exception as e:
        print("Initial fetch error:", e)

    print("🚀 Starting live event stream...")

    # ✅ STEP 2: Live stream
    w = watch.Watch()

    for event in w.stream(v1.list_event_for_all_namespaces):
        try:
            raw_event = event['object']
            parsed = parse_event(raw_event)

            print("LIVE EVENT:", parsed)

            add_event(parsed)
            detect(parsed)

        except Exception as e:
            print("Stream error:", e)