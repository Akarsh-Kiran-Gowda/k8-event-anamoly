import { useEffect, useMemo, useState } from "react";
import axios from "axios";

const API_URL = "http://127.0.0.1:8000/anomalies";
const POLL_INTERVAL_MS = 3000;
const SEVERITY_RANK = {
  CRITICAL: 0,
  WARNING: 1,
  INFO: 2,
};

function normalizeSeverity(value) {
  if (value === "CRITICAL" || value === "WARNING" || value === "INFO") {
    return value;
  }
  return "INFO";
}

function App() {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");

  const sortedAnomalies = useMemo(() => {
    return [...anomalies].sort((left, right) => {
      const leftType = normalizeSeverity(left.type);
      const rightType = normalizeSeverity(right.type);

      if (SEVERITY_RANK[leftType] !== SEVERITY_RANK[rightType]) {
        return SEVERITY_RANK[leftType] - SEVERITY_RANK[rightType];
      }

      const leftTime = Date.parse(left.time || "") || 0;
      const rightTime = Date.parse(right.time || "") || 0;
      return rightTime - leftTime;
    });
  }, [anomalies]);

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        const response = await axios.get(API_URL, { timeout: 2500 });

        if (!mounted) {
          return;
        }

        setAnomalies(Array.isArray(response.data) ? response.data : []);
        setLastUpdated(new Date().toLocaleTimeString());
        setError("");
      } catch (requestError) {
        if (!mounted) {
          return;
        }

        setError("Dashboard cannot reach the backend right now.");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void fetchData();
    const timer = window.setInterval(fetchData, POLL_INTERVAL_MS);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="page">
      <div className="glow glow-a" />
      <div className="glow glow-b" />

      <header className="hero">
        <p className="eyebrow">Kubernetes Runtime Signals</p>
        <h1>K8s Anomaly Radar</h1>
        <p className="subtitle">
          Live stream of inferred cluster anomalies from Kubernetes events.
        </p>

        <div className="meta-row">
          <span className={`pill ${error ? "pill-error" : "pill-ok"}`}>
            {error ? "Backend Disconnected" : "Polling Every 3s"}
          </span>
          <span className="pill pill-neutral">
            {lastUpdated ? `Updated ${lastUpdated}` : "Waiting for first payload"}
          </span>
        </div>
      </header>

      <main className="content">
        {loading && (
          <section className="state-card">
            Reading first anomaly snapshot...
          </section>
        )}

        {!loading && error && <section className="state-card error-card">{error}</section>}

        {!loading && !sortedAnomalies.length && !error && (
          <section className="state-card">No anomalies detected yet.</section>
        )}

        <section className="grid">
          {sortedAnomalies.map((anomaly, index) => {
            const severity = normalizeSeverity(anomaly.type);

            return (
              <article
                key={`${anomaly.time || "unknown"}-${anomaly.message || "empty"}-${index}`}
                className={`anomaly-card severity-${severity.toLowerCase()}`}
                style={{ animationDelay: `${index * 70}ms` }}
              >
                <div className="card-top">
                  <span className="severity-tag">{severity}</span>
                  <span className="time-tag">{anomaly.time || "Unknown time"}</span>
                </div>
                <p className="message">{anomaly.message || "No message provided."}</p>
              </article>
            );
          })}
        </section>
      </main>
    </div>
  );
}

export default App;
