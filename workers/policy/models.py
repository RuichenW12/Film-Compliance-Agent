"""Worker-internal policy records that are not shared A/B contracts."""

from pydantic import BaseModel, ConfigDict


class InternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyDiff(InternalModel):
    source_id: str
    previous_sha256: str
    current_sha256: str
    unified_diff: str
