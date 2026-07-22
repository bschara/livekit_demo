import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchRecordings } from "../lib/api.js";

function formatDuration(seconds) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function RecordingsPage() {
  const [recordings, setRecordings] = useState(null);
  const [error, setError] = useState(null);
  const [playingId, setPlayingId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchRecordings()
      .then((data) => !cancelled && setRecordings(data))
      .catch((err) => !cancelled && setError(err.message || "Failed to load recordings"));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Recordings</h2>
        <Link className="btn btn-outline" to="/">
          Home
        </Link>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {recordings === null && !error && <p className="muted">Loading…</p>}

      {recordings?.length === 0 && (
        <div className="card muted" style={{ textAlign: "center", padding: 60 }}>
          No recordings yet. Recordings started from the Broadcast page will show up here
          once they finish processing.
        </div>
      )}

      {recordings?.map((rec) => (
        <div key={rec.id} className="card" style={{ marginBottom: 12, textAlign: "left" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong>{rec.room}</strong>{" "}
              <span className="muted">by {rec.broadcaster_name}</span>
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                {new Date(rec.started_at).toLocaleString()} &middot;{" "}
                {formatDuration(rec.duration_seconds)}
              </div>
            </div>
            <button
              className="btn btn-outline"
              onClick={() => setPlayingId(playingId === rec.id ? null : rec.id)}
            >
              {playingId === rec.id ? "Hide" : "Watch"}
            </button>
          </div>
          {playingId === rec.id && (
            <video
              controls
              src={rec.url}
              style={{ width: "100%", marginTop: 16, borderRadius: 8, background: "#000" }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
