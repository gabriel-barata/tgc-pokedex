import logging

from fastapi import APIRouter, Response, status

from tcg_pokedex.controllers.dependencies import Database
from tcg_pokedex.models.health import database_reachable
from tcg_pokedex.views.health import HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/healthz",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthStatus}},
)
def healthz(response: Response, engine: Database) -> HealthStatus:
    if not database_reachable(engine):
        logger.warning("Health check could not reach the database")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="degraded", database="unavailable")
    return HealthStatus(status="ok", database="ok")
