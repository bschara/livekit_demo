import asyncio
import uuid
from datetime import timedelta

from django.conf import settings
from livekit import api
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RoomSummarySerializer, TokenRequestSerializer, TokenResponseSerializer

BROADCASTER_PREFIX = "broadcaster-"


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
