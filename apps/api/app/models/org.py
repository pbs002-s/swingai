"""Factory structure, catalog, machines, devices, workers, assignments and policies."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class Factory(Base):
    __tablename__ = "factories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Dhaka")
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Floor(Base):
    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("factory_id", "code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120))


class Line(Base):
    __tablename__ = "lines"
    __table_args__ = (UniqueConstraint("floor_id", "code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)


class Station(Base):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Operation(Base):
    __tablename__ = "operations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    name_bn: Mapped[str | None] = mapped_column(String(120))
    smv: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    difficulty_group: Mapped[str] = mapped_column(String(8), default="B")


class ReasonCode(Base):
    __tablename__ = "reason_codes"
    __table_args__ = (UniqueConstraint("category", "code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(16))  # downtime | pause | reject
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120))
    name_bn: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)


class Machine(Base):
    __tablename__ = "machines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id"), index=True)
    asset_code: Mapped[str] = mapped_column(String(32), unique=True)
    machine_type: Mapped[str] = mapped_column(String(64))
    brand: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")


class MachineAssignment(Base):
    """Which machine stands at which station, over time. Overlaps are refused in service code."""

    __tablename__ = "machine_assignments"
    __table_args__ = (Index("ix_machine_assign_station_time", "station_id", "valid_from"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(24))  # edge_box | camera | machine_sensor | card_reader
    station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id"), index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True)


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id"), index=True)
    employee_code: Mapped[str] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    full_name_bn: Mapped[str | None] = mapped_column(String(120))
    rfid_card_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class WorkerAssignment(Base):
    """Which worker sits at which station on which operation, over time."""

    __tablename__ = "worker_assignments"
    __table_args__ = (Index("ix_worker_assign_station_time", "station_id", "valid_from"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id"))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # shift | thresholds | ranking | retention
    name: Mapped[str] = mapped_column(String(120))


class PolicyVersion(Base):
    """Policies are never edited: a change is a new version (PRD F-POL-6)."""

    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[dict[str, Any]] = mapped_column(JSON)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
