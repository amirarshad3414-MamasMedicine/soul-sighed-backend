from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, func, text
from sqlmodel import Field, SQLModel


class Purchase(SQLModel, table=True):
    """Xano table `Purchases` (id 10).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "purchases"

    __table_args__ = (
        Index("ix_purchases_created_at", 'created_at'),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    user_id: int | None = None  # access=public
    child_id: UUID | None = None  # access=public
    journey_id: UUID = Field(default=None, nullable=False)  # access=public
    purchase_source: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    purchase_reference: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    email: str | None = None  # access=public
