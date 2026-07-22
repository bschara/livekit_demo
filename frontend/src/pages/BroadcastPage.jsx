import { useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Track } from "livekit-client";
import { useRemoteTracks } from "../lib/useRemoteTracks.js";
import { useLiveKitConnection } from "../lib/useLiveKitConnection.js";
import { AudioSink, VideoTile } from "../components/MediaTile.jsx";
import { startRecording, stopRecording } from "../lib/api.js";

export default function BroadcastPage() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const [recording, setRecording] = useState(false);
  const [egressId, setEgressId] = useState(null);
  const [recordingBusy, setRecordingBusy] = useState(false);
  const [recordingError, setRecordingError] = useState(null);

  const { room, status, error, roomRef } = useLiveKitConnection({
    state,
    navigate,
    role: "broadcaster",
    successStatus: "live",
    errorFallback: "Failed to start broadcast",
    onConnected: async (r) => {
      await r.localParticipant.setCameraEnabled(true);
      await r.localParticipant.setMicrophoneEnabled(true);
      const camPub = r.localParticipant.getTrackPublication(Track.Source.Camera);
      if (camPub?.track && videoRef.current) {
        camPub.track.attach(videoRef.current);
      }
    },
  });

  const { tracks, participantCount } = useRemoteTracks(room);

  const toggleRecording = async () => {
    setRecordingBusy(true);
    setRecordingError(null);
    try {
      if (recording) {
        await stopRecording({ egressId });
        setRecording(false);
        setEgressId(null);
      } else {
        const res = await startRecording({ name: state?.name, room: state?.room });
        setEgressId(res.egress_id);
        setRecording(true);
      }
    } catch (err) {
      setRecordingError(err.message || "Recording action failed");
    } finally {
      setRecordingBusy(false);
    }
  };

  const endStream = () => {
    if (recording && egressId) stopRecording({ egressId }).catch(() => {});
    roomRef.current?.disconnect();
    navigate("/");
  };

  // Every remote participant is a viewer; some may have opted into camera/mic
  // to interact — their video/audio shows up here as guest tiles.
  const guestVideos = tracks.filter((t) => t.kind === Track.Kind.Video);
  const audioTracks = tracks.filter((t) => t.kind === Track.Kind.Audio);

  return (
    <div className="page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Broadcasting to "{state?.room}"</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {recording && (
            <span className="badge badge-live">
              <span className="dot" />
              Recording
            </span>
          )}
          {status === "live" && (
            <span className="badge badge-live">
              <span className="dot" />
              Live &middot; {participantCount} watching
            </span>
          )}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {recordingError && <div className="error-banner">{recordingError}</div>}

      <div className="video-tile hero">
        <video ref={videoRef} autoPlay playsInline muted />
        <span className="label">{state?.name} (you)</span>
      </div>

      {guestVideos.length > 0 && (
        <>
          <h3 style={{ marginTop: 24 }}>Interacting with you</h3>
          <div className="viewers-grid">
            {guestVideos.map((t) => (
              <VideoTile key={t.sid} track={t.track} label={t.participant.name || t.participant.identity} />
            ))}
          </div>
        </>
      )}

      {audioTracks.map((t) => (
        <AudioSink key={t.sid} track={t.track} />
      ))}

      <div style={{ marginTop: 20, display: "flex", gap: 12 }}>
        <button
          className="btn btn-outline"
          onClick={toggleRecording}
          disabled={status !== "live" || recordingBusy}
        >
          {recording ? "Stop recording" : "Start recording"}
        </button>
        <button className="btn btn-danger" onClick={endStream} disabled={status === "ended"}>
          End stream
        </button>
      </div>

      {status === "connecting" && <p className="muted" style={{ marginTop: 12 }}>Connecting to camera and mic…</p>}
      {status === "ended" && <p className="muted" style={{ marginTop: 12 }}>Stream ended.</p>}
    </div>
  );
}
