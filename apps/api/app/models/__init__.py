"""All ORM models. Importing this package registers every table on Base.metadata."""

from app.models.alerts import Alert, AlertRule
from app.models.auth import AuditLog, Lead, Session, User, UserRole
from app.models.catalog import MachineBrand, MachineType
from app.models.edge import EdgeJob
from app.models.events import Event, EventReview, StationLive
from app.models.org import (
    Device,
    Factory,
    Floor,
    Line,
    Machine,
    MachineAssignment,
    Operation,
    Policy,
    PolicyVersion,
    Product,
    ReasonCode,
    Station,
    Worker,
    WorkerAssignment,
)
from app.models.production import NeedleBatch, NeedleEvent, NeedleIssue, NeedleSupplier, ProductionEntry

__all__ = [
    "Alert",
    "AlertRule",
    "AuditLog",
    "Device",
    "EdgeJob",
    "Event",
    "EventReview",
    "Factory",
    "Floor",
    "Lead",
    "Line",
    "Machine",
    "MachineBrand",
    "MachineType",
    "MachineAssignment",
    "NeedleBatch",
    "NeedleEvent",
    "NeedleIssue",
    "NeedleSupplier",
    "Operation",
    "Policy",
    "PolicyVersion",
    "Product",
    "ProductionEntry",
    "ReasonCode",
    "Session",
    "Station",
    "StationLive",
    "User",
    "UserRole",
    "Worker",
    "WorkerAssignment",
]
