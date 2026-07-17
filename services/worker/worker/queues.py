import json
from dataclasses import dataclass
from typing import Any

from supabase import Client


@dataclass(frozen=True)
class QueueMessage:
    message_id: int
    payload: dict[str, Any]


class QueueAdapter:
    def __init__(self, client: Client, visibility_seconds: int) -> None:
        self.client = client
        self.visibility_seconds = visibility_seconds

    def read(self, queue: str) -> list[QueueMessage]:
        function = {"ingestion": "read_ingestion_jobs", "generation": "read_generation_jobs"}[queue]
        rows = self.client.rpc(
            function,
            {"p_visibility_seconds": self.visibility_seconds, "p_limit": 1},
        ).execute().data or []
        messages: list[QueueMessage] = []
        for row in rows:
            payload = row["message"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                raise ValueError("Queue message payload must be an object.")
            messages.append(QueueMessage(message_id=int(row["message_id"]), payload=payload))
        return messages

    def archive(self, queue: str, message_id: int) -> None:
        function = {"ingestion": "archive_ingestion_job", "generation": "archive_generation_job"}[queue]
        self.client.rpc(function, {"p_message_id": message_id}).execute()

    def enqueue_course_planning(self, course_id: str, owner_id: str) -> None:
        self.client.rpc(
            "enqueue_course_planning",
            {"p_course_id": course_id, "p_owner_id": owner_id},
        ).execute()
