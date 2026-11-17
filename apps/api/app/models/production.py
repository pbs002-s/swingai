"""Production entries and needle traceability."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductionEntry(Base):
    __tablename__ = "production_entries"
    __table_args__ = (Index("ix_production_station_period", "station_id", "period_start"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id"))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    qty_accepted: Mapped[int] = mapped_column(Integer)
    qty_rework: Mapped[int] = mapped_column(Integer, default=0)
    qty_rejected: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16))  # manual | sensor | simulator | import
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | confirmed
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class NeedleSupplier(Base):
    __tablename__ = "needle_suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class NeedleBatch(Base):
    __tablename__ = "needle_batches"
    __table_args__ = (UniqueConstraint("supplier_id", "lot_no"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("needle_suppliers.id"), index=True)
    lot_no: Mapped[str] = mapped_column(String(48))
    model: Mapped[str] = mapped_column(String(64))  # e.g. "DBx1 · Nm 90 · SES"
    received_on: Mapped[date] = mapped_column(Date)
    qty_received: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | quarantined | exhausted


class NeedleIssue(Base):
    """One needle installed on one machine, until it is removed."""

    __tablename__ = "needle_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("needle_batches.id"), index=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removal_reason: Mapped[str | None] = mapped_column(String(16))  # broken | routine | worn | other


class NeedleEvent(Base):
    __tablename__ = "needle_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    needle_issue_id: Mapped[int] = mapped_column(ForeignKey("needle_issues.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    type: Mapped[str] = mapped_column(String(24))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | confirmed | rejected
