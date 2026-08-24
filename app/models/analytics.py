from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, text
from sqlmodel import Field, SQLModel


class OnboardingVisit(SQLModel, table=True):
    """Xano table `onboarding_visit` (id 13).

    `created_at` is a real timestamp column. Xano serialises it as epoch
    milliseconds on the wire — that conversion lives in the response
    schema. See xano-export/formats.md.
    """

    __tablename__ = "onboarding_visit"

    __table_args__ = (
        UniqueConstraint('session_id', 'flow', 'step', name="uq_onboarding_visit_session_id_flow_step"),
    )

    id: int = Field(default=None, primary_key=True)  # access=public
    created_at: datetime = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=text("'epoch'"), nullable=False))  # access=public
    session_id: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    flow: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    step: str = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("''")})  # access=public
    step_index: int = Field(default=None, nullable=False, sa_column_kwargs={"server_default": text("0")})  # access=public
