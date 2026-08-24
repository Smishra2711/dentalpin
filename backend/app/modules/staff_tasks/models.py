"""StaffTask model — one handoff/task row on the clinic's board."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, TimestampMixin


class StaffTask(Base, TimestampMixin):
    """An internal task or handoff note between clinic staff members.

    Lifecycle: ``open`` → (optionally) ``claimed`` → ``done``, with
    ``cancelled`` as an escape hatch. ``assignee_id`` is optional while
    ``open`` — claiming assigns the claimer.
    """

    __tablename__ = "staff_tasks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")

    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
