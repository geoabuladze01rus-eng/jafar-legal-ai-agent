from dataclasses import dataclass

from jafar.deadlines.reminders import Reminder
from jafar.notifications.models import Notification, NotificationChannel


_PRIORITY = {"normal": 0, "warning": 1, "urgent": 2, "critical": 3}


@dataclass(frozen=True)
class NotificationRouter:
    channels: tuple[NotificationChannel, ...] = (
        NotificationChannel.IN_APP,
        NotificationChannel.PUSH,
    )

    def route_deadline_reminder(self, reminder: Reminder, matter_id: str) -> list[Notification]:
        notifications: list[Notification] = []
        for channel in self.channels:
            notifications.append(
                Notification(
                    notification_id=f"deadline:{reminder.deadline_id}:{channel.value}:{reminder.level}",
                    title=f"Юридический срок: {reminder.level}",
                    body=reminder.message,
                    channel=channel,
                    priority=reminder.level,
                    matter_id=matter_id,
                    deadline_id=reminder.deadline_id,
                )
            )
        return notifications

    @staticmethod
    def should_voice(priority: str) -> bool:
        return _PRIORITY.get(priority, 0) >= _PRIORITY["critical"]
