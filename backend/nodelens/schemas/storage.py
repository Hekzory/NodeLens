"""Response shapes for /api/health/storage."""

from __future__ import annotations

from pydantic import BaseModel


class TelemetrySize(BaseModel):
    total_bytes: int
    compressed_bytes: int
    uncompressed_bytes: int
    compression_ratio: float | None  # uncompressed / (uncompressed + compressed-on-disk)


class BudgetStatus(BaseModel):
    budget_bytes: int
    used_bytes: int
    used_percent: float


class StoragePolicyConfig(BaseModel):
    retention_days: int
    compression_after_days: int
    disk_budget_gb: int
    retention_check_interval_seconds: int


class StorageStats(BaseModel):
    telemetry: TelemetrySize
    budget: BudgetStatus
    config: StoragePolicyConfig
