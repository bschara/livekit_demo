from unittest.mock import AsyncMock, MagicMock, patch

from rest_framework.test import APITestCase

from .models import Recording


class TokenViewBroadcasterCollisionTests(APITestCase):
    def _post(self, **overrides):
        payload = {"name": "Alice", "room": "test-room", "role": "broadcaster"}
        payload.update(overrides)
        return self.client.post("/api/token/", payload, format="json")

    @patch("streaming.views.TokenView._room_has_broadcaster", new_callable=AsyncMock)
    def test_broadcaster_blocked_when_room_already_live(self, mock_check):
        mock_check.return_value = True
        response = self._post()
        self.assertEqual(response.status_code, 409)
        self.assertIn("already has an active broadcaster", response.data["detail"])

    @patch("streaming.views.TokenView._room_has_broadcaster", new_callable=AsyncMock)
    def test_broadcaster_allowed_when_room_empty(self, mock_check):
        mock_check.return_value = False
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["identity"].startswith("broadcaster-"))

    @patch("streaming.views.TokenView._room_has_broadcaster", new_callable=AsyncMock)
    def test_viewer_not_subject_to_broadcaster_check(self, mock_check):
        response = self._post(role="viewer")
        self.assertEqual(response.status_code, 200)
        mock_check.assert_not_called()


class RecordingStartStopTests(APITestCase):
    @patch("streaming.views.RecordingStartView._start", new_callable=AsyncMock)
    def test_start_creates_recording(self, mock_start):
        mock_start.return_value = MagicMock(egress_id="EG_123")
        response = self.client.post(
            "/api/recordings/start/", {"name": "Alice", "room": "test-room"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["egress_id"], "EG_123")
        recording = Recording.objects.get(egress_id="EG_123")
        self.assertEqual(recording.status, "recording")
        self.assertEqual(recording.room, "test-room")

    @patch("streaming.views.RecordingStartView._start", new_callable=AsyncMock)
    def test_start_blocked_when_already_recording(self, mock_start):
        Recording.objects.create(
            room="test-room", broadcaster_name="Alice", egress_id="EG_1", status="recording"
        )
        response = self.client.post(
            "/api/recordings/start/", {"name": "Alice", "room": "test-room"}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        mock_start.assert_not_called()

    @patch("streaming.views.RecordingStopView._stop", new_callable=AsyncMock)
    def test_stop_marks_processing(self, mock_stop):
        Recording.objects.create(
            room="test-room", broadcaster_name="Alice", egress_id="EG_1", status="recording"
        )
        response = self.client.post("/api/recordings/stop/", {"egress_id": "EG_1"}, format="json")
        self.assertEqual(response.status_code, 204)
        mock_stop.assert_awaited_once_with("EG_1")
        recording = Recording.objects.get(egress_id="EG_1")
        self.assertEqual(recording.status, "processing")


class RecordingListTests(APITestCase):
    @patch("streaming.views._s3_client")
    def test_list_only_returns_ready_with_presigned_url(self, mock_s3_client):
        mock_s3_client.return_value.generate_presigned_url.return_value = "http://minio/signed-url"
        Recording.objects.create(
            room="r1",
            broadcaster_name="Alice",
            egress_id="EG_ready",
            status="ready",
            object_key="r1/foo.mp4",
        )
        Recording.objects.create(
            room="r2", broadcaster_name="Bob", egress_id="EG_recording", status="recording"
        )

        response = self.client.get("/api/recordings/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["room"], "r1")
        self.assertEqual(response.data[0]["url"], "http://minio/signed-url")


class LiveKitWebhookTests(APITestCase):
    def _post_webhook(self, event):
        with patch("streaming.views.api.WebhookReceiver") as mock_receiver_cls:
            mock_receiver_cls.return_value.receive.return_value = event
            return self.client.post(
                "/api/webhooks/livekit/",
                data=b"{}",
                content_type="application/webhook+json",
                HTTP_AUTHORIZATION="fake-token",
            )

    def test_egress_ended_marks_ready(self):
        from livekit import api as lk_api

        Recording.objects.create(
            room="r1", broadcaster_name="Alice", egress_id="EG_1", status="processing"
        )
        file_info = MagicMock(filename="r1/abc.mp4", duration=5_000_000_000, size=12345)
        event = MagicMock(
            event="egress_ended",
            egress_info=MagicMock(
                egress_id="EG_1",
                status=lk_api.EgressStatus.EGRESS_COMPLETE,
                file_results=[file_info],
            ),
        )

        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 204)
        recording = Recording.objects.get(egress_id="EG_1")
        self.assertEqual(recording.status, "ready")
        self.assertEqual(recording.object_key, "r1/abc.mp4")
        self.assertEqual(recording.duration_seconds, 5.0)
        self.assertEqual(recording.size_bytes, 12345)

    def test_egress_ended_event_but_aborted_marks_failed(self):
        """The webhook event type is "egress_ended" even when the egress
        aborted (e.g. an empty room with nothing to record) — only
        egress_info.status says whether it actually succeeded."""
        from livekit import api as lk_api

        Recording.objects.create(
            room="r1", broadcaster_name="Alice", egress_id="EG_9", status="processing"
        )
        event = MagicMock(
            event="egress_ended",
            egress_info=MagicMock(
                egress_id="EG_9",
                status=lk_api.EgressStatus.EGRESS_ABORTED,
                file_results=[],
            ),
        )

        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 204)
        recording = Recording.objects.get(egress_id="EG_9")
        self.assertEqual(recording.status, "failed")
        self.assertEqual(recording.object_key, "")

    def test_egress_failed_marks_failed(self):
        Recording.objects.create(
            room="r1", broadcaster_name="Alice", egress_id="EG_2", status="recording"
        )
        event = MagicMock(
            event="egress_failed",
            egress_info=MagicMock(egress_id="EG_2", file_results=[]),
        )

        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 204)
        recording = Recording.objects.get(egress_id="EG_2")
        self.assertEqual(recording.status, "failed")

    @patch("streaming.views.RecordingStopView._stop", new_callable=AsyncMock)
    def test_room_finished_stops_lingering_recording(self, mock_stop):
        Recording.objects.create(
            room="r1", broadcaster_name="Alice", egress_id="EG_3", status="recording"
        )
        event = MagicMock(event="room_finished")
        event.room.name = "r1"  # MagicMock(name=...) sets repr name, not an attribute

        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 204)
        mock_stop.assert_awaited_once_with("EG_3")
        recording = Recording.objects.get(egress_id="EG_3")
        self.assertEqual(recording.status, "processing")
