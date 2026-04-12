import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";

const API_URL = "http://127.0.0.1:8000/anomalies";
const CLEAR_API_URL = "http://127.0.0.1:8000/clear";
const LOGIN_API_URL = "http://127.0.0.1:8000/login";
const POLL_INTERVAL_MS = 3000;
const MAX_VISIBLE_CARDS = 50;
const TOKEN_STORAGE_KEY = "k8-event-token";
const LOGIN_ROUTE = "/login";
const HOME_ROUTE = "/";
const TIME_ZONES = {
  INDIA: {
    label: "India",
    zone: "Asia/Kolkata",
  },
  US: {
    label: "US",
    zone: "America/New_York",
  },
  EU: {
    label: "EU",
    zone: "Europe/Berlin",
  },
  JP: {
    label: "Japan",
    zone: "Asia/Tokyo",
  },
};
const SEVERITY_META = {
  CRITICAL: {
    emoji: "🔴",
    label: "CRITICAL",
  },
  WARNING: {
    emoji: "🟡",
    label: "WARNING",
  },
  INFO: {
    emoji: "🔵",
    label: "INFO",
  },
};

function normalizeSeverity(value) {
  if (value === "CRITICAL" || value === "WARNING" || value === "INFO") {
    return value;
  }
  return "INFO";
}

function getAnomalyIdentity(anomaly) {
  const sourceEvent = String(anomaly.source_event || "").trim();
  if (sourceEvent) {
    return sourceEvent;
  }

  return `${String(anomaly.time || "")}|${String(anomaly.message || "")}|${String(anomaly.type || "")}`;
}

function formatTime(utcTime, zoneKey) {
  const timeString = String(utcTime || "");
  const date = new Date(timeString);

  if (Number.isNaN(date.getTime())) {
    return timeString || "Unknown time";
  }

  const zone = TIME_ZONES[zoneKey]?.zone || TIME_ZONES.INDIA.zone;
  return date.toLocaleString("en-US", {
    timeZone: zone,
    dateStyle: "medium",
    timeStyle: "medium",
  });
}

