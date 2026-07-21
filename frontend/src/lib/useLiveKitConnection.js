import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent } from "livekit-client";
import { fetchToken } from "./api.js";

export function useLiveKitConnection({ state, navigate, role, successStatus, errorFallback, onConnected }) {
  const roomRef = useRef(null);
  const [room, setRoom] = useState(null);
  const [status, setStatus] = useState("connecting");
  const [error, setError] = useState(null);

  /* oxlint-disable react-hooks/exhaustive-deps -- onConnected and errorFallback
     are page-defined closures intentionally excluded from deps to avoid
     reconnecting on every render */
  useEffect(() => {
    if (!state?.name || !state?.room) {
      navigate("/");
      return;
    }

    let cancelled = false;
    const r = new Room();
    roomRef.current = r;

    r.on(RoomEvent.Disconnected, () => setStatus("ended"));

    (async () => {
      try {
        const { token, ws_url: wsUrl } = await fetchToken({
          name: state.name,
          room: state.room,
          role,
        });
        if (cancelled) return;
        await r.connect(wsUrl, token);
        if (cancelled) return;
        if (onConnected) await onConnected(r);
        if (cancelled) return;
        setRoom(r);
        setStatus(successStatus);
      } catch (err) {
        console.error(err);
        setError(err.message || errorFallback || "Failed to connect");
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
      r.disconnect();
    };
  }, [state, navigate, role, successStatus]);
  /* oxlint-enable react-hooks/exhaustive-deps */

  return { room, status, error, roomRef };
}
