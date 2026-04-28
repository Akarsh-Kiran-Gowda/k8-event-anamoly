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
- `POST /clear`: clears in-memory events and anomalies
- `POST /login`: returns a demo token for `admin/admin`
- `GET /ml/health`: ML status and last score snapshot

### Detection Rules

- `CRITICAL`: OOM kill events (`OOMKilled` reason or OOM patterns in message)
- `CRITICAL`: crash/restart patterns (`back-off`, `backoff`, `crashloop`) in message, or reason contains `Failed`
- `WARNING`: readiness/health issues (`Unhealthy` reason or `probe failed` in message)
- `WARNING`: more than 5 recent `ScalingReplicaSet` events in rolling window
- `INFO`: rolling event buffer has more than 40 events

### Hardening Included

- Thread-safe in-memory storage for collector + API access
- Bounded buffers for events and anomalies
- Duplicate anomaly suppression in short windows
- Collector config fallback:
  - local kubeconfig first
  - in-cluster config second
  - collector stays disabled if neither is available

### ML Detection (Conference-ready Baselines)

This project ships a hybrid ML detector that runs alongside rule-based alerts:

- TF-IDF + IsolationForest (rare event text patterns)
- N-gram sequence rarity model (rare event sequences)

The ML scorer runs in a background thread and emits anomalies with ML scores, without blocking the rule-based pipeline.

#### Train ML Models

```bash
cd backend
python -m ml.train_models --output-dir backend/ml/models
```

This downloads the dataset from: https://github.com/hkerma/kubernetes-event-dataset

#### Runtime

When model files exist in `backend/ml/models/`, the ML scorer auto-starts on backend startup and emits anomalies with:

- `ml_score`
- `ml_if_score`
- `ml_ngram_score`

You can override the ML threshold without retraining:

```bash
set ML_COMBINED_THRESHOLD=0.55
```

## Frontend

### Install and Run

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

Default login: `admin / admin`

The dashboard polls `http://127.0.0.1:8000/anomalies` every 3 seconds using incremental updates (only unseen anomalies are prepended), includes:

- timezone selector (`India`, `US`, `EU`, `Japan`)
- severity indicators (`CRITICAL`, `WARNING`, `INFO`)
- auto-scroll toggle
- clear memory action

## Quick Smoke Check

1. Start backend.
2. Open `http://127.0.0.1:8000/healthz` and verify `{"status":"ok"}`.
3. Start frontend and open `http://127.0.0.1:5173`.
4. Confirm the dashboard shows polling status and updates anomaly cards.

## Notes

- This MVP intentionally uses in-memory storage.
- If your machine is not connected to a Kubernetes cluster, backend endpoints still run and return empty lists.
