"""Demo factory: structure, people, machines, devices, policies, rules and needle lots.

Idempotent: does nothing when a factory already exists. Used for demos, tests and local dev.
"""

import random
import secrets
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.security import hash_password, sha256
from app.models import (
    AlertRule,
    Device,
    Factory,
    Floor,
    Line,
    Machine,
    MachineAssignment,
    MachineBrand,
    MachineType,
    NeedleBatch,
    NeedleEvent,
    NeedleIssue,
    NeedleSupplier,
    Operation,
    Policy,
    PolicyVersion,
    Product,
    ReasonCode,
    Station,
    User,
    UserRole,
    Worker,
    WorkerAssignment,
)
from app.modules.shift import DEFAULT_SHIFT, DEFAULT_THRESHOLDS

DEMO_PASSWORD = "stitchsense-demo"  # dev/demo only; production requires SS_ADMIN_PASSWORD
STATIONS_PER_LINE = 24
LINES = [  # (code, product, operation, operation_bn, smv, difficulty group, machine type)
    ("L1", "Basic T-shirt", "Sleeve attach", "হাতা লাগানো", "0.450", "B", "Overlock"),
    ("L2", "Basic T-shirt", "Collar attach", "কলার লাগানো", "0.620", "C", "Lockstitch"),
    ("L3", "Polo shirt", "Placket attach", "প্লাকেট লাগানো", "0.620", "C", "Lockstitch"),
    ("L4", "Polo shirt", "Side seam", "সাইড সেলাই", "0.380", "A", "Overlock"),
    ("L5", "Hoodie", "Hood join", "হুড জোড়া", "0.780", "C", "Overlock"),
    ("L6", "Hoodie", "Cuff attach", "কাফ লাগানো", "0.520", "B", "Flatlock"),
]
FIRST = [
    "Rahima",
    "Shirin",
    "Laila",
    "Josna",
    "Ruma",
    "Nasrin",
    "Popy",
    "Mitu",
    "Salma",
    "Taslima",
    "Moushumi",
    "Rokeya",
    "Sumi",
    "Akhi",
    "Beauty",
    "Lipi",
    "Farzana",
    "Jesmin",
    "Kulsum",
    "Shapla",
    "Rina",
    "Hasina",
    "Kamal",
    "Rubel",
    "Jahid",
    "Sohel",
    "Nayeem",
    "Rafiq",
]
LAST = ["Khatun", "Akter", "Begum", "Islam", "Sarkar", "Hossain", "Rahman", "Das", "Mia", "Biswas"]
BRANDS = ["Juki", "Jack", "Brother", "Typical", "Siruba"]


async def ensure_admin(db: AsyncSession) -> None:
    """First start of any install: create the admin account from SS_ADMIN_EMAIL / SS_ADMIN_PASSWORD."""
    if (await db.execute(select(User.id).limit(1))).first():
        return
    s = get_settings()
    if s.admin_password is None and s.env == "production":
        raise RuntimeError("SS_ADMIN_PASSWORD is required to create the first admin")
    password = s.admin_password.get_secret_value() if s.admin_password else DEMO_PASSWORD
    admin = User(email=s.admin_email.lower(), full_name="Factory admin", password_hash=hash_password(password))
    admin.roles = [UserRole(role="system_admin"), UserRole(role="factory_admin")]
    db.add(admin)
    await db.commit()


DEMO_PEOPLE = [  # one login per role, so each role's access can be tried on its own
    ("supervisor@stitchsense.local", "Line supervisor", ["supervisor"]),
    ("quality@stitchsense.local", "Quality manager", ["quality"]),
    ("maintenance@stitchsense.local", "Maintenance lead", ["maintenance"]),
    ("manager@stitchsense.local", "Factory manager", ["management"]),
]


async def _demo_users(db: AsyncSession) -> None:
    """Demo logins (never created in production; see Settings). Re-syncs their roles on every start."""
    for email, name, roles in DEMO_PEOPLE:
        u = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if u is None:
            u = User(email=email, full_name=name, password_hash=hash_password(DEMO_PASSWORD))
            db.add(u)
        if sorted(r.role for r in u.roles or []) != sorted(roles):
            u.roles = [UserRole(role=r) for r in roles]


