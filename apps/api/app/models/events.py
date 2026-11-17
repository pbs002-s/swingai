"""Raw events (append-only), human reviews of them, and the live state per station.

Worker and machine states arrive as *transition* events: each says "from start_time this
station is in state X"; it lasts until the next transition of the same type.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow

EVENT_STATES: dict[str, set[str]] = {
    "worker_state": {"working", "idle", "phone_use", "away", "break", "uncertain"},
    "machine_state": {"running", "stopped"},
    "production_count": {"count"},
    "needle_event": {"suspected_break", "needle_break", "thread_break", "jam", "other"},
    "quality_event": {"possible_skipped_stitch", "possible_puckering", "other_defect", "no_defect"},
    "rfid_tap": {"tap"},
}

# Event types/states that always wait for a person, whatever the confidence (PRD §7.3).
ALWAYS_REVIEW = {("worker_state", "phone_use"), ("needle_event", "*"), ("quality_event", "*")}


class Event(Base):
    __tablename__ = "events"
    # ponytail: one table; partition by month (BACKEND_DESIGN §3.2) once an install passes ~50M rows.
    __table_args__ = (
        Index("ix_events_station_time", "station_id", "start_time"),
        Index("ix_events_type_time", "event_type", "start_time"),
        Index("ix_events_review", "review_status"),
    )
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    event_uuid: Mapped[Any] = mapped_column(Uuid, unique=True)
    event_type: Mapped[str] = mapped_column(String(24))
    state: Mapped[str] = mapped_column(String(32))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    machine_id: Mapped[int | None] = mapped_column(Integer)
    worker_id: Mapped[int | None] = mapped_column(Integer, index=True)
    operation_id: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))  # simulator | manual | sensor | vision | import
    device_id: Mapped[int | None] = mapped_column(Integer)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    model_version: Mapped[str | None] = mapped_column(String(48))
    review_status: Mapped[str] = mapped_column(String(16))  # auto_accepted | pending | confirmed | rejected
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventReview(Base):
    __tablename__ = "event_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))  # confirm | reject | reclassify
    new_state: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(500))
    reviewed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StationLive(Base):
    """Latest known worker and machine state per station, kept current by ingest."""

    __tablename__ = "station_live"
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), primary_key=True)
    worker_state: Mapped[str | None] = mapped_column(String(32))
    worker_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    machine_state: Mapped[str | None] = mapped_column(String(16))
    machine_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
