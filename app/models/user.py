from typing import ClassVar
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Xano table `user` (id 1).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_created_at", 'created_at'),
        UniqueConstraint('email', name="uq_users_email"),
    )

    id: int = Field(default=None, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    name: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    email: str | None = None  # access=public
    password: str | None = None  # access=internal
    account_id: int = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    role: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # xano enum ['admin', 'member']; str because '' occurs; access=private
    # Xano's live auth/me returns password_reset as {token:"", expiration:null,
    # used:false}, never {} and never null (measured 2026-08-25). The three
    # sub-fields are visibility=internal but still appear, masked to their zero
    # values. Default to that exact shape so the port matches — a frontend
    # reading password_reset.used must not hit null.used on new accounts.
    password_reset: dict = Field(
        default_factory=lambda: {"token": "", "expiration": None, "used": False},
        sa_column=Column(JSONB, nullable=False, server_default=text(
            "'{\"token\":\"\",\"expiration\":null,\"used\":false}'")))  # access=public
    otp: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    otp_expiry: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=text("'epoch'"), nullable=False))  # access=public
    relationship_focus: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # xano enum ['parent', 'child']; str because '' occurs; access=public

    HIDDEN_FIELDS: ClassVar[list[str]] = ['password']


class LegacyUser(SQLModel, table=True):
    """Xano table `User_01` (id 6).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "user_01"

    __table_args__ = (
        Index("ix_user_01_created_at", 'created_at'),
        UniqueConstraint('memberstack_id', name="uq_user_01_memberstack_id"),
        UniqueConstraint('email', name="uq_user_01_email"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    name: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    memberstack_id: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    email: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    password: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    date_of_birth: date = Field(default=None, nullable=False)  # access=public
    time_of_birth: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=text("'epoch'"), nullable=False))  # access=public
    lat: float = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    lon: float = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    pronoun: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
