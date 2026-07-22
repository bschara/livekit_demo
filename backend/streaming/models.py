from django.db import models


class Recording(models.Model):
    STATUS_CHOICES = [
        ("recording", "Recording"),
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    room = models.CharField(max_length=64)
    broadcaster_name = models.CharField(max_length=64)
    egress_id = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="recording")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    object_key = models.CharField(max_length=512, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.room} @ {self.started_at:%Y-%m-%d %H:%M} ({self.status})"
