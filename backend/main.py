import logging
import threading
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collector import clear_processed_events, start_collector
from storage import clear_anomalies, clear_events, get_anomalies, get_events

app = FastAPI(title="K8s Event Anomaly Detector", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    collector_thread = threading.Thread(
        target=start_collector,
        name="k8s-event-collector",
        daemon=True,
    )
    collector_thread.start()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
def events() -> list[dict[str, Any]]:
    return get_events()


@app.get("/anomalies")
def anomalies() -> list[dict[str, Any]]:
    return get_anomalies()


@app.post("/clear")
def clear() -> dict[str, str]:
    clear_anomalies()
    clear_events()
    clear_processed_events()
    return {"status": "cleared"}
