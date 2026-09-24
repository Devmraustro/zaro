from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Commune(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical Algeria commune (district) reference data.

    Linked to a wilaya via ``wilaya_id``. Multilingual name support (en/fr/ar).
    These rows are the authoritative source for commune names; existing
    ``commune`` string columns on ``custom_requests`` are preserved as
    submission-time snapshots.
    """

    __tablename__ = "communes"
    __table_args__ = (
        UniqueConstraint("wilaya_id", "code", name="uq_communes_wilaya_code"),
        {"extend_existing": True},
    )

    wilaya_id: Mapped[str] = mapped_column(ForeignKey("wilayas.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_fr: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<Commune code={self.code} wilaya_id={self.wilaya_id} name_en={self.name_en!r}>"
