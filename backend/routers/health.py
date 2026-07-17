"""Health and service-discovery endpoints."""
from fastapi import APIRouter, Depends

from schemas.health import HealthResponse, ServiceInfoResponse
from config import Settings, get_settings

router = APIRouter(tags=["service"])


@router.get("/", response_model=ServiceInfoResponse)
def root(settings: Settings = Depends(get_settings)) -> ServiceInfoResponse:
    return ServiceInfoResponse(service=settings.app_name, status="ok", version=settings.api_version, docs="/docs")


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment)
