from kubernetes import client, config

print("Loading kubeconfig...")
config.load_kube_config()

print("Creating client...")
v1 = client.CoreV1Api()

print("Fetching events...")
events = v1.list_event_for_all_namespaces().items

print("Total events:", len(events))

for e in events:
    print(e.message)