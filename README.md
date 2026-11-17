# StitchSense

Sewing-floor monitoring for garment factories: working time, output against target (SMV efficiency), machine downtime, needle breaks traced to the supplier lot, a supervisor review queue and a live alert center. English and Bangla. Self-hosted: one install per client factory.

| Part | Stack | Folder |
|---|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 16 | [apps/api](apps/api) |
| Web | Next.js 15, React 19, TypeScript, Tailwind CSS 4, GSAP | [apps/web](apps/web) |
| Simulator | Built into the API; a realistic factory for demos | [apps/api/app/simulator](apps/api/app/simulator) |
| Deploy | Docker Compose + Caddy (automatic HTTPS) | [deploy](deploy) |
| Docs | PRD, TRD, flows, backend design, API, deployment | [docs](docs) |

## Run it locally

Needs Docker, Python with [uv](https://docs.astral.sh/uv/), and Node 22+.

```bash
# 1. database (port 5433 so it does not clash with a local Postgres)
docker run -d --name ss-postgres -e POSTGRES_USER=stitchsense -e POSTGRES_PASSWORD=stitchsense \
  -e POSTGRES_DB=stitchsense -p 5433:5432 postgres:16-alpine

# 2. API with the simulator on
cd apps/api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8000

# 3. web (another terminal)
cd apps/web
npm install
NEXT_PUBLIC_DEMO=1 npm run dev -- -p 3100
```

Open http://localhost:3100. Demo logins (password `stitchsense-demo`): `admin@stitchsense.local`, `supervisor@stitchsense.local`, `quality@stitchsense.local`.

On first start the API creates a demo factory (6 lines, 144 stations, workers, machines, devices, alert rules, needle lots) and the simulator replays the current shift, then keeps the floor moving. Outside shift hours the simulator moves the demo shift so there is always a live floor to show.

## Tests

```bash
# API: unit + integration against a real Postgres (creates stitchsense_test)
docker exec ss-postgres psql -U stitchsense -c "create database stitchsense_test"
cd apps/api && uv run pytest --cov=app

# Web: types, lint, end-to-end in a real browser (API and web must be running)
cd apps/web
npx tsc --noEmit && npx eslint src e2e
NEXT_PUBLIC_DEMO=1 npm run build && npx next start -p 3100 &
npx playwright test
```

CI runs all of this on every push: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Deploy for a client factory

```bash
cp deploy/.env.example deploy/.env      # set the domain, database password and admin password
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

- Caddy gets an HTTPS certificate for `SITE_ADDRESS` automatically.
- The API runs database migrations on start and refuses to start in production without `SS_ADMIN_PASSWORD` (12+ characters) and secure cookies.
- For a demo install (university, sales), set `SS_ENV=demo`, `SS_SIMULATOR_ENABLED=true` and `DEMO_MODE=1`.
- Hardware, network and what the client provides: [docs/DEPLOYMENT_REQUIREMENTS.md](docs/DEPLOYMENT_REQUIREMENTS.md).

## Where things are

- Product rules: [docs/PRD.md](docs/PRD.md) (time-state precedence §7.1, worker attribution §7.2, fairness §7.3)
- API reference: [docs/API.md](docs/API.md) · live OpenAPI at `/api/docs` outside production
- Camera and sensor plan: [docs/VISION_AND_SENSING_PLAN.md](docs/VISION_AND_SENSING_PLAN.md)
- Release 1 task list: [docs/TASKS_R1.md](docs/TASKS_R1.md)
