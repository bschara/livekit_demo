from rest_framework import serializers

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
