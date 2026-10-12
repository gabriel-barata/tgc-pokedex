from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Every table class lives on this base, so Atlas sees the whole schema."""

    type_annotation_map: ClassVar[dict[type, Any]] = {
        str: Text,
        datetime: DateTime(timezone=True),
    }
    metadata: ClassVar[MetaData] = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
