import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Track } from "livekit-client";
import { BROADCASTER_PREFIX } from "../lib/api.js";
import { useRemoteTracks } from "../lib/useRemoteTracks.js";
import { useLiveKitConnection } from "../lib/useLiveKitConnection.js";
import { AudioSink, VideoTile } from "../components/MediaTile.jsx";

export default function WatchPage() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const localVideoRef = useRef(null);
  const [camOn, setCamOn] = useState(false);
  const [micOn, setMicOn] = useState(false);

  const { room, status, error, roomRef } = useLiveKitConnection({
    state,
    navigate,
    role: "viewer",
    successStatus: "watching",
    errorFallback: "Failed to connect to stream",
  });

  const { tracks, participantCount } = useRemoteTracks(room);

  const toggleCamera = async () => {
    const r = roomRef.current;
    if (!r) return;
    const next = !camOn;
    await r.localParticipant.setCameraEnabled(next);
    setCamOn(next);
    if (next) {
      const pub = r.localParticipant.getTrackPublication(Track.Source.Camera);
      if (pub?.track && localVideoRef.current) pub.track.attach(localVideoRef.current);
    }
  };

  const toggleMic = async () => {
    const r = roomRef.current;
    if (!r) return;
    const next = !micOn;
    await r.localParticipant.setMicrophoneEnabled(next);
    setMicOn(next);
  };

  const leave = () => {
    roomRef.current?.disconnect();
    navigate("/");
  };

  const broadcasterVideo = tracks.find(
    (t) => t.kind === Track.Kind.Video && t.participant.identity.startsWith(BROADCASTER_PREFIX)
  );
  const guestVideos = tracks.filter(
    (t) => t.kind === Track.Kind.Video && t !== broadcasterVideo
  );
  const audioTracks = tracks.filter((t) => t.kind === Track.Kind.Audio);
  const isLive = status === "watching" && !!broadcasterVideo;

  return (
    <div className="page">
      <div className="stream-layout">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Watching "{state?.room}"</h2>
          {isLive ? (
            <span className="badge badge-live">
              <span className="dot" />
              Live &middot; {participantCount} in room
            </span>
          ) : (
            <span className="badge badge-off">Waiting for broadcaster…</span>
          )}
        </div>

        {error && <div className="error-banner">{error}</div>}

        {!broadcasterVideo && status === "watching" && (
          <div className="card muted" style={{ textAlign: "center", padding: 60, marginBottom: 16 }}>
            You're connected. The stream will appear here as soon as the broadcaster goes live.
          </div>
        )}

        {broadcasterVideo && (
          <VideoTile
            track={broadcasterVideo.track}
            label={broadcasterVideo.participant.name || broadcasterVideo.participant.identity}
            className="hero"
          />
        )}

        {audioTracks.map((t) => (
          <AudioSink key={t.sid} track={t.track} />
        ))}

        <div className="stream-actions">
          <button className="btn btn-outline" onClick={toggleCamera} disabled={status !== "watching"}>
            {camOn ? "Turn off camera" : "Turn on camera"}
          </button>
          <button className="btn btn-outline" onClick={toggleMic} disabled={status !== "watching"}>
            {micOn ? "Turn off mic" : "Turn on mic"}
          </button>
          <button className="btn btn-outline" onClick={leave} disabled={status === "ended"}>
            Leave
          </button>
        </div>

        {status === "connecting" && <p className="muted" style={{ marginTop: 12 }}>Connecting…</p>}
        {status === "ended" && <p className="muted" style={{ marginTop: 12 }}>Stream ended.</p>}

        {(guestVideos.length > 0 || camOn) && (
          <div className="viewers-grid" style={{ marginTop: 24 }}>
            {camOn && (
              <div className="video-tile">
                <video ref={localVideoRef} autoPlay playsInline muted />
                <span className="label">{state?.name} (you)</span>
              </div>
            )}
            {guestVideos.map((t) => (
              <VideoTile key={t.sid} track={t.track} label={t.participant.name || t.participant.identity} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
