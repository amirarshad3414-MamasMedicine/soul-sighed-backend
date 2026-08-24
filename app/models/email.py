from datetime import datetime

from sqlalchemy import Column, DateTime, Index, func, text
from sqlmodel import Field, SQLModel


class EmailMessage(SQLModel, table=True):
    """Xano table `Email` (id 12).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "email"

    __table_args__ = (
        Index("ix_email_created_at", 'created_at'),
    )

    id: int = Field(default=None, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    email: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    subject: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    html_content: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    timestamp: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=text("'epoch'"), nullable=False))  # access=public
    delivered: bool = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("false")})  # access=public
