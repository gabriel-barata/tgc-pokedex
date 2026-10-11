from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthStatus(BaseModel):
    status: Literal["ok"]


@router.get("/healthz")
def healthz() -> HealthStatus:
    return HealthStatus(status="ok")
