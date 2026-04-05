# AGENTS.md

## Project identity

**Name:** NodeLens
**Type:** Diploma project
**Official theme:** “A web application for monitoring IoT telemetry with intelligent alert processing”

## Current status

This repository is currently a **first-iteration partially implemented project**.

Important:
- Many files may still exist but be empty.
- File presence does **not** imply implementation exists.
- A minimal runnable slice **does exist now**:
  - PostgreSQL + TimescaleDB
  - Redis Streams
  - Web backend (FastAPI)
  - Ingestor
  - Plugins worker (with a built-in demo_sender device plugin)
- `docker-compose.yml` currently starts 5 services: `postgres`, `redis`, `api`, `ingestor`, `plugins`.
- Metadata required for ingestion (`plugins`, `devices`, `sensors`) is registered at runtime by plugins themselves via the `registration_events` Redis stream. The ingestor consumes that stream and upserts rows into the DB. Registration is idempotent — plugins re-register on every restart.
- Python target is **3.13**.
- Python dependencies are managed with **uv** from `backend/pyproject.toml`.
- If a behavior is not described here as fixed, do not assume it is implemented.
- Prefer explicit placeholders over invented details.

Use this convention when something is not implemented yet:

> [this part is not currently implemented, will be replaced with details of internals later]

---

## Product scope

NodeLens is a self-hosted IoT telemetry monitoring system.

Primary goals:
- monitor IoT telemetry
- display telemetry in a modern dashboard UI
- support user-defined alert rules
- support alert delivery through integrations
- remain easy to deploy with Docker Compose

Non-goals by default:
- no device control plane
- no “turn on/off” or command dispatch features
- no requirement for public SaaS hosting
- no high-load / enterprise-scale assumptions

Target scale:
- home / small self-hosted setup
- one technically competent operator
- polling-based frontend is acceptable

---

## Fixed architecture constraints

The container/component layout is fixed and should be preserved.

There are **8 containers**:

1. **Web frontend**
   - React 19 + TypeScript, Vite, pnpm
   - UI: Mantine v7 (dark-only theme, `forceColorScheme="dark"`)
   - Data: TanStack Query (10s polling interval)
   - Routing: React Router v7
   - Charts: @mantine/charts (Recharts wrapper)
   - Dashboard layout: react-grid-layout v2 (drag/resize with `dragConfig`/`resizeConfig`, `useContainerWidth()` for width)
   - Icons: @tabler/icons-react
   - built during Docker image build (multi-stage: node:22-alpine → nginx:alpine)
   - served by nginx, proxies `/api/` to backend
   - talks to backend over HTTP only, polling-based

2. **Web backend**
   - Python + FastAPI
   - configuration/query plane
   - handles dashboards, plugin settings, alert settings, telemetry queries

3. **PostgreSQL + TimescaleDB**
   - primary durable storage
   - stores both telemetry and application data

4. **Redis Streams**
   - internal event bus / queue

5. **MQTT broker**
   - expected default ingress path for IoT telemetry
   - present by default

6. **Alert processor**
   - background worker
   - evaluates alert rules and triggers integrations

7. **Ingestor**
   - background worker
   - consumes normalized telemetry events and writes them to DB

8. **Plugins worker**
   - background worker
   - loads plugins from the repo/plugin directory
   - each plugin runs as its own process inside this container

These roles are fixed even if some services share a codebase.

Current implementation note:
- The 8-container layout remains the target architecture and should still be treated as fixed.
- The **currently implemented runtime subset** is:
  1. PostgreSQL + TimescaleDB
  2. Redis Streams
  3. Web backend (FastAPI)
  4. Ingestor
  5. Plugins worker
  6. Frontend (React, served by nginx)
- Frontend is implemented as an MVP (dashboard, devices, plugins pages).
- MQTT broker usage and alert processor are not yet active runtime components in the current iteration.

---

## Core design intent

### Stack
- Backend/workers: Python 3.13
- Dependency management: uv + `backend/pyproject.toml`
- Web API: FastAPI
- Database: PostgreSQL + TimescaleDB extension
- Event bus: Redis Streams
- MQTT: Mosquitto
- Frontend: React 19 + TypeScript, Vite, pnpm, Mantine v7, TanStack Query, react-grid-layout v2
- Deployment: Docker Compose

