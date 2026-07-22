from django.urls import path

from .views import (
    LiveKitWebhookView,
    RecordingListView,
    RecordingStartView,
    RecordingStopView,
    RoomListView,
    TokenView,
)

urlpatterns = [
    path("token/", TokenView.as_view(), name="token"),
    path("rooms/", RoomListView.as_view(), name="rooms"),
    path("recordings/", RecordingListView.as_view(), name="recordings"),
    path("recordings/start/", RecordingStartView.as_view(), name="recordings-start"),
    path("recordings/stop/", RecordingStopView.as_view(), name="recordings-stop"),
    path("webhooks/livekit/", LiveKitWebhookView.as_view(), name="livekit-webhook"),
]
