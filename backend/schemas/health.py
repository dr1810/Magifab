"""Stable Pydantic response schemas for the service foundation."""
from pydantic import BaseModel, ConfigDict


class ServiceInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: str
    status: str
    version: str
    docs: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    environment: str
