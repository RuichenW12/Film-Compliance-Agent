from datetime import datetime, timezone

from workers.policy.interfaces import PolicyRepository
from workers.policy.repository import InMemoryPolicyRepository


NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)


def test_in_memory_repository_works_through_composed_protocol() -> None:
    repository: PolicyRepository = InMemoryPolicyRepository()

    repository.create_run("run_protocol", "nrta_micro_drama", NOW)

    assert repository.get_run("run_protocol").status == "running"