Current core Python deps for the implemented part:
- `sqlalchemy[asyncio] >= 2.0.48`
- `asyncpg >= 0.31.0`
- `redis >= 7.3.0`
- `pydantic >= 2.12.5`
- `pydantic-settings >= 2.13.1`
- `ruamel.yaml == 0.19.1`

### Architectural principles
- keep components loosely coupled
- avoid unnecessary complexity
- do not reinvent everything, but also do not just wrap unrelated products
- use a shared Python codebase with separate service entry points
- keep plugin-facing contracts explicit
- optimize for ease of development and deployment

---

## Main runtime data flow

### Telemetry ingest path
1. IoT device sends data through some external protocol
2. A **device plugin** receives that data
3. The plugin normalizes it into a shared internal event format
4. The plugin publishes the normalized event to **Redis Streams**
5. **Ingestor** reads the stream and writes telemetry to **TimescaleDB**

### Alert path
1. Telemetry event appears in Redis
2. **Alert processor** consumes events from Redis
3. Alert processor also reads DB state when rules require time-window checks
4. If a rule triggers:
   - write alert history to DB
   - dispatch through integration mechanism

### Dashboard/read path
1. Frontend requests dashboard/telemetry data from backend
2. Backend queries PostgreSQL/TimescaleDB
3. Frontend polls periodically
4. No WebSocket requirement is planned

### Currently implemented data flow
1. **Plugin registration (on plugin startup):**
   - Each plugin publishes `register_plugin`, `register_device`, and `register_sensor` events to the `registration_events` Redis stream.
   - Ingestor consumes this stream and upserts plugin/device/sensor rows into the DB.
   - Registration is idempotent — safe to repeat across restarts.
2. **Telemetry publishing:**
   - The demo_sender plugin (running inside the plugins worker container) publishes synthetic telemetry into Redis stream `telemetry_events`.
3. **Telemetry ingestion:**
   - Ingestor consumes `telemetry_events` through consumer group `ingest_group`.
   - Ingestor parses and validates each event:
     - `device_id` and `sensor_id` are valid UUIDs
     - `sensor_id` exists in the `sensors` table
     - `sensor_id` belongs to the given `device_id`
     - `device_id` exists and has a registered plugin (enforced by FK)
   - Accepted rows are written into the `telemetry` hypertable.
   - `devices.last_seen` is updated to the latest event timestamp for each affected device.
   - Events that fail validation are logged and skipped (not written).

---

## Hard boundaries between components

These are intentional and should not be casually broken.

### Frontend
- should talk to backend over HTTP
- should not talk directly to Redis, MQTT, or Postgres
- should assume polling, not push, unless requirements change explicitly

### Web backend
- should handle configuration, dashboard CRUD, alert rule CRUD, plugin config CRUD, telemetry read APIs
- should not become the main ingest worker
- should not absorb alert processing logic that belongs to background workers

### Device plugins
- connect to external systems
- normalize incoming data
- publish normalized events to Redis Streams
- should **not** write directly to Postgres telemetry tables

### Ingestor
- reads telemetry events from Redis stream `telemetry_events`
- reads registration events from Redis stream `registration_events`
- writes telemetry into TimescaleDB after validation
- upserts plugin/device/sensor metadata from registration events
- validates that sensor_id exists, belongs to the given device_id, and the device has a registered plugin
- updates `devices.last_seen` on successful telemetry write
- should remain focused on durable ingestion and registration
- should **not** create plugins, devices, or sensors from telemetry events (only from explicit registration events)

### Alert processor
- reads telemetry events from Redis
- may query DB for historical/time-window conditions
- writes alert history to DB
- dispatches notifications through integration mechanism

### MQTT broker
- infrastructure component only
- devices may publish here
- a device plugin may subscribe and normalize payloads

---

## Plugin model

There are **two plugin types**.

### 1. Device plugins
Purpose:
- connect to external telemetry sources
- discover devices if applicable
- receive or poll telemetry
- normalize and publish telemetry events
- register themselves, their devices, and sensors via the registration stream

