from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Insight(SQLModel, table=True):
    """Xano table `Insights` (id 9).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "insights"

    __table_args__ = (
        Index("ix_insights_created_at", 'created_at'),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    real_user_id: int = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    child_id: UUID = Field(default=None, nullable=False)  # access=public
    journey_id: UUID = Field(default=None, nullable=False)  # access=public
    status: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # xano enum ['processing', 'ready', 'failed']; str because '' occurs; access=public
    deep_text: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    summary_text: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    teaser_text: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    request_id: UUID = Field(default=None, nullable=False)  # access=public
    last_error: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    insights_api_payload: dict = Field(default=None, sa_column=Column(JSONB, server_default=text("'{}'"), nullable=False))  # access=public


class Journey(SQLModel, table=True):
    """Xano table `Journey` (id 8).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "journey"

    __table_args__ = (
        Index("ix_journey_created_at", 'created_at'),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    title: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    desc: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    number: int = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    image: str | None = None  # access=public
