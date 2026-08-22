"""Customer schemas (staff-facing)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    company_name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)
    municipality: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    company_name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=100)
    municipality: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern=r"^(active|blocked)$")


class CustomerResponse(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    company_name: str | None
    address: str | None
    city: str | None
    municipality: str | None
    notes: str | None
    status: str
    user_id: UUID | None
    created_at: datetime
    updated_at: datetime