async def _policies(db: AsyncSession, factory: Factory) -> None:
    for kind, name, body in (("shift", "Day shift", DEFAULT_SHIFT), ("thresholds", "Floor thresholds", DEFAULT_THRESHOLDS)):
        p = Policy(factory_id=factory.id, kind=kind, name=name)
        db.add(p)
        await db.flush()
        db.add(PolicyVersion(policy_id=p.id, version=1, body=body, effective_from=utcnow() - timedelta(days=60)))
    rules = [
        (
            "Machine stopped",
            "state_duration",
            {"event_type": "machine_state", "state": "stopped", "min_minutes": 15},
            "critical",
            ["supervisor", "maintenance"],
        ),
        (
            "Idle at station",
            "state_duration",
            {"event_type": "worker_state", "state": "idle", "min_minutes": 8},
            "warning",
            ["supervisor"],
        ),
        (
            "Away from station",
            "state_duration",
            {"event_type": "worker_state", "state": "away", "min_minutes": 20},
            "info",
            ["supervisor"],
        ),
        (
            "Possible phone use",
            "event",
            {"event_type": "worker_state", "state": "phone_use", "lookback_minutes": 30},
            "warning",
            ["supervisor"],
        ),
        (
            "Suspected needle break",
            "event",
            {"event_type": "needle_event", "state": "suspected_break", "lookback_minutes": 60},
            "critical",
            ["maintenance", "supervisor"],
        ),
        ("Device offline", "device_offline", {"after_minutes": 3}, "info", ["system_admin"]),
    ]
    for name, kind, cond, sev, roles in rules:
        db.add(AlertRule(factory_id=factory.id, name=name, kind=kind, condition=cond, severity=sev, recipient_roles=roles))
    for cat, code, name, bn in (
        ("downtime", "breakdown", "Machine breakdown", "মেশিন নষ্ট"),
        ("downtime", "needle_change", "Needle change", "সুই বদল"),
        ("pause", "material", "Waiting for material", "কাপড়ের অপেক্ষা"),
        ("pause", "personal", "Personal break", "ব্যক্তিগত বিরতি"),
        ("pause", "quality_check", "Quality check", "মান যাচাই"),
    ):
        db.add(ReasonCode(category=cat, code=code, name=name, name_bn=bn))


async def _needles(db: AsyncSession, machines: list[tuple[Machine, Station, Worker]], rng: random.Random) -> None:
    lots = [
        ("Supplier A", "B-104", "DBx1 · Nm 90 · SES", 20),
        ("Supplier B", "GB-5521", "DCx27 · Nm 80 · FFG", 300),
        ("Supplier A", "B-109", "DBx1 · Nm 90 · SES", 200),
        ("Supplier C", "C-077", "DCx27 · Nm 80 · SES", 20),
        ("Supplier D", "D-311", "DBx1 · Nm 100 · R", 200),
    ]
    suppliers: dict[str, NeedleSupplier] = {}
    batches = []
    for sup, lot, model, qty in lots:
        if sup not in suppliers:
            suppliers[sup] = NeedleSupplier(name=sup)
            db.add(suppliers[sup])
            await db.flush()
        b = NeedleBatch(
            supplier_id=suppliers[sup].id,
            lot_no=lot,
            model=model,
            qty_received=qty,
            received_on=date.today() - timedelta(days=rng.randint(10, 40)),
        )
        db.add(b)
        batches.append(b)
    await db.flush()
    now = utcnow()
    bad = []
    for i, (m, st, w) in enumerate(machines):
        b = batches[0] if i % 12 == 0 else batches[3] if i == 5 else batches[1 + i % 2] if i % 7 else batches[4]
        hours_ago = rng.uniform(2, 10) if b is batches[0] else rng.uniform(24, 140)
        db.add(NeedleIssue(batch_id=b.id, machine_id=m.id, station_id=st.id, installed_at=now - timedelta(hours=hours_ago)))
        if b is batches[0]:
            bad.append((m, st, w))
    # history: lot B-104 broke 8 times across many machines and workers; a few normal breaks elsewhere
    history = [(batches[0], bad[k % len(bad)]) for k in range(8)] + [(batches[1], machines[3]), (batches[2], machines[40])]
    for k, (b, (m, st, w)) in enumerate(history):
        start = now - timedelta(hours=20 + k * 9)
        issue = NeedleIssue(
            batch_id=b.id,
            machine_id=m.id,
            station_id=st.id,
            installed_at=start,
            removed_at=start + timedelta(hours=rng.uniform(2, 7)),
            removal_reason="broken",
        )
        db.add(issue)
        await db.flush()
        db.add(
            NeedleEvent(
                needle_issue_id=issue.id, type="needle_break", occurred_at=issue.removed_at, worker_id=w.id, status="confirmed"
            )
        )