Examples:
- demo_sender (built-in, generates synthetic telemetry)
- MQTT plugin
- HTTP poller plugin
- [future examples not currently implemented]

### 2. Integration plugins
Purpose:
- provide alert outputs / destinations

Examples:
- [not implemented]

### Plugin placement
- user-facing plugin folders live under root `plugins/devices/` and `plugins/integrations/`
- shared Python SDK / interfaces live under `backend/nodelens/sdk/`

### Plugin SDK (`backend/nodelens/sdk/`)

Implemented classes:
- `BasePlugin` — abstract base with `configure()`, `start()`, `stop()` lifecycle methods
- `DevicePlugin(BasePlugin)` — adds abstract `on_message(raw_data: bytes) -> list[TelemetryEvent]`
- `IntegrationPlugin(BasePlugin)` — adds abstract `send(channel_config, message: AlertMessage) -> bool`
- `PluginContext` — injected runtime context providing:
  - `register_plugin()`, `register_device()`, `register_sensor()` — publish to `registration_events` stream
  - `publish_telemetry(event)` — publish to `telemetry_events` stream
  - Redis connection lifecycle (`connect()` / `close()`)
- `PluginError`, `PluginConfigError` — exception hierarchy

### Plugin manifest

Each plugin directory must contain a `manifest.yaml` with these required fields:

```yaml
id: "<UUID>"              # deterministic, unique per plugin
name: "<module_name>"     # unique identifier string
display_name: "<human-readable name>"
version: "<semver>"
type: "device"            # or "integration"
entry_point: "module:ClassName"  # e.g. "plugin:DemoSenderPlugin"
```

Optional field: `description`.

Devices and sensors are **not** declared in the manifest — plugins register them dynamically at runtime via the registration stream.

### Plugin lifecycle
1. Plugin runner supervisor discovers plugins under `PLUGINS_DIR` by scanning for `manifest.yaml` files.
2. Each valid plugin is launched as a **separate subprocess** via `run_single.py`.
3. The subprocess loads the manifest, imports the plugin class, creates a `PluginContext`, and calls:
   - `plugin.configure({})` — one-time setup
   - `plugin.start()` — main loop (runs until cancelled)
   - `plugin.stop()` — graceful shutdown on exit
4. If a plugin subprocess exits, the supervisor restarts it after a short delay.

### Plugin registration flow
1. On startup, a plugin calls `ctx.register_plugin()`, `ctx.register_device(...)`, `ctx.register_sensor(...)`.
2. These publish structured events to the `registration_events` Redis stream.
3. The ingestor's registration consumer reads and upserts them into Postgres.
4. Registration is idempotent — plugins re-register on every restart.
5. After a short settle delay, the plugin begins publishing telemetry.
6. If telemetry arrives before registration is processed, events are skipped by the ingestor (not an error — self-healing on next restart).

### Plugin expectations
- plugin configuration should be manageable through the web backend/UI (not yet implemented)

Exact plugin hot-reload behavior:
- [this part is not currently implemented, will be replaced with details of internals later]

Exact integration plugin invocation path:
- [this part is not currently implemented, will be replaced with details of internals later]

---

## Repository map

This is the intended repository layout.

### `/deploy`
Deployment artifacts:
- separate Dockerfiles for Python services
- config for Postgres, Redis, Mosquitto

### `/backend`
Shared Python codebase.

Currently implemented parts:
- `nodelens/config.py` → settings (`DATABASE_URL`, `REDIS_URL`, `LOG_LEVEL`, `PLUGINS_DIR`)
- `nodelens/constants.py` → stream/group constants for both `telemetry_events` and `registration_events`
- `nodelens/db` → SQLAlchemy base, async session, models (Plugin, Device, Sensor, TelemetryRecord)
- `nodelens/redis` → Redis client + stream helpers
- `nodelens/schemas/events.py` → TelemetryEvent, AlertMessage, RegisterPluginEvent, RegisterDeviceEvent, RegisterSensorEvent
- `nodelens/sdk` → plugin SDK (BasePlugin, DevicePlugin, IntegrationPlugin, PluginContext, exceptions)
- `nodelens/workers/ingestor` → telemetry consumer, registration consumer, writer with validation
- `nodelens/workers/plugin_runner` → plugin supervisor, loader, single-plugin subprocess runner

