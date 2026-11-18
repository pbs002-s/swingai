"""Admin-editable lists that other records refer to by value (PRD F-POL-8)."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MachineType(Base):
    """`Machine.machine_type` stores the `code` of one of these."""

    __tablename__ = "machine_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    name_bn: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)


class MachineBrand(Base):
    """`Machine.brand` stores the `name` of one of these."""

    __tablename__ = "machine_brands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
