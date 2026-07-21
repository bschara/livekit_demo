import { useEffect, useRef } from "react";

function useAttachTrack(track, ref) {
  useEffect(() => {
    const el = ref.current;
    if (el) track.attach(el);
    return () => track.detach(el);
  }, [track]);
}

export function VideoTile({ track, label, muted = false, className = "" }) {
  const ref = useRef(null);
  useAttachTrack(track, ref);
  return (
    <div className={`video-tile ${className}`}>
      <video ref={ref} autoPlay playsInline muted={muted} />
      <span className="label">{label}</span>
    </div>
  );
}

export function AudioSink({ track }) {
  const ref = useRef(null);
  useAttachTrack(track, ref);
  return <audio ref={ref} autoPlay />;
}
