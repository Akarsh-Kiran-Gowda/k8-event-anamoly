# K8s Event Anomaly Detector

A day-1 MVP for streaming Kubernetes events, running lightweight anomaly detection, and visualizing findings in a React dashboard.

## Project Structure

```text
k8-event-anamoly/
├── backend/
│   ├── main.py
│   ├── collector.py
│   ├── parser.py
│   ├── detector.py
│   ├── storage.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       └── main.jsx
└── README.md
```

## Backend

### Install and Run

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend API URL: `http://127.0.0.1:8000`

### Endpoints

- `GET /healthz`: health probe
- `GET /events`: last 100 parsed Kubernetes events
- `GET /anomalies`: last 50 detected anomalies

### Detection Rules

- `CRITICAL`: event message contains `BackOff` or reason contains `Failed`
- `WARNING`: more than 5 recent `ScalingReplicaSet` events in rolling window
- `INFO`: rolling event buffer has more than 30 events

### Hardening Included

- Thread-safe in-memory storage for collector + API access
- Bounded buffers for events and anomalies
- Duplicate anomaly suppression in short windows
- Collector config fallback:
  - local kubeconfig first
  - in-cluster config second
  - collector stays disabled if neither is available

## Frontend

### Install and Run

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

The dashboard polls `http://127.0.0.1:8000/anomalies` every 3 seconds and shows severity cards for `CRITICAL`, `WARNING`, and `INFO`.

## Quick Smoke Check

1. Start backend.
2. Open `http://127.0.0.1:8000/healthz` and verify `{"status":"ok"}`.
3. Start frontend and open `http://127.0.0.1:5173`.
4. Confirm the dashboard shows polling status and updates anomaly cards.

## Notes

- This MVP intentionally uses in-memory storage.
- If your machine is not connected to a Kubernetes cluster, backend endpoints still run and return empty lists.
