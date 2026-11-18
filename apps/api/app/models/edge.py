"""Edge job queue: the web app asks an edge box to do camera work it alone can reach (VISION plan §6.1)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow

JOB_KINDS = ("discover_cameras", "test_camera", "snapshot", "test_detection")
JOB_STATUSES = ("queued", "running", "done", "failed")


class EdgeJob(Base):
    __tablename__ = "edge_jobs"
    __table_args__ = (Index("ix_edge_jobs_device_status", "edge_device_id", "status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edge_device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    kind: Mapped[str] = mapped_column(String(24))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # camera passwords inside are Fernet-encrypted
    status: Mapped[str] = mapped_column(String(16), default="queued")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
