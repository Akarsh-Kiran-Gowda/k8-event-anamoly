from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import requests
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer

DATASET_URL = "https://raw.githubusercontent.com/hkerma/kubernetes-event-dataset/main/events-dataset.txt"


def load_dataset(url: str, limit: int | None = None) -> list[str]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    lines = [line.strip().lower() for line in response.text.splitlines() if line.strip()]
    if limit:
        return lines[:limit]
    return lines


def build_ngram_model(tokens: list[str], n: int = 3) -> dict[str, object]:
    counts: dict[str, int] = {}
    total = 0

    for idx in range(len(tokens) - n + 1):
        key = " ".join(tokens[idx : idx + n])
        counts[key] = counts.get(key, 0) + 1
        total += 1

    return {
        "n": n,
        "counts": counts,
        "total": total,
    }


def compute_ngram_rarity(tokens: list[str], model: dict[str, object]) -> np.ndarray:
    n = int(model["n"])
    counts = model["counts"]
    total = int(model["total"])

    scores = []
    for idx in range(len(tokens) - n + 1):
        key = " ".join(tokens[idx : idx + n])
        count = int(counts.get(key, 0))
        prob = (count + 1) / (total + len(counts) + 1)
        scores.append(-np.log(prob))

    return np.asarray(scores)


def train(dataset: list[str], output_dir: Path, contamination: float, random_state: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=2,
    )
    matrix = vectorizer.fit_transform(dataset)

    isolation_forest = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_state,
    )
    isolation_forest.fit(matrix)

    if_scores = -isolation_forest.decision_function(matrix)
    if_p5 = float(np.percentile(if_scores, 5))
    if_p95 = float(np.percentile(if_scores, 95))

    ngram_model = build_ngram_model(dataset, n=3)
    ngram_scores = compute_ngram_rarity(dataset, ngram_model)
    ngram_p50 = float(np.percentile(ngram_scores, 50)) if len(ngram_scores) else 0.0
    ngram_p95 = float(np.percentile(ngram_scores, 95)) if len(ngram_scores) else max(ngram_p50, 1.0)

    meta = {
        "model_version": "v1",
        "dataset_url": DATASET_URL,
        "dataset_size": len(dataset),
        "if_p5": if_p5,
        "if_p95": if_p95,
        "ngram_p50": ngram_p50,
        "ngram_p95": ngram_p95,
        "combined_threshold": 0.72,
    }

    joblib.dump(vectorizer, output_dir / "tfidf_vectorizer.joblib")
    joblib.dump(isolation_forest, output_dir / "isolation_forest.joblib")
    joblib.dump(ngram_model, output_dir / "ngram_model.joblib")

    with (output_dir / "meta.json").open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-url", default=DATASET_URL)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default="backend/ml/models")
    parser.add_argument("--contamination", type=float, default=0.02)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset_url, args.limit)
    train(dataset, Path(args.output_dir), args.contamination, args.random_state)


if __name__ == "__main__":
    main()
