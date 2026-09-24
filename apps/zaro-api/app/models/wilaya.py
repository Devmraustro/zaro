from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Wilaya(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical Algeria wilaya (province) reference data.

    Multilingual name support (en/fr/ar). These rows are the authoritative
    source for wilaya names; existing ``wilaya`` string columns on
    ``customers`` and ``custom_requests`` are preserved as submission-time
    snapshots.
    """

    __tablename__ = "wilayas"
    __table_args__ = (UniqueConstraint("code", name="uq_wilayas_code"),)

    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_fr: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<Wilaya code={self.code} name_en={self.name_en!r}>"
