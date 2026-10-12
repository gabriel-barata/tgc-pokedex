import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from tcg_pokedex.db import get_engine
from tcg_pokedex.schemas import HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/healthz",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthStatus}},
)
def healthz(
    response: Response, engine: Annotated[Engine, Depends(get_engine)]
) -> HealthStatus:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Health check could not reach the database", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="degraded", database="unavailable")
    return HealthStatus(status="ok", database="ok")