- `tests/` → unit tests (pytest + pytest-asyncio); covers event parsing, writer validation pipeline, registration coercion, plugin loader/discovery, and API route logic (alerts, telemetry, dashboards)

Planned but not implemented yet:
- `nodelens/workers/alerts` → alert worker
- `alembic/` → migrations

### `/plugins`
Drop-in plugins:
- `devices/`
- `integrations/`

This directory is intended to be extended by developers/users.

### `/frontend`
React + TypeScript application:
- pages
- components
- API client layer
- hooks/store/types/utils
- nginx-based runtime image

### `/scripts`
Utility scripts for setup/seed/health.

Currently implemented:
- `init_db.py`
- `seed_db.py`

### `/docs`
Architecture/deployment/plugin docs

---

## Expected responsibilities by backend package

### `backend/nodelens/api`
FastAPI application layer.

Expected concerns:
- dashboards
- alerts CRUD
- plugins CRUD/config
- telemetry query endpoints
- health endpoints

Exact routes and payloads:

**Health** `health.py`
- `GET /api/health` — liveness
- `GET /api/health/db` — DB check

**Plugins** `plugins.py`
- `GET /api/plugins` — list with device count
- `GET /api/plugins/{plugin_id}` — get single
- `PATCH /api/plugins/{plugin_id}` — toggle `is_active`
- `GET /api/plugins/{plugin_id}/devices` — list devices for plugin

**Devices** `devices.py`
- `GET /api/devices` — list (with plugin/online filters)
- `GET /api/devices/{device_id}` — detail with sensors
- `GET /api/devices/{device_id}/sensors` — list sensors for device

**Telemetry** `telemetry.py`
- `GET /api/telemetry/{sensor_id}` — time-series data
- `GET /api/telemetry/{sensor_id}/latest` — single latest reading
- `GET /api/telemetry/{sensor_id}/summary` — min/max/avg for time window
- `GET /api/telemetry/device/{device_id}` — latest readings from all sensors on device

**Alerts** `alerts.py`
- `GET /api/alerts/rules` — list rules
- `POST /api/alerts/rules` — create rule
- `GET /api/alerts/rules/{rule_id}` — get single rule
- `PATCH /api/alerts/rules/{rule_id}` — partial update
- `DELETE /api/alerts/rules/{rule_id}` — delete rule
- `GET /api/alerts/history` — list fired alerts (paginated, filterable)
- `POST /api/alerts/history/{history_id}/acknowledge` — mark acknowledged

**Dashboards** `dashboards.py`
- `GET /api/dashboards` — list dashboards
- `POST /api/dashboards` — create dashboard
- `GET /api/dashboards/{dashboard_id}` — detail with widgets
- `PATCH /api/dashboards/{dashboard_id}` — partial update
- `DELETE /api/dashboards/{dashboard_id}` — delete dashboard
- `POST /api/dashboards/{dashboard_id}/widgets` — add widget
- `PATCH /api/dashboards/{dashboard_id}/widgets/{widget_id}` — update widget config/layout
- `DELETE /api/dashboards/{dashboard_id}/widgets/{widget_id}` — remove widget

### `backend/nodelens/db`
Database access and models.

Current implemented schema subset:

- `plugins`
  - `id: UUID` (PK)
  - `plugin_type: VARCHAR`
  - `module_name: VARCHAR` (unique)
  - `display_name: VARCHAR`
  - `version: VARCHAR`
  - `is_active: BOOLEAN`
  - `created_at: TIMESTAMPTZ`

- `devices`
  - `id: UUID` (PK)
  - `plugin_id: UUID` (FK → `plugins.id`)
  - `external_id: VARCHAR`
  - `name: VARCHAR`
  - `location: VARCHAR | NULL`
  - `is_online: BOOLEAN`
  - `last_seen: TIMESTAMPTZ | NULL`
  - `created_at: TIMESTAMPTZ`

