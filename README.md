# NodeLens

Self-hosted IoT telemetry monitoring system with a dashboard UI, plugin-based device support, and rule-based alerting (diploma project).

**Backend:** Python 3.13, FastAPI, SQLAlchemy (async), TimescaleDB, Redis Streams

**Frontend:** React 19, TypeScript, Vite, Mantine v7, TanStack Query, react-grid-layout

**Deployment:** Docker Compose (7 services)

## Quick start

```bash
# Operator path — pulls pre-built images from GHCR, only `plugins` builds locally.
# This is the fast path: ingestor / api / alerts / frontend come straight from
# ghcr.io/hekzory/nodelens-<svc>:latest.
make up

# Open the UI
open http://localhost

# View logs
make logs            # all services
make logs-ingestor   # telemetry consumer
make logs-alerts     # alert evaluator
make logs-plugins    # plugin subprocesses
make logs-api        # FastAPI

# Refresh registry images without restarting
make pull

# Tear down
make down            # keep data
make down-v          # wipe postgres volume
```

### Pinning to a specific commit

`make up` follows `:latest`, which is mutable and tracks `master` HEAD. To pin
the four registry-published services to a specific commit, set `NODELENS_TAG`
in your `.env`:

```bash
echo "NODELENS_TAG=sha-abc1234" >> .env
make up
```

Available tags per image: `latest`, `master`, and `sha-<7chars>` for every
commit on `master`. See [GitHub Packages](https://github.com/Hekzory?tab=packages).

### Contributor path

Edit code, then rebuild every service from local source:

```bash
make up-dev          # docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
make build-dev       # rebuild without restarting
```

`make up-dev` tags locally-built images as `nodelens-<svc>:dev` so they don't
collide with the registry tags.

## Services

| Service   | Port | Description |
|-----------|------|-------------|
| frontend  | 80   | React SPA served by nginx, proxies `/api/` to backend |
| api       | 8000 | FastAPI — REST API ([Swagger UI](http://localhost:8000/api/docs)) |
| ingestor  | —    | Consumes `telemetry_events` + `registration_events`, writes to TimescaleDB |
| alerts    | —    | Consumes `telemetry_events` (own consumer group), evaluates rules, writes alert history, dispatches via integration plugins |
| plugins   | —    | Plugin supervisor — discovers plugins, runs each as a subprocess, restarts on crash |
| postgres  | 5432 | TimescaleDB (PostgreSQL 17) |
| redis     | 6379 | Event bus (Redis Streams) |

## Frontend pages

- **Dashboard** (`/`) — configurable widget grid (charts, gauges, stat cards, status indicators) with drag-and-drop layout
- **Devices** (`/devices`) — device list with online status, filtering by plugin/status; detail view with sensor telemetry charts
- **Alerts** (`/alerts`) — Rules / Channels / History tabs; create instant or aggregated rules, attach channels, acknowledge fired alerts
- **Plugins** (`/plugins`) — plugin management with enable/disable toggle (stops the plugin's subprocess when disabled)

## Alerting

Three rule kinds are supported:

- **Instant** — every incoming reading is compared to a `threshold` with one of `gt`, `lt`, `gte`, `lte`, `eq`, `neq`.
- **Aggregated** — `avg|min|max|sum|count` over a configurable time window (`duration_seconds`) is compared to a threshold on each new event.
- **No data** (`condition=no_data`) — fires when the rule's sensor has produced no telemetry within `duration_seconds`. A periodic scanner (`NO_DATA_SCAN_INTERVAL_SECONDS`, default 5s) runs alongside the event-driven evaluator inside the `alerts` container. To prevent spurious fires, the scanner additionally requires (a) it has been running at least `duration_seconds` since process start (so a fresh container restart cannot mass-fire on accumulated silence) and (b) the engine has processed at least one telemetry event within `duration_seconds` (so a stalled pipeline does not look like silent sensors). Rules whose sensor has never reported any telemetry are not fired (treated as not-yet-deployed).

Each rule has a `cooldown_seconds` window enforced via the `alert_history` table — re-fires are suppressed until the cooldown has elapsed since the last fire. Fired alerts can be acknowledged from the History tab.

A rule is linked to one or more **notification channels** (many-to-many). A channel binds an integration plugin (e.g. `email`) to a destination config (e.g. `to`, SMTP host, app password). When a rule fires, one event per active linked channel is published to the `alert_dispatch_events` Redis stream; each integration plugin reads its own consumer group on that stream and calls its `send()` method.

Built-in integration: **`email`** — plain SMTP via `aiosmtplib`. Supports MX auto-discovery (leave `smtp_host` blank), authenticated TLS submission (port 465 / `use_tls`), or STARTTLS (port 587 / `start_tls`). For real delivery to a Gmail/Yandex/Outlook inbox, configure your provider's submission server with an app password.

## Plugin system

Plugins live in `plugins/devices/` and `plugins/integrations/`. Each plugin has a `manifest.yaml` with `id`, `name`, `type` (`device` | `integration`), `version`, and `entry_point`. The supervisor discovers plugins on startup, bootstraps a row in the `plugins` DB table for each, and runs every plugin where `is_active=True` as its own subprocess. Toggling `is_active` from the UI starts/stops the corresponding subprocess on the next supervisor cycle.

Built-in plugins:

- **`demo_sender`** (device) — generates synthetic telemetry across 5 sensors every 3 s; useful for seeing the full pipeline without real hardware.
- **`email`** (integration) — described above.

Plugin authors only need to subclass `DevicePlugin` (implement `on_message`) or `IntegrationPlugin` (implement `send`) from `nodelens.sdk`. Integration plugins typically delegate their `start()` to the SDK's `run_dispatch_loop` helper, which handles stream subscription and message filtering.

## Development

```bash
# Backend tests — unit + integration in one pytest run. Integration tests spin up
# throwaway Postgres/Redis containers via testcontainers (auto-skipped without Docker).
make test
make pytest       # verbose

# Backend lint
make lint
make lint-fix

# Frontend dev server (hot reload, proxies /api/ to localhost:8000)
cd frontend && pnpm dev

# Frontend type-check + lint
cd frontend && pnpm exec tsc -b && pnpm lint

# API docs (Swagger UI)
make api-docs

# Useful queries
make query-devices
make query-sensors
make query-telemetry
make query-plugins
make redis-stream
make redis-registration
```

## Project structure

```
backend/          Python backend (FastAPI + ingestor + alerts + plugin runner)
  nodelens/
    api/          FastAPI routers (health, plugins, devices, telemetry, alerts, channels, dashboards)
    db/           SQLAlchemy async models + session
    redis/        Stream client + helpers + shared parsers
    schemas/      Dataclasses (events) + Pydantic API schemas
    sdk/          Plugin authoring surface (BasePlugin, Device/IntegrationPlugin, PluginContext, run_dispatch_loop)
    workers/
      ingestor/   Telemetry + registration consumers
      alerts/     Rule evaluator + dispatcher
      plugin_runner/  Subprocess supervisor
  tests/          Pytest suite (unit + integration via testcontainers)
frontend/         React + TypeScript SPA (Vite + Mantine)
plugins/          Drop-in device/integration plugins
  devices/demo_sender/
  integrations/email/
deploy/           Per-service Dockerfiles, nginx, postgres init, redis config
scripts/          Utility scripts (init_db, loadtest)
docs/             Architecture documentation
```

See [AGENTS.md](./AGENTS.md) for the full architecture spec, fixed constraints, and deferred work.
