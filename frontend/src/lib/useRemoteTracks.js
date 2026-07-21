import { useEffect, useState } from "react";
import { RoomEvent } from "livekit-client";

// Tracks every remote participant's published tracks plus a live participant
// count, for any connected Room. Both the broadcast and watch pages need this
// (interactive viewers publish too, so the broadcaster has to render remote
// tracks now, not just the viewer).
export function useRemoteTracks(room) {
  const [tracks, setTracks] = useState([]);
  const [participantCount, setParticipantCount] = useState(0);

  useEffect(() => {
    if (!room) return;

    const updateCount = () => setParticipantCount(room.remoteParticipants.size);

    const onSubscribed = (track, publication, participant) => {
      setTracks((prev) =>
        prev.some((t) => t.sid === publication.trackSid)
          ? prev
          : [...prev, { sid: publication.trackSid, kind: track.kind, participant, track }]
      );
    };
    const onUnsubscribed = (_track, publication) => {
      setTracks((prev) => prev.filter((t) => t.sid !== publication.trackSid));
    };
    const onParticipantDisconnected = (participant) => {
      setTracks((prev) => prev.filter((t) => t.participant.identity !== participant.identity));
      updateCount();
    };

    room.on(RoomEvent.TrackSubscribed, onSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, onUnsubscribed);
    room.on(RoomEvent.ParticipantConnected, updateCount);
    room.on(RoomEvent.ParticipantDisconnected, onParticipantDisconnected);
    updateCount();

    // Tracks published before this hook attached (e.g. the broadcaster's
    // camera, already live when a viewer joins) are auto-subscribed by
    // LiveKit as part of connecting — that TrackSubscribed event can fire
    // before this effect runs, so seed from what's already there too.
    for (const participant of room.remoteParticipants.values()) {
      for (const publication of participant.trackPublications.values()) {
        if (publication.track) onSubscribed(publication.track, publication, participant);
      }
    }

    return () => {
      room.off(RoomEvent.TrackSubscribed, onSubscribed);
      room.off(RoomEvent.TrackUnsubscribed, onUnsubscribed);
      room.off(RoomEvent.ParticipantConnected, updateCount);
      room.off(RoomEvent.ParticipantDisconnected, onParticipantDisconnected);
      setTracks([]);
    };
  }, [room]);

  return { tracks, participantCount };
}
