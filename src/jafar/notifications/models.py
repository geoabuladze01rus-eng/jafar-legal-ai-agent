from dataclasses import dataclass
from enum import Enum


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    PUSH = "push"
    VOICE = "voice"


@dataclass(frozen=True)
class Notification:
    notification_id: str
    title: str
    body: str
    channel: NotificationChannel
    priority: str = "normal"
    matter_id: str | None = None
    deadline_id: str | None = None


@dataclass(frozen=True)
class NotificationPreference:
    channel: NotificationChannel
    enabled: bool = True
    minimum_priority: str = "normal"
