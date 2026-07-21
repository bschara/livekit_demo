import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchRooms } from "../lib/api.js";

const DEFAULT_ROOM = "main-stream";

export default function HomePage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [room, setRoom] = useState(DEFAULT_ROOM);
  const [liveInfo, setLiveInfo] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const rooms = await fetchRooms();
        if (cancelled) return;
        setLiveInfo(rooms.find((r) => r.name === room) || null);
      } catch {
        // API not reachable yet — ignore, the form still works once it is.
      }
    };
    poll();
    const id = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [room]);

  const canSubmit = name.trim().length > 0 && room.trim().length > 0;

  const goTo = (path) => {
    if (!canSubmit) return;
    navigate(path, { state: { name: name.trim(), room: room.trim() } });
  };

  return (
    <div className="page" style={{ justifyContent: "center" }}>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <h1>LiveKit Broadcast POC</h1>
        <p className="muted">One broadcaster, unlimited viewers, powered by a LiveKit SFU.</p>
      </div>

      <div className="card" style={{ maxWidth: 420, margin: "0 auto", width: "100%" }}>
        <div className="field">
          <label htmlFor="name">Your name</label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Jamie"
            autoFocus
          />
        </div>
        <div className="field">
          <label htmlFor="room">Room</label>
          <input id="room" value={room} onChange={(e) => setRoom(e.target.value)} />
        </div>

        <div style={{ marginBottom: 16 }}>
          {liveInfo?.is_live ? (
            <span className="badge badge-live">
              <span className="dot" />
              Live now &middot; {liveInfo.num_participants} watching
            </span>
          ) : (
            <span className="badge badge-off">Nobody broadcasting yet</span>
          )}
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button className="btn" disabled={!canSubmit} onClick={() => goTo("/broadcast")}>
            Go live
          </button>
          <button
            className="btn btn-outline"
            disabled={!canSubmit}
            onClick={() => goTo("/watch")}
          >
            Watch stream
          </button>
        </div>
      </div>
    </div>
  );
}