- `sensors`
  - `id: UUID` (PK)
  - `device_id: UUID` (FK → `devices.id`)
  - `key: VARCHAR`
  - `name: VARCHAR`
  - `unit: VARCHAR | NULL`
  - `value_type: VARCHAR`
  - `created_at: TIMESTAMPTZ`

- `telemetry`
  - `time: TIMESTAMPTZ`
  - `sensor_id: UUID` (FK → `sensors.id`)
  - `value_numeric: DOUBLE PRECISION | NULL`
  - `value_text: VARCHAR | NULL`
  - primary key: (`time`, `sensor_id`)

- `alert_rules`
  - `id: UUID` (PK)
  - `name: VARCHAR`
  - `sensor_id: UUID` (FK)
  - `rule_type: VARCHAR` ('instant' or 'aggregated')
  - `condition: VARCHAR` (gt, lt, eq, no_data, etc.)
  - `threshold: FLOAT`
  - `duration_seconds: INT`, `cooldown_seconds: INT`
  - `is_active: BOOLEAN`

- `alert_history`
  - `id: UUID` (PK)
  - `rule_id: UUID` (FK)
  - `triggered_value: FLOAT`
  - `message: VARCHAR`
  - `triggered_at: TIMESTAMPTZ`
  - `acknowledged_at: TIMESTAMPTZ`

- `dashboards`
  - `id: UUID` (PK)
  - `name: VARCHAR`
  - `is_default: BOOLEAN`

- `dashboard_widgets`
  - `id: UUID` (PK)
  - `dashboard_id: UUID` (FK)
  - `widget_type: VARCHAR`
  - `config: JSONB`
  - `layout: JSONB`

Full future application schema beyond this subset:
- [this part is not currently implemented, will be replaced with details of internals later]

### `backend/nodelens/redis`
Redis connection and stream helpers.

Current implemented stream structures:

**Telemetry stream:**
- stream name: `telemetry_events`
- consumer group: `ingest_group`
- consumer name: `ingestor-1`
- serialized fields: `device_id`, `sensor_id`, `value`, `timestamp`

**Registration stream:**
- stream name: `registration_events`
- consumer group: `registration_group`
- consumer name: `registrar-1`
- event types: `register_plugin`, `register_device`, `register_sensor`
- each event includes an `event_type` field plus type-specific fields matching the corresponding dataclass

Implemented concerns:
- Redis connection helper
- stream publish helper
- consumer-group creation helper
- stream read helper
- ack helper

Other stream contracts:
- [this part is not currently implemented, will be replaced with details of internals later]

### `backend/nodelens/schemas`
Shared data contracts (dataclasses).

Current implemented definitions:

```python
@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    device_id: str
    sensor_id: str
    value: float
    timestamp: datetime

@dataclass(frozen=True, slots=True)
class AlertMessage:
    rule_name: str
    device_name: str
    triggered_value: float
    message: str
    triggered_at: datetime

@dataclass(frozen=True, slots=True)
class RegisterPluginEvent:
    plugin_id: str
    plugin_type: str
    module_name: str
    display_name: str
    version: str

@dataclass(frozen=True, slots=True)
class RegisterDeviceEvent:
    device_id: str
    plugin_id: str
    external_id: str
    name: str
    location: str = ""

@dataclass(frozen=True, slots=True)
class RegisterSensorEvent:
    sensor_id: str
    device_id: str
    key: str
    name: str
    unit: str = ""
    value_type: str = "numeric"
```

Current semantics:
- device_id = stringified `devices.id`
- sensor_id = stringified `sensors.id`
- plugin_id = stringified `plugins.id`

Other API schemas:
- Implemented as Pydantic models in `backend/nodelens/schemas/` covering responses for alerts, dashboards, devices, plugins, and telemetry.


### `backend/nodelens/sdk`
Plugin authoring surface.

Implemented concerns:
- `BasePlugin` — abstract base class with `configure()`, `start()`, `stop()` lifecycle
- `DevicePlugin` — extends BasePlugin with `on_message(raw_data) -> list[TelemetryEvent]`
- `IntegrationPlugin` — extends BasePlugin with `send(channel_config, message) -> bool`
- `PluginContext` — runtime context with registration helpers and telemetry publishing
- `PluginError`, `PluginConfigError` — exception classes
- re-exports of `TelemetryEvent`, `AlertMessage`, registration event dataclasses

