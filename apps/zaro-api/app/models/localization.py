from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProductLocalization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Display-field translations for a product (name + description).

    A row is one locale for one product. Locales: en / fr / ar.
    The canonical English row lives on ``products`` itself; localizations
    override name/description per locale and fall back to the base row.
    """

    __tablename__ = "product_localizations"
    __table_args__ = (UniqueConstraint("product_id", "locale", name="uq_product_localizations_product_id_locale"),)

    product_id: Mapped[object] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ProductLocalization product_id={self.product_id} locale={self.locale!r}>"


class CategoryLocalization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Display-field translations for a category (name + description)."""

    __tablename__ = "category_localizations"
    __table_args__ = (UniqueConstraint("category_id", "locale", name="uq_category_localizations_category_id_locale"),)

    category_id: Mapped[object] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CategoryLocalization category_id={self.category_id} locale={self.locale!r}>"
