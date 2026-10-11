import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from tcg_pokedex.database import get_engine

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]


def database_is_reachable(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Health check could not reach the database", exc_info=True)
        return False
    return True


@router.get(
    "/healthz",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthStatus}},
)
def healthz(
    response: Response, engine: Annotated[Engine, Depends(get_engine)]
) -> HealthStatus:
    if database_is_reachable(engine):
        return HealthStatus(status="ok", database="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthStatus(status="degraded", database="unavailable")
