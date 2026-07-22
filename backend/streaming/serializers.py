from rest_framework import serializers

from .models import Recording

ROOM_NAME_RE = r"^[A-Za-z0-9_\-]{1,64}$"


class TokenRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, trim_whitespace=True)
    room = serializers.RegexField(ROOM_NAME_RE, max_length=64)
    role = serializers.ChoiceField(choices=["broadcaster", "viewer"])


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    ws_url = serializers.CharField()
    room = serializers.CharField()
    identity = serializers.CharField()


class RoomSummarySerializer(serializers.Serializer):
    name = serializers.CharField()
    num_participants = serializers.IntegerField()
    is_live = serializers.BooleanField()


class RecordingStartRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, trim_whitespace=True)
    room = serializers.RegexField(ROOM_NAME_RE, max_length=64)


class RecordingStopRequestSerializer(serializers.Serializer):
    egress_id = serializers.CharField(max_length=128)


class RecordingSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = [
            "id",
            "room",
            "broadcaster_name",
            "status",
            "started_at",
            "ended_at",
            "duration_seconds",
            "size_bytes",
            "url",
        ]

    def get_url(self, obj):
        return self.context.get("presigned_urls", {}).get(obj.id)
