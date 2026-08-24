"""Environment configuration (API contract v1 section 8)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    google_cloud_project: str = ""
    region: str = "us-central1"
    firestore_emulator_host: str = ""
    pubsub_emulator_host: str = ""
    gcs_bucket: str = ""
    vertex_model_gemini: str = ""
    snapshot_seed_path: str = "policy/seed-snapshot-v1.yaml"
    internal_token: str = ""
    flag_veo_teaser: bool = False
    flag_us_track: bool = False
    store_backend: str = "memory"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            region=os.getenv("REGION", "us-central1"),
            firestore_emulator_host=os.getenv("FIRESTORE_EMULATOR_HOST", ""),
            pubsub_emulator_host=os.getenv("PUBSUB_EMULATOR_HOST", ""),
            gcs_bucket=os.getenv("GCS_BUCKET", ""),
            vertex_model_gemini=os.getenv("VERTEX_MODEL_GEMINI", ""),
            snapshot_seed_path=os.getenv(
                "SNAPSHOT_SEED_PATH", "policy/seed-snapshot-v1.yaml"
            ),
            internal_token=os.getenv("INTERNAL_TOKEN", ""),
            flag_veo_teaser=_flag("FLAG_VEO_TEASER"),
            flag_us_track=_flag("FLAG_US_TRACK"),
            store_backend=os.getenv("STORE_BACKEND", "memory"),
        )

    @property
    def snapshot_path(self) -> Path:
        path = Path(self.snapshot_seed_path)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def llm_configured(self) -> bool:
        return bool(self.google_cloud_project and self.vertex_model_gemini)
