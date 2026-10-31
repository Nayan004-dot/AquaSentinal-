"""Pydantic request/response schemas shared by the API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SensorStatus = Literal["valid", "invalid", "disconnected", "warming_up", "unavailable"]


class MeasurementBase(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    value: float | None
    status: SensorStatus
    calibrated: bool
    unit: str

    @model_validator(mode="after")
    def valid_measurement_requires_value(self):
        if self.status == "valid" and self.value is None:
            raise ValueError("A measurement with status='valid' must include a numeric value")
        return self


class TDSMeasurement(MeasurementBase):
    unit: Literal["ppm"]


class PHMeasurement(MeasurementBase):
    unit: Literal["pH"]


class TurbidityMeasurement(MeasurementBase):
    unit: Literal["NTU", "raw"]


class TemperatureMeasurement(MeasurementBase):
    unit: Literal["C"]


class OutletMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tds: TDSMeasurement
    ph: PHMeasurement
    turbidity: TurbidityMeasurement
    temperature: TemperatureMeasurement


class OutletTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    sequence: int = Field(ge=0)
    timestamp: datetime
    measurement_point: Literal["outlet"] = "outlet"
    firmware_version: str | None = Field(default=None, max_length=40)
    outlet: OutletMeasurements

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset or Z")
        return value.astimezone(timezone.utc)


class HealthResponse(BaseModel):
    status: str
    service: str
    api_version: str
