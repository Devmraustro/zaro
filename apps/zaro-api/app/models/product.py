from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType
from app.models.enums import ProductStatus, StockStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    # Server-controlled human reference (ZAR-ATL-001). Clients can never set it.
    product_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[object | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Physical specifications
    dimensions: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # {width,height,depth,unit}
    materials_spec: Mapped[list | None] = mapped_column(JSONType, nullable=True)  # [{name, grade, finish}]
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    # Pricing: integer minor units (centimes). Never floats.
    # New drafts start at 0 (unpriced); publishing requires a positive price.
    selling_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")

    status: Mapped[ProductStatus] = mapped_column(String(20), index=True, nullable=False, default=ProductStatus.DRAFT)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    production_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_status: Mapped[StockStatus] = mapped_column(String(20), nullable=False, default=StockStatus.MADE_TO_ORDER)

    delivery_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    delivery_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_by: Mapped[object | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} code={self.product_code!r} status={self.status}>"


class ProductVariant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "product_variants"

    product_id: Mapped[object] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)  # "120cm / Black / Natural Wood"
    attributes: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # {size,color,finish}
    # Optional price override; falls back to the product selling price.
    price_override_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="DZD")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped[Product] = relationship(back_populates="variants")

    def __repr__(self) -> str:
        return f"<ProductVariant id={self.id} sku={self.sku!r}>"