---

## Alerting model

High-level intent:
- allow smart rules based on observed telemetry
- support immediate triggers from new events
- support time-window checks using DB history
- support external delivery integrations

Expected rule categories:
- threshold
- absence/no data
- rate-of-change
- compound logic

Exact alert DSL / configuration schema:
- Rules are persisted via Web Backend API as either `instant` (single realtime value vs threshold) or `aggregated` (agg function over a time window `duration_seconds`).

Exact deduplication, cooldown, acknowledgement behavior:
- [this part is not currently implemented, will be replaced with details of internals later]

---

## Dashboard model

High-level intent:
- editable dashboard
- metric-oriented UI
- clean and modern look
- watch-only UX

Expected capabilities:
- widget layout
- telemetry charts/cards/gauges/status widgets
- dashboard persistence
- polling-based refresh

Exact widget catalog and layout persistence format:
- Widgets (`chart`, `gauge`, `stat_card`, `status`) are saved in DB via Web Backend API with `config` and `layout` as flexible `JSONB` blobs to be interpreted by the frontend.

---

## Deployment assumptions

Primary deployment model:
- clone repo
- configure environment
- run Docker Compose
- system starts locally/self-hosted

This project is intentionally designed to avoid requiring the author to host a public service.

Current compose/runtime definitions:
- `docker-compose.yml` currently runs:
  - `postgres`
  - `redis`
  - `api`
  - `ingestor`
  - `plugins`

Current relevant env vars:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL`
- `REDIS_URL`
- `LOG_LEVEL`
- `PLUGINS_DIR`

Current useful commands:
- `make up`
- `make down` / `make down-v`
- `make seed`
- `make logs` / `make logs-ingestor` / `make logs-plugins` / `make logs-api`
- `make restart` / `make restart-api`
- `make ps`
- `make query-telemetry`
- `make query-devices`
- `make query-sensors`
- `make query-plugins`
- `make redis-stream`
- `make redis-registration`

Future full 8-service compose layout:
- [this part is not currently implemented, will be replaced with details of internals later]

---

## What future agents should NOT assume

Do not assume any of the following already exist unless they are explicitly implemented in code:
- authentication system
- finalized full application database schema beyond the currently implemented ingestion subset
- finalized Redis/event contracts beyond the currently implemented telemetry ingestion contract
- plugin hot-reloading
- plugin security sandboxing
- detailed alert delivery engine
- observability stack
- production hardening

For all of the above, use:
- [this part is not currently implemented, will be replaced with details of internals later]

---

## Rules for future implementation work

1. Preserve the 8-container topology.
2. Keep the backend/workers loosely coupled even if they share code.
3. Keep telemetry write flow as:
   - device plugin → Redis Streams → ingestor → TimescaleDB
4. Do not let device plugins write directly to telemetry tables.
5. Keep the frontend polling-based unless explicitly changed.
6. Do not add device control features unless explicitly requested.
7. When something is unspecified, state the assumption clearly.
8. Do not present guessed behavior as existing behavior.
9. If a previously unspecified area becomes implemented, update this file.

---

## Short summary

NodeLens is a Docker Compose-deployed, self-hosted IoT telemetry monitoring system with:
- modern dashboard UI
- watch-only product scope
- Python/FastAPI backend
- Postgres + TimescaleDB storage
- Redis Streams as event bus
- MQTT broker by default
- plugin-based device ingestion and alert integrations
- separate ingestor / alert / plugin worker services

Current implemented slice:
- PostgreSQL + TimescaleDB
- Redis Streams
- Web Backend (FastAPI, 6 domains: health, plugins, devices, telemetry, alerts, dashboards)
- Ingestor worker (telemetry consumer + registration consumer)
- Plugins worker (supervisor + subprocess launcher)
- Plugin SDK (BasePlugin, DevicePlugin, IntegrationPlugin, PluginContext)
- Built-in demo_sender device plugin (generates synthetic telemetry)
- Registration stream for idempotent plugin/device/sensor metadata upserts

Anything not explicitly fixed above should be treated as:

> [this part is not currently implemented, will be replaced with details of internals later]
