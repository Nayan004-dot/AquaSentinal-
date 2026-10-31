"""Environment-based backend configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _parse_device_tokens(raw: str) -> dict[str, str]:
    """Parse DEVICE_TOKENS as DEVICE_ID=TOKEN;DEVICE_ID_2=TOKEN_2."""
    tokens: dict[str, str] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError("DEVICE_TOKENS entries must use DEVICE_ID=TOKEN format")
        device_id, token = item.split("=", 1)
        device_id, token = device_id.strip(), token.strip()
        if not device_id or not token:
            raise ValueError("DEVICE_TOKENS entries cannot contain blank IDs or tokens")
        tokens[device_id] = token
    return tokens


@dataclass(frozen=True)
class Settings:
    database_path: str = "data/aquasentinel.sqlite3"
    device_tokens: dict[str, str] = field(default_factory=dict)
    sampling_interval_seconds: int = 10
    device_stale_after_seconds: int = 120
    aggregation_late_arrival_seconds: int = 120
    aggregation_min_valid_coverage: float = 0.80
    aggregation_poll_seconds: int = 60
    max_history_days: int = 31
    default_history_limit: int = 500
    max_history_limit: int = 1000
    cors_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        origins = tuple(x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip())
        return cls(
            database_path=os.getenv("DATABASE_PATH", "data/aquasentinel.sqlite3"),
            device_tokens=_parse_device_tokens(os.getenv("DEVICE_TOKENS", "")),
            sampling_interval_seconds=max(1, int(os.getenv("SAMPLING_INTERVAL_SECONDS", "10"))),
            device_stale_after_seconds=max(1, int(os.getenv("DEVICE_STALE_AFTER_SECONDS", "120"))),
            aggregation_late_arrival_seconds=max(0, int(os.getenv("AGGREGATION_LATE_ARRIVAL_SECONDS", "120"))),
            aggregation_min_valid_coverage=min(1.0, max(0.0, float(os.getenv("AGGREGATION_MIN_VALID_COVERAGE", "0.80")))),
            aggregation_poll_seconds=max(5, int(os.getenv("AGGREGATION_POLL_SECONDS", "60"))),
            max_history_days=max(1, int(os.getenv("MAX_HISTORY_DAYS", "31"))),
            default_history_limit=max(1, int(os.getenv("DEFAULT_HISTORY_LIMIT", "500"))),
            max_history_limit=max(1, int(os.getenv("MAX_HISTORY_LIMIT", "1000"))),
            cors_origins=origins,
        )

    def resolved_database_path(self) -> Path:
        path = Path(self.database_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
