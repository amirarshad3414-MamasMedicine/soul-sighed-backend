from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, UniqueConstraint, func, text
from sqlmodel import Field, SQLModel


class Child(SQLModel, table=True):
    """Xano table `children` (id 7).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "children"

    __table_args__ = (
        Index("ix_children_created_at", 'created_at'),
        # NOTE: user_01_id is NULL in every row and Postgres treats NULLs as distinct, so this never fires. add_children checks user_id instead. 52 duplicate rows exist today. Reproduced for parity — see triage.
        UniqueConstraint('user_01_id', 'name', 'date_of_birth', name="uq_children_user_01_id_name_date_of_birth"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))  # access=private
    user_01_id: UUID | None = None  # access=public
    user_id: int = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    name: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    date_of_birth: date | None = None  # access=public
    time_of_birth: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))  # access=public
    lat: float = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    lon: float = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
    pronoun: str | None = None  # access=public
    default_child: bool = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("false")})  # access=public
    relationship_focus: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("'child'")})  # xano enum ['child', 'parent']; str because '' occurs; access=public
