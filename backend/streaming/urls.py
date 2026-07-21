from django.urls import path

from .views import RoomListView, TokenView

urlpatterns = [
    path("token/", TokenView.as_view(), name="token"),
    path("rooms/", RoomListView.as_view(), name="rooms"),
]
