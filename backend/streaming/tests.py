from unittest.mock import AsyncMock, patch

from rest_framework.test import APITestCase


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