function LoginPage({ onLogin, loading, error }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [focus, setFocus] = useState("none");
  const [showPassword, setShowPassword] = useState(false);
  const [isBlinking, setIsBlinking] = useState(false);
  const [look, setLook] = useState({ x: 0, y: 0 });
  const pandaHeadRef = useRef(null);

  const handleMouseMove = useCallback((event) => {
    if (!pandaHeadRef.current) {
      return;
    }

    const rect = pandaHeadRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const relativeX = (event.clientX - centerX) / (rect.width / 2);
    const relativeY = (event.clientY - centerY) / (rect.height / 2);

    const clampedX = Math.max(-1, Math.min(1, relativeX));
    const clampedY = Math.max(-1, Math.min(1, relativeY));

    setLook({
      x: clampedX * 3.4,
      y: clampedY * 2.6,
    });
  }, []);

  const handleMouseLeave = () => {
    setLook({ x: 0, y: 0 });
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    void onLogin(username, password);
  };

  const isUsernameMode = focus === "username" || username.length > 0;
  const isPasswordFocus = focus === "password";
  const pandaEyeMode = showPassword ? "peek" : isPasswordFocus ? "closed" : "open";

  useEffect(() => {
    if (pandaEyeMode !== "open") {
      setIsBlinking(false);
      return undefined;
    }

    let cancelled = false;
    let blinkTimer = 0;
    let reopenTimer = 0;

    const scheduleBlink = () => {
      blinkTimer = window.setTimeout(
        () => {
          if (cancelled) {
            return;
          }

          setIsBlinking(true);
          reopenTimer = window.setTimeout(() => {
            if (cancelled) {
              return;
            }

            setIsBlinking(false);
            scheduleBlink();
          }, 160);
        },
        2400 + Math.random() * 2600
      );
    };

    scheduleBlink();

    return () => {
      cancelled = true;
      window.clearTimeout(blinkTimer);
      window.clearTimeout(reopenTimer);
    };
  }, [pandaEyeMode]);

  return (
    <div className="login-shell" onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}>
      <div className="glow glow-a" />
      <div className="glow glow-b" />

      <section className="login-layout">
        <section className="auth-card">
          <p className="eyebrow">Kubernetes Runtime Signals</p>
          <h1>Welcome Back</h1>
          <p className="subtitle">Sign in to continue. Demo credentials: admin/admin.</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="auth-label" htmlFor="username">
              Username or email
            </label>
            <input
              id="username"
              className="auth-input"
              value={username}
              onChange={(event) => {
                setUsername(event.target.value);
              }}
              onFocus={() => {
                setFocus("username");
              }}
              onBlur={() => {
                setFocus("none");
              }}
              autoComplete="username"
              required
            />

            <label className="auth-label" htmlFor="password">
              Password
            </label>
            <div className="password-row">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                className="auth-input auth-input-password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                }}
                onFocus={() => {
                  setFocus("password");
                }}
                onBlur={() => {
                  setFocus("none");
                }}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="show-pass-button"
                onMouseDown={(event) => {
                  event.preventDefault();
                }}
                onClick={() => {
                  setShowPassword((previous) => !previous);
                }}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>

            <p className="auth-tip">Tip: Panda follows your cursor, smiles for username, and protects password.</p>

            <button className="auth-button" type="submit" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </button>

            {error && <p className="auth-error">{error}</p>}
          </form>
        </section>

        <aside className="panda-stage">
          <div
            className={`panda-shell panda-eye-${pandaEyeMode} ${isUsernameMode ? "panda-smile" : ""} ${isBlinking ? "panda-blink" : ""}`}
            style={{
              "--look-x": `${look.x}px`,
              "--look-y": `${look.y}px`,
            }}
          >
            <div className="panda-head" ref={pandaHeadRef}>
              <span className="panda-ear panda-ear-left" />
              <span className="panda-ear panda-ear-right" />

              <div className="panda-face">
                <div className="eye-patch eye-patch-left">
                  <span className="panda-eye panda-eye-left">
                    <span className="pupil" />
                  </span>
                </div>
                <div className="eye-patch eye-patch-right">
                  <span className="panda-eye panda-eye-right">
                    <span className="pupil" />
                  </span>
                </div>
                <span className="panda-nose" />
                <span className="panda-mouth" />
              </div>

              <span className="panda-arm panda-arm-left" />
              <span className="panda-arm panda-arm-right" />
            </div>

            <div className="panda-body">
              <span className="panda-belly" />
            </div>

            <div className="panda-feet">
              <span className="panda-foot" />
              <span className="panda-foot" />
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY) || "");
  const [route, setRoute] = useState(() => (window.location.pathname === LOGIN_ROUTE ? LOGIN_ROUTE : HOME_ROUTE));

  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [clearing, setClearing] = useState(false);
  const [selectedZone, setSelectedZone] = useState("INDIA");
  const [autoScroll, setAutoScroll] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const seenIds = useRef(new Set());

  const navigate = useCallback((nextRoute) => {
    if (window.location.pathname !== nextRoute) {
      window.history.pushState({}, "", nextRoute);
    }
    setRoute(nextRoute);
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setRoute(window.location.pathname === LOGIN_ROUTE ? LOGIN_ROUTE : HOME_ROUTE);
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  useEffect(() => {
    if (!token && route !== LOGIN_ROUTE) {
      navigate(LOGIN_ROUTE);
      return;
    }

    if (token && route === LOGIN_ROUTE) {
      navigate(HOME_ROUTE);
    }
  }, [navigate, route, token]);

  useEffect(() => {
    if (!token || route === LOGIN_ROUTE) {
      return undefined;
    }

    let mounted = true;

    const fetchData = async () => {
      try {
        const response = await axios.get(API_URL, { timeout: 2500 });

        if (!mounted) {
          return;
        }

        const incoming = Array.isArray(response.data) ? response.data : [];
        const newOnes = incoming.filter((anomaly) => {
          const anomalyId = getAnomalyIdentity(anomaly);
          if (seenIds.current.has(anomalyId)) {
            return false;
          }

          seenIds.current.add(anomalyId);
          return true;
        });

        if (newOnes.length > 0) {
          const ordered = [...newOnes].reverse();
          setAnomalies((previous) => [...ordered, ...previous].slice(0, MAX_VISIBLE_CARDS));

          if (autoScroll) {
            window.scrollTo({ top: 0, behavior: "smooth" });
          }
        }

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
  }, [autoScroll, route, token]);

  const handleLogin = async (username, password) => {
    try {
      setAuthLoading(true);
      setAuthError("");

      const response = await axios.post(
        LOGIN_API_URL,
        {
          username,
          password,
        },
        { timeout: 2500 }
      );

      const nextToken = String(response.data?.token || "").trim();
      if (!nextToken) {
        setAuthError("Login failed. Please try again.");
        return;
      }

      localStorage.setItem(TOKEN_STORAGE_KEY, nextToken);
      setToken(nextToken);
      setAuthError("");
      setError("");
      setAnomalies([]);
      seenIds.current.clear();
      setLoading(true);
    } catch (requestError) {
      setAuthError("Invalid credentials. Use admin/admin.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken("");
    setAnomalies([]);
    setError("");
    setLastUpdated("");
    setLoading(true);
    seenIds.current.clear();
    navigate(LOGIN_ROUTE);
  };

  const handleClear = async () => {
    try {
      setClearing(true);
      await axios.post(CLEAR_API_URL, null, { timeout: 2500 });
      setAnomalies([]);
      seenIds.current.clear();
      setLastUpdated(new Date().toLocaleTimeString());
      setError("");
    } catch (requestError) {
      setError("Unable to clear in-memory data right now.");
    } finally {
      setClearing(false);
    }
  };

  if (!token || route === LOGIN_ROUTE) {
    return <LoginPage onLogin={handleLogin} loading={authLoading} error={authError} />;
  }

  return (
    <div className="page">
      <div className="glow glow-a" />
      <div className="glow glow-b" />

      <header className="hero">
        <p className="eyebrow">Kubernetes Runtime Signals</p>
        <h1>K8s Anomaly Radar</h1>
        <p className="subtitle">
          Live stream with incremental anomaly cards, timezone-aware timestamps, and operator controls.
        </p>

        <div className="meta-row">
          <span className={`pill ${error ? "pill-error" : "pill-ok"}`}>
            {error ? "Backend Disconnected" : "Polling Every 3s"}
          </span>
          <span className="pill pill-neutral">
            {lastUpdated ? `Updated ${lastUpdated}` : "Waiting for first payload"}
          </span>
          <label className="control-field" htmlFor="timezone-select">
            <span>Timezone</span>
            <select
              id="timezone-select"
              className="control-select"
              value={selectedZone}
              onChange={(event) => {
                setSelectedZone(event.target.value);
              }}
            >
              {Object.entries(TIME_ZONES).map(([key, config]) => (
                <option key={key} value={key}>
                  {config.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className={`toggle-button ${autoScroll ? "toggle-on" : "toggle-off"}`}
            onClick={() => {
              setAutoScroll((previous) => !previous);
            }}
          >
            Auto-scroll {autoScroll ? "ON" : "OFF"}
          </button>
          <button
            type="button"
            className="clear-button"
            onClick={() => {
              void handleClear();
            }}
            disabled={clearing}
          >
            {clearing ? "Clearing..." : "Clear Memory"}
          </button>
          <button type="button" className="logout-button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="content">
        {loading && <section className="state-card">Reading first anomaly snapshot...</section>}

        {!loading && error && <section className="state-card error-card">{error}</section>}

        {!loading && !anomalies.length && !error && (
          <section className="state-card">No anomalies detected yet.</section>
        )}

        <section className="grid">
          {anomalies.map((anomaly, index) => {
            const severity = normalizeSeverity(anomaly.type);
            const severityMeta = SEVERITY_META[severity];

            return (
              <article
                key={`${getAnomalyIdentity(anomaly)}-${index}`}
                className={`anomaly-card severity-${severity.toLowerCase()}`}
                style={{ animationDelay: `${index * 70}ms` }}
              >
                <div className="card-top">
                  <span className="severity-tag">{`${severityMeta.emoji} ${severityMeta.label}`}</span>
                  <span className="time-tag">{formatTime(anomaly.time, selectedZone)}</span>
                </div>
                <p className="message">{anomaly.message || "No message provided."}</p>
                {anomaly.source_event && <p className="source-tag">Source: {anomaly.source_event}</p>}
              </article>
            );
          })}
        </section>
      </main>
    </div>
  );
}

export default App;
