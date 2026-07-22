import asyncio
import uuid
from datetime import timedelta

import boto3
from django.conf import settings
from django.utils import timezone
from livekit import api
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Recording
from .serializers import (
    RecordingSerializer,
    RecordingStartRequestSerializer,
    RecordingStopRequestSerializer,
    RoomSummarySerializer,
    TokenRequestSerializer,
    TokenResponseSerializer,
)

BROADCASTER_PREFIX = "broadcaster-"
# MinIO doesn't care about region, but boto3's S3 client requires one to be set.
S3_REGION = "us-east-1"


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name=S3_REGION,
    )


class TokenView(APIView):
    """Mint a short-lived, room-scoped LiveKit access token.

    Both roles get publish+subscribe grants, so a viewer can opt into camera/mic
    to interact with the broadcaster — "broadcaster" vs "viewer" is really just
    the identity prefix used to tell who's the host (see BROADCASTER_PREFIX)
    rather than a hard permission split. Django never proxies media itself —
    this is the only thing it does before the browser talks to LiveKit directly.
    """

    def post(self, request):
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        role = data["role"]
        room = data["room"]

        if role == "broadcaster" and asyncio.run(self._room_has_broadcaster(room)):
            return Response(
                {"detail": "This room already has an active broadcaster."},
                status=409,
            )

        # Suffix the identity so two viewers picking the same display name don't
        # collide (LiveKit requires a unique identity per participant per room).
        identity = f"{BROADCASTER_PREFIX if role == 'broadcaster' else 'viewer-'}{data['name']}-{uuid.uuid4().hex[:6]}"

        grants = api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )
        token = (
            api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(data["name"])
            .with_grants(grants)
            .with_ttl(timedelta(hours=2))
            .to_jwt()
        )

        response = TokenResponseSerializer(
            {
                "token": token,
                "ws_url": settings.LIVEKIT_WS_URL,
                "room": room,
                "identity": identity,
            }
        )
        return Response(response.data)

    @staticmethod
    async def _room_has_broadcaster(room_name):
        async with api.LiveKitAPI(
            settings.LIVEKIT_HTTP_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        ) as lk:
            listed = await lk.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
            if not listed.rooms:
                return False
            participants = await lk.room.list_participants(
                api.ListParticipantsRequest(room=room_name)
            )
            return any(
                p.identity.startswith(BROADCASTER_PREFIX) for p in participants.participants
            )


class RoomListView(APIView):
    """List currently active LiveKit rooms, flagging which ones have a broadcaster live.

    Lets the Watch page show "stream is live" vs "waiting for host" instead of
    guessing, without Django keeping any state of its own — LiveKit is the source
    of truth.
    """

    def get(self, request):
        rooms = asyncio.run(self._fetch_rooms())
        serializer = RoomSummarySerializer(rooms, many=True)
        return Response(serializer.data)

    @staticmethod
    async def _fetch_rooms():
        async with api.LiveKitAPI(
            settings.LIVEKIT_HTTP_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        ) as lk:
            listed = await lk.room.list_rooms(api.ListRoomsRequest())
            summaries = []
            for room in listed.rooms:
                participants = await lk.room.list_participants(
                    api.ListParticipantsRequest(room=room.name)
                )
                is_live = any(
                    p.identity.startswith(BROADCASTER_PREFIX) for p in participants.participants
                )
                summaries.append(
                    {
                        "name": room.name,
                        "num_participants": room.num_participants,
                        "is_live": is_live,
                    }
                )
            return summaries


