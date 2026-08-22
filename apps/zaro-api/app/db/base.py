from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JSONType = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Fetch server-generated defaults (created_at/updated_at) during INSERT/
    # UPDATE via RETURNING instead of lazily on next attribute access.
    # Without this, reading ``updated_at`` after a commit triggers a
    # synchronous lazy load that explodes inside async (MissingGreenlet).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012 - SQLAlchemy requires a class-level mapping
