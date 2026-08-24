"""Validated policy.updated publication through Google Cloud Pub/Sub."""

from __future__ import annotations

from typing import Any

from schemas.policy_snapshot import PolicyUpdatedEvent


class PolicyEventPublishError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class PubSubEventPublisher:
    def __init__(self, publisher: Any, topic_path: str) -> None:
        self._publisher = publisher
        self._topic_path = topic_path

    @classmethod
    def from_project(
        cls,
        project: str,
        topic: str,
    ) -> "PubSubEventPublisher":
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient()
        return cls(publisher, publisher.topic_path(project, topic))

    def publish(self, event: PolicyUpdatedEvent) -> str:
        try:
            future = self._publisher.publish(
                self._topic_path,
                event.model_dump_json().encode("utf-8"),
            )
            message_id = future.result(timeout=30)
            if not isinstance(message_id, str) or not message_id:
                raise ValueError("empty Pub/Sub message id")
            return message_id
        except Exception as exc:
            raise PolicyEventPublishError(
                "POLICY_EVENT_PUBLISH_FAILED",
                "policy event could not be published",
            ) from exc
