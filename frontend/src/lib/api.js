const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Must match BROADCASTER_PREFIX in backend/streaming/views.py — identities are
// prefixed server-side so the UI can tell the host apart from viewers/guests.
export const BROADCASTER_PREFIX = "broadcaster-";

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    let detail;
    try {
      detail = JSON.parse(body).detail;
    } catch {
      // Not a JSON error body — fall through to the raw text below.
    }
    throw new Error(detail || `${options?.method || "GET"} ${path} failed (${res.status}): ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function fetchToken({ name, room, role }) {
  return request("/api/token/", {
    method: "POST",
    body: JSON.stringify({ name, room, role }),
  });
}

export function fetchRooms() {
  return request("/api/rooms/");
}

export function startRecording({ name, room }) {
  return request("/api/recordings/start/", {
    method: "POST",
    body: JSON.stringify({ name, room }),
  });
}

export function stopRecording({ egressId }) {
  return request("/api/recordings/stop/", {
    method: "POST",
    body: JSON.stringify({ egress_id: egressId }),
  });
}

export function fetchRecordings() {
  return request("/api/recordings/");
}