class RecordingStartView(APIView):
    """Manually start a room-composite recording (broadcaster's Start recording
    button — see the frontend BroadcastPage). Records everything a viewer
    actually sees: the broadcaster plus any interacting guest tiles, via
    LiveKit's RoomCompositeEgress, uploaded straight to MinIO.
    """

    def post(self, request):
        serializer = RecordingStartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        room = data["room"]

        if Recording.objects.filter(room=room, status="recording").exists():
            return Response(
                {"detail": "This room already has a recording in progress."},
                status=409,
            )

        egress_info = asyncio.run(self._start(room))

        recording = Recording.objects.create(
            room=room,
            broadcaster_name=data["name"],
            egress_id=egress_info.egress_id,
        )
        return Response({"recording_id": recording.id, "egress_id": recording.egress_id})

    @staticmethod
    async def _start(room_name):
        async with api.LiveKitAPI(
            settings.LIVEKIT_HTTP_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        ) as lk:
            object_key = f"{room_name}/{uuid.uuid4().hex}.mp4"
            egress_request = api.RoomCompositeEgressRequest(
                room_name=room_name,
                file_outputs=[
                    api.EncodedFileOutput(
                        filepath=object_key,
                        s3=api.S3Upload(
                            access_key=settings.MINIO_ACCESS_KEY,
                            secret=settings.MINIO_SECRET_KEY,
                            bucket=settings.MINIO_BUCKET,
                            endpoint=settings.MINIO_INTERNAL_ENDPOINT,
                            region=S3_REGION,
                            force_path_style=True,
                        ),
                    )
                ],
            )
            return await lk.egress.start_room_composite_egress(egress_request)


class RecordingStopView(APIView):
    """Stop an in-progress recording. Final status/details are confirmed
    asynchronously via LiveKitWebhookView once the upload actually finishes.
    """

    def post(self, request):
        serializer = RecordingStopRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        egress_id = serializer.validated_data["egress_id"]

        asyncio.run(self._stop(egress_id))
        Recording.objects.filter(egress_id=egress_id).update(status="processing")
        return Response(status=204)

    @staticmethod
    async def _stop(egress_id):
        async with api.LiveKitAPI(
            settings.LIVEKIT_HTTP_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        ) as lk:
            await lk.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))


class RecordingListView(APIView):
    """List finished recordings with a time-limited presigned playback URL
    each — the bucket itself stays private.
    """

    def get(self, request):
        recordings = Recording.objects.filter(status="ready").exclude(object_key="")
        presigned_urls = {r.id: self._presigned_url(r.object_key) for r in recordings}
        serializer = RecordingSerializer(
            recordings, many=True, context={"presigned_urls": presigned_urls}
        )
        return Response(serializer.data)

    @staticmethod
    def _presigned_url(object_key):
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET, "Key": object_key},
            ExpiresIn=3600,
        )


class LiveKitWebhookView(APIView):
    """Receives LiveKit webhooks. Used for two things: learning when a
    recording's upload has actually finished (egress_ended/egress_failed —
    Egress confirms this asynchronously, not in the stop response), and as a
    safety net that stops any recording still running if its room ends first
    (room_finished), so a forgotten "Stop recording" click doesn't record
    indefinitely.
    """

    def post(self, request):
        verifier = api.TokenVerifier(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        receiver = api.WebhookReceiver(verifier)
        event = receiver.receive(
            request.body.decode("utf-8"), request.headers.get("Authorization", "")
        )

        if event.event in ("egress_ended", "egress_failed"):
            self._handle_egress_ended(event)
        elif event.event == "room_finished":
            self._handle_room_finished(event)

        return Response(status=204)

    @staticmethod
    def _handle_egress_ended(event):
        info = event.egress_info
        try:
            recording = Recording.objects.get(egress_id=info.egress_id)
        except Recording.DoesNotExist:
            return

        recording.ended_at = timezone.now()
        # The event type is "egress_ended" even when the egress failed or was
        # aborted (e.g. an empty room with nothing to record) — the actual
        # outcome is in egress_info.status, not the webhook event name.
        if info.status == api.EgressStatus.EGRESS_COMPLETE and info.file_results:
            file_info = info.file_results[0]
            recording.object_key = file_info.filename
            recording.duration_seconds = file_info.duration / 1e9
            recording.size_bytes = file_info.size
            recording.status = "ready"
        else:
            recording.status = "failed"
        recording.save()

    @staticmethod
    def _handle_room_finished(event):
        stuck = Recording.objects.filter(room=event.room.name, status="recording")
        for recording in stuck:
            asyncio.run(RecordingStopView._stop(recording.egress_id))
            recording.status = "processing"
            recording.save(update_fields=["status"])
