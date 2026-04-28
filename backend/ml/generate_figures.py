from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import requests

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATASET_URL = "https://raw.githubusercontent.com/hkerma/kubernetes-event-dataset/main/events-dataset.txt"


def load_dataset(url: str, limit: int | None = None) -> list[str]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    lines = [line.strip().lower() for line in response.text.splitlines() if line.strip()]
    if limit:
        return lines[:limit]
    return lines


def load_models(model_dir: Path) -> tuple[object, object, dict[str, object], dict[str, float]]:
    vectorizer = joblib.load(model_dir / "tfidf_vectorizer.joblib")
    isolation_forest = joblib.load(model_dir / "isolation_forest.joblib")
    ngram_model = joblib.load(model_dir / "ngram_model.joblib")
    meta = (model_dir / "meta.json").read_text(encoding="utf-8")
    return vectorizer, isolation_forest, ngram_model, json_load(meta)


def json_load(raw: str) -> dict[str, float]:
    import json

    return json.loads(raw)


def score_isolation_forest(vectorizer: object, isolation_forest: object, texts: list[str], meta: dict[str, float]) -> np.ndarray:
    matrix = vectorizer.transform(texts)
    raw_scores = -isolation_forest.decision_function(matrix)

    p5 = float(meta.get("if_p5", 0.0))
    p95 = float(meta.get("if_p95", max(p5 + 1e-6, 1.0)))
    normalized = (raw_scores - p5) / (p95 - p5)
    return np.clip(normalized, 0.0, 1.0)


def score_ngram(texts: list[str], ngram_model: dict[str, object], meta: dict[str, float]) -> np.ndarray:
    n = int(ngram_model.get("n", 3))
    counts = ngram_model.get("counts", {})
    total = int(ngram_model.get("total", 1))

    scores = []
    for text in texts:
        tokens = text.split()
        if len(tokens) < n:
            scores.append(0.0)
            continue

        key = " ".join(tokens[-n:])
        count = int(counts.get(key, 0))
        prob = (count + 1) / (total + len(counts) + 1)
        scores.append(-np.log(prob))

    scores = np.asarray(scores)
    p50 = float(meta.get("ngram_p50", 0.0))
    p95 = float(meta.get("ngram_p95", max(p50 + 1e-6, 1.0)))
    normalized = (scores - p50) / (p95 - p50)
    return np.clip(normalized, 0.0, 1.0)


def plot_score_distribution(combined: np.ndarray, threshold: float, output_path: Path) -> None:
    plt.figure(figsize=(7.5, 4.6))
    plt.hist(combined, bins=40, color="#0c7a84", alpha=0.8)
    plt.axvline(threshold, color="#d64545", linestyle="--", linewidth=2, label=f"Threshold {threshold:.2f}")
    plt.xlabel("Combined score")
    plt.ylabel("Event count")
    plt.title("Combined ML score distribution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_if_vs_ngram(if_scores: np.ndarray, ngram_scores: np.ndarray, threshold: float, output_path: Path) -> None:
    combined = np.maximum(if_scores, ngram_scores)
    mask = combined >= threshold

    plt.figure(figsize=(6.6, 5.4))
    plt.scatter(if_scores[~mask], ngram_scores[~mask], s=16, alpha=0.35, color="#7a8a93", label="Below threshold")
    plt.scatter(if_scores[mask], ngram_scores[mask], s=18, alpha=0.65, color="#d64545", label="Anomalous")
    plt.xlabel("IsolationForest score")
    plt.ylabel("N-gram rarity score")
    plt.title("IF vs N-gram score")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_threshold_curve(combined: np.ndarray, output_path: Path) -> None:
    thresholds = np.linspace(0.0, 1.0, 51)
    rates = [(combined >= t).mean() for t in thresholds]

    plt.figure(figsize=(7.2, 4.6))
    plt.plot(thresholds, rates, color="#0c7a84", linewidth=2)
    plt.xlabel("Threshold")
    plt.ylabel("Anomaly rate")
    plt.title("Anomaly rate vs threshold")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_rare_ngrams(ngram_model: dict[str, object], output_path: Path) -> None:
    counts = ngram_model.get("counts", {})
    if not counts:
        plt.figure(figsize=(7.2, 4.6))
        plt.text(0.5, 0.5, "No n-gram data available", ha="center", va="center")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(output_path, dpi=200)
        plt.close()
        return

    items = sorted(counts.items(), key=lambda item: (item[1], item[0]))[:12]
    labels = [key for key, _ in items]
    values = [int(value) for _, value in items]

    plt.figure(figsize=(8.2, 5.4))
    plt.barh(labels, values, color="#0c7a84")
    plt.xlabel("Occurrences")
    plt.title("Least frequent n-grams")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-url", default=DATASET_URL)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model-dir", default="backend/ml/models")
    parser.add_argument("--output-dir", default="docs/figures")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset_url, args.limit)
    repo_root = Path(__file__).resolve().parents[2]
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        candidate = repo_root / args.model_dir
        if candidate.exists():
            model_dir = candidate

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (repo_root / output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    vectorizer, isolation_forest, ngram_model, meta = load_models(model_dir)

    if_scores = score_isolation_forest(vectorizer, isolation_forest, dataset, meta)
    ngram_scores = score_ngram(dataset, ngram_model, meta)
    combined = np.maximum(if_scores, ngram_scores)

    threshold = float(meta.get("combined_threshold", 0.72))

    plot_score_distribution(combined, threshold, output_dir / "fig1-score-distribution.png")
    plot_if_vs_ngram(if_scores, ngram_scores, threshold, output_dir / "fig2-if-vs-ngram.png")
    plot_threshold_curve(combined, output_dir / "fig3-threshold-curve.png")
    plot_rare_ngrams(ngram_model, output_dir / "fig4-rare-ngrams.png")


if __name__ == "__main__":
    main()