async def seed_demo(db: AsyncSession, seed: int = 7) -> bool:
    await _demo_users(db)
    if (await db.execute(select(Factory.id).limit(1))).first():
        await db.commit()
        return False
    rng = random.Random(seed)
    factory = Factory(code="U2", name="Unit 2", timezone="Asia/Dhaka", settings={"card_tap_enabled": True, "face_blur": True})
    db.add(factory)
    await db.flush()
    await _policies(db, factory)
    for code, bn in (("Overlock", "ওভারলক"), ("Lockstitch", "লকস্টিচ"), ("Flatlock", "ফ্ল্যাটলক")):
        db.add(MachineType(code=code, name=code, name_bn=bn))
    db.add_all(MachineBrand(name=b) for b in BRANDS)
    floors = [Floor(factory_id=factory.id, code=f"F{n}", name=f"Floor {n}") for n in (1, 2)]
    db.add_all(floors)
    await db.flush()
    edge = Device(
        code="EDGE-1",
        kind="edge_box",
        config={"name": "Floor 1 edge box", "simulated": True},
        token_hash=sha256(secrets.token_urlsafe(32)),
        last_seen_at=utcnow(),
    )
    db.add(edge)
    since = utcnow() - timedelta(days=30)
    machines: list[tuple[Machine, Station, Worker]] = []
    wn = 0
    for li, (code, prod, op_name, op_bn, smv, grp, mtype) in enumerate(LINES):
        line = Line(floor_id=floors[li // 3].id, code=code, name=f"Line {li + 1}")
        product = (await db.execute(select(Product).where(Product.name == prod))).scalar_one_or_none()
        if product is None:
            product = Product(code=f"P-{prod.split()[0][:4].upper()}{li}", name=prod)
            db.add(product)
        db.add(line)
        await db.flush()
        op = Operation(
            product_id=product.id, code=f"OP-{code}", name=op_name, name_bn=op_bn, smv=Decimal(smv), difficulty_group=grp
        )
        db.add(op)
        await db.flush()
        for p in range(1, STATIONS_PER_LINE + 1):
            st = Station(line_id=line.id, code=f"{code}-S{p:02d}", name=f"Station {p}", position=p)
            db.add(st)
            await db.flush()
            m = Machine(factory_id=factory.id, asset_code=f"M-{li + 1}{p:03d}", machine_type=mtype, brand=rng.choice(BRANDS))
            wn += 1
            w = Worker(
                factory_id=factory.id,
                employee_code=f"E-{1000 + wn}",
                full_name=f"{rng.choice(FIRST)} {rng.choice(LAST)[0]}.",
                rfid_card_id=f"04{wn:06X}",
            )
            db.add_all([m, w])
            await db.flush()
            db.add_all(
                [
                    MachineAssignment(machine_id=m.id, station_id=st.id, valid_from=since),
                    WorkerAssignment(worker_id=w.id, station_id=st.id, operation_id=op.id, valid_from=since),
                    Device(code=f"SENS-{st.code}", kind="machine_sensor", station_id=st.id, last_seen_at=utcnow()),
                ]
            )
            if p % 2 == 1:
                db.add(
                    Device(
                        code=f"CAM-{st.code}",
                        kind="camera",
                        station_id=st.id,
                        last_seen_at=utcnow(),
                        config={"stations": [st.code], "fps": 5, "face_blur": True},
                    )
                )
            machines.append((m, st, w))
    await _needles(db, machines, rng)
    await db.commit()
    return True
