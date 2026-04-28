from __future__ import annotations

import json
import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import joblib
    import numpy as np
except Exception:  # pragma: no cover - optional dependency guard
    joblib = None
    np = None

from storage import add_anomaly


@dataclass(frozen=True)
class ModelBundle:
    vectorizer: Any
    isolation_forest: Any
    ngram_model: dict[str, Any]
    meta: dict[str, Any]


class MLScorer:
    def __init__(self, model_dir: Path, queue_size: int = 512) -> None:
        self._model_dir = model_dir
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._bundle = self._load_models()
        self._processed = 0
        self._emitted = 0
        self._last_scores: dict[str, float] | None = None

    @property
    def enabled(self) -> bool:
        return self._bundle is not None

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run, name="ml-scorer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def enqueue(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return

        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Drop when overloaded to avoid backpressure on core pipeline.
            return

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model_dir": str(self._model_dir),
            "processed": self._processed,
            "emitted": self._emitted,
            "queue_size": self._queue.qsize(),
            "meta": self._bundle.meta if self._bundle else {},
            "last_scores": self._last_scores or {},
        }

    def _load_models(self) -> ModelBundle | None:
        if joblib is None or np is None:
            return None

        vectorizer_path = self._model_dir / "tfidf_vectorizer.joblib"
        if_path = self._model_dir / "isolation_forest.joblib"
        ngram_path = self._model_dir / "ngram_model.joblib"
        meta_path = self._model_dir / "meta.json"

        if not (vectorizer_path.exists() and if_path.exists() and ngram_path.exists() and meta_path.exists()):
            return None

        try:
            vectorizer = joblib.load(vectorizer_path)
            isolation_forest = joblib.load(if_path)
            ngram_model = joblib.load(ngram_path)
            with meta_path.open("r", encoding="utf-8") as handle:
                meta = json.load(handle)
            return ModelBundle(vectorizer, isolation_forest, ngram_model, meta)
        except Exception:
            return None

    def _run(self) -> None:
        if not self._bundle:
            return

        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.4)
            except queue.Empty:
                continue

            try:
                self._score_event(event)
            except Exception:
                continue

    def _score_event(self, event: dict[str, Any]) -> None:
        if not self._bundle:
            return

        text = _event_text(event)
        if not text:
            return

        if_score = _score_isolation_forest(self._bundle, text)
        ngram_score = _score_ngram(self._bundle, text)
        combined = max(if_score, ngram_score)

        self._processed += 1
        self._last_scores = {
            "combined": round(combined, 4),
            "if_score": round(if_score, 4),
            "ngram_score": round(ngram_score, 4),
        }

        threshold = float(
            os.getenv(
                "ML_COMBINED_THRESHOLD",
                self._bundle.meta.get("combined_threshold", 0.72),
            )
        )
        if combined < threshold:
            return

        source_event = str(event.get("event_id", "unknown"))
        event_time = str(event.get("timestamp", ""))
        obj = str(event.get("object", "unknown"))

        add_anomaly(
            {
                "type": "WARNING",
                "message": f"ML anomaly detected in {obj}",
                "time": event_time,
                "source_event": source_event,
                "ml_score": round(combined, 4),
                "ml_if_score": round(if_score, 4),
                "ml_ngram_score": round(ngram_score, 4),
                "ml_model": self._bundle.meta.get("model_version", "v1"),
                "ml_threshold": round(threshold, 4),
            }
        )
        self._emitted += 1


def _event_text(event: dict[str, Any]) -> str:
    parts = [
        str(event.get("reason", "")),
        str(event.get("message", "")),
        str(event.get("object", "")),
        str(event.get("type", "")),
    ]
    return " ".join(part for part in parts if part).strip().lower()


def _score_isolation_forest(bundle: ModelBundle, text: str) -> float:
    if np is None:
        return 0.0

    vector = bundle.vectorizer.transform([text])
    raw_scores = -bundle.isolation_forest.decision_function(vector)
    raw = float(raw_scores[0])

    p5 = float(bundle.meta.get("if_p5", 0.0))
    p95 = float(bundle.meta.get("if_p95", max(p5 + 1e-6, 1.0)))
    normalized = (raw - p5) / (p95 - p5)
    return float(np.clip(normalized, 0.0, 1.0))


def _score_ngram(bundle: ModelBundle, text: str) -> float:
    if np is None:
        return 0.0

    ngram = bundle.ngram_model
    n = int(ngram.get("n", 3))
    counts = ngram.get("counts", {})
    total = int(ngram.get("total", 1))

    tokens = text.split()
    if len(tokens) < n:
        return 0.0

    key = " ".join(tokens[-n:])
    count = int(counts.get(key, 0))
    prob = (count + 1) / (total + len(counts) + 1)
    rarity = -np.log(prob)

    p50 = float(bundle.meta.get("ngram_p50", 0.0))
    p95 = float(bundle.meta.get("ngram_p95", max(p50 + 1e-6, 1.0)))
    normalized = (rarity - p50) / (p95 - p50)
    return float(np.clip(normalized, 0.0, 1.0))


_default_scorer: MLScorer | None = None


def get_scorer() -> MLScorer | None:
    return _default_scorer


def start_scorer(model_dir: Path) -> None:
    global _default_scorer

    if _default_scorer is None:
        _default_scorer = MLScorer(model_dir)

    _default_scorer.start()
