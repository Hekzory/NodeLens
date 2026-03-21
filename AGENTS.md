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
  - Ingestor
- `docker-compose.yml` currently starts only those 3 services.
- The ingestor currently also runs a **temporary fake publisher** for test telemetry so the Redis → Ingestor → DB pipeline can be verified before plugins are implemented.
- Metadata required for ingestion (`plugins`, `devices`, `sensors`) is currently created by `scripts/seed_db.py`, **not** by the ingestor.
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
   - React + TypeScript
   - built during Docker image build
   - served by nginx
   - talks to backend over HTTP only

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
- However, the **currently implemented runtime subset** is only:
  1. PostgreSQL + TimescaleDB
  2. Redis Streams
  3. Ingestor
- Frontend, web backend, MQTT broker usage, alert processor, and plugins worker are not yet active runtime components in the current iteration.

---

## Core design intent

### Stack
- Backend/workers: Python 3.13
- Dependency management: uv + `backend/pyproject.toml`
- Web API: FastAPI
- Database: PostgreSQL + TimescaleDB extension
- Event bus: Redis Streams
- MQTT: Mosquitto
- Frontend: React + TypeScript
- Deployment: Docker Compose

Current core Python deps for the implemented part:
- `sqlalchemy[asyncio] >= 2.0.48`
- `asyncpg >= 0.31.0`
- `redis >= 7.3.0`
- `pydantic == 2.12.5`
- `pydantic-settings == 2.13.1`

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
4. No WebSocket requirement is planned at this stage

### Currently implemented first iteration
1. `scripts/seed_db.py` creates demo rows in:
   - `plugins`
   - `devices`
   - `sensors`
2. The temporary fake publisher publishes synthetic telemetry into Redis stream `telemetry_events`
3. Ingestor consumes that stream through consumer group `ingest_group`
4. Ingestor parses and validates each event
5. Ingestor checks that:
   - `device_id` is a valid UUID
   - `sensor_id` is a valid UUID
   - `sensor_id` exists
   - the sensor belongs to the given device
6. Ingestor writes accepted rows into the `telemetry` hypertable

Important current semantics:
- `TelemetryEvent.device_id` is a stringified internal UUID from `devices.id`
- `TelemetryEvent.sensor_id` is a stringified internal UUID from `sensors.id`
- these are **not** external IDs in the current iteration

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
- reads telemetry events from Redis
- writes telemetry into TimescaleDB
- should remain focused on durable ingestion
- should validate event references before insert
- should **not** create plugins, devices, or sensors based on telemetry events
- metadata/bootstrap logic belongs to setup/seed scripts or future dedicated flows, not to the ingestor

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

Examples:
- MQTT plugin
- HTTP poller plugin
- [future examples not currently implemented]

### 2. Integration plugins
Purpose:
- provide alert outputs / destinations

Examples:
- Telegram
- Email/SMTP
- [future examples not currently implemented]

### Plugin placement
- user-facing plugin folders live under root `plugins/`
- shared Python SDK / interfaces live under `backend/nodelens/sdk/`

### Plugin expectations
- plugins should have explicit metadata/manifest
- plugin configuration should be manageable through the web backend/UI
- runtime lifecycle should be supervised by the plugins worker

Exact manifest shape:
- [this part is not currently implemented, will be replaced with details of internals later]

Exact plugin lifecycle and hot-reload behavior:
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
- `nodelens/config.py` → settings
- `nodelens/constants.py` → stream/group constants
- `nodelens/db` → SQLAlchemy base, async session, models
- `nodelens/redis` → Redis client + stream helpers
- `nodelens/schemas/events.py` → current telemetry contract
- `nodelens/workers/ingestor` → current runnable worker

Planned but not implemented yet:
- `nodelens/api` → FastAPI service
- `nodelens/workers/alerts` → alert worker
- `nodelens/workers/plugin_runner` → plugin supervisor/runner
- `nodelens/sdk` → plugin SDK
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

Other script behavior:
- [this part is not currently implemented, will be replaced with details of internals later]

### `/tests`
Unit/API/integration test placeholders

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
- [this part is not currently implemented, will be replaced with details of internals later]

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

Current Timescale behavior:
- `telemetry` is converted into a hypertable partitioned by `time`

Full future application schema beyond this subset:
- [this part is not currently implemented, will be replaced with details of internals later]

### `backend/nodelens/redis`
Redis connection and stream helpers.

Current implemented stream structure:
- stream name: `telemetry_events`
- consumer group: `ingest_group`
- consumer name: `ingestor-1`

Current serialized event fields in Redis:
- `device_id`
- `sensor_id`
- `value`
- `timestamp`

Implemented concerns:
- Redis connection helper
- stream publish helper
- consumer-group creation helper
- stream read helper
- ack helper

Other stream contracts:
- [this part is not currently implemented, will be replaced with details of internals later]

### `backend/nodelens/schemas`
Shared Pydantic/data contracts.

Current implemented schema definition:

```python
@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    device_id: str
    sensor_id: str
    value: float
    timestamp: datetime
```

Current semantics:

- device_id = stringified devices.id
- sensor_id = stringified sensors.id

Currently implemented concerns:

- telemetry event contract for Redis publisher/consumer pipeline

Other API / plugin / alert schemas:

- [this part is not currently implemented, will be replaced with details of internals later]


### `backend/nodelens/sdk`
Plugin authoring surface.

Expected concerns:
- device plugin base interface
- integration plugin base interface
- plugin context object
- common exceptions/events

Exact SDK interface:
- [this part is not currently implemented, will be replaced with details of internals later]

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
- [this part is not currently implemented, will be replaced with details of internals later]

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
- [this part is not currently implemented, will be replaced with details of internals later]

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
  - `ingestor`

Current relevant env vars:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL`
- `REDIS_URL`
- `LOG_LEVEL`

Current useful commands:
- `make up`
- `make bootstrap`
- `make seed`
- `make init-db`
- `make logs-ingestor`
- `make query-devices`
- `make query-sensors`
- `make query-seed`
- `make query-telemetry`
- `make redis-stream`

Future full 8-service compose layout:
- [this part is not currently implemented, will be replaced with details of internals later]

---

## What future agents should NOT assume

Do not assume any of the following already exist unless they are explicitly implemented in code:
- authentication system
- finalized full application database schema beyond the currently implemented ingestion subset
- finalized Redis/event contracts beyond the currently implemented telemetry ingestion contract
- finished API routes
- plugin hot-reloading
- plugin security sandboxing
- detailed alert delivery engine
- dashboard widget persistence logic
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
- ingestor worker
- seed/init scripts
- temporary fake publisher for telemetry generation

Anything not explicitly fixed above should be treated as:

> [this part is not currently implemented, will be replaced with details of internals later]
