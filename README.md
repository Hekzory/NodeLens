# NodeLens

Self-hosted IoT telemetry monitoring system with a dashboard UI, plugin-based device support, and alerting (diploma project).

**Backend:** Python 3.13, FastAPI, SQLAlchemy (async), TimescaleDB, Redis Streams

**Frontend:** React 19, TypeScript, Vite, Mantine v7, TanStack Query, react-grid-layout

**Deployment:** Docker Compose (7 services)

## Quick start

```bash
# Start all services (postgres, redis, api, ingestor, plugins, frontend)
make up

# Open the UI
open http://localhost

# Seed demo data (optional — demo_sender plugin generates data automatically)
make seed

# View logs
make logs            # all services
make logs-ingestor   # ingestor only
make logs-plugins    # plugins only
make logs-api        # api only

# Tear down
make down            # keep data
make down-v          # wipe postgres volume
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 80 | React SPA served by nginx, proxies `/api/` to backend |
| api | 8000 | FastAPI — REST API ([Swagger UI](http://localhost:8000/docs)) |
| ingestor | — | Consumes Redis streams, writes telemetry to TimescaleDB |
| plugins | — | Plugin supervisor — discovers, starts, and monitors device plugins |
| postgres | 5432 | TimescaleDB (PostgreSQL 17) |
| redis | 6379 | Event bus (Redis Streams) |
| seed | — | One-shot demo data seeder (optional profile) |

## Frontend pages

- **Dashboard** (`/`) — configurable widget grid (charts, gauges, stat cards, status indicators), drag-and-drop layout
- **Devices** (`/devices`) — device list with online status, filtering by plugin/status; detail view with sensor telemetry charts
- **Plugins** (`/plugins`) — plugin management with enable/disable toggle (stops data collection when disabled)

## Plugin system

Plugins live in `plugins/devices/` (and eventually `plugins/integrations/`). Each plugin has a `manifest.yaml` with id, name, type, version, and entry point. The supervisor discovers plugins on startup and manages their lifecycle based on the `is_active` DB flag.

A built-in `demo_sender` plugin generates synthetic telemetry for development.

## Development

```bash
# Backend tests
make test

# Frontend dev server (hot reload, proxies /api/ to localhost:8000)
cd frontend && pnpm dev

# API docs
make api-docs

# Useful queries
make query-devices
make query-sensors
make query-telemetry
make query-plugins
make redis-stream
```

## Project structure

```
backend/          Python backend (FastAPI + workers)
frontend/         React frontend (Vite + Mantine)
plugins/          Drop-in device/integration plugins
deploy/           Dockerfiles, nginx, postgres init, redis config
scripts/          Utility scripts (seed, init)
docs/             Architecture documentation
```
