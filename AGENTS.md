# AGENTS.md

## Project identity

**Name:** NodeLens
**Type:** Diploma project
**Official theme:** “A web application for monitoring IoT telemetry with intelligent alert processing”

## Current status

This repository is currently a **partially implemented project**.

Important:
- Many files may still exist but be empty.
- File presence does **not** imply implementation exists.
- A minimal runnable slice **does exist now**:
  - PostgreSQL + TimescaleDB
  - Redis Streams
  - Web backend (FastAPI)
  - Ingestor
  - Plugins worker (with a built-in demo_sender device plugin and an `email` integration plugin)
  - Alert processor (consumes telemetry, evaluates rules, dispatches via integration plugins)
  - Frontend (React + nginx)
- `docker-compose.yml` currently starts 8 services: `postgres`, `redis`, `mosquitto`, `ingestor`, `alerts`, `plugins`, `api`, `frontend`.
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

There are **8 containers** (auth is enforced at the API layer; workers and Redis/MQTT do not authenticate):

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
  3. MQTT broker (Eclipse Mosquitto)
  4. Web backend (FastAPI)
  5. Ingestor
  6. Alert processor
  7. Plugins worker (with `email` integration plugin)
  8. Frontend (React, served by nginx)
- MQTT broker (Eclipse Mosquitto 2.0) is deployed and reachable at `mosquitto:1883` on the compose network (anonymous, no TLS). No MQTT device plugin consumes from it yet — see plugin model section.

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
2. **Alert processor** consumes events from Redis via its own consumer group (`alert_group`)
3. Alert processor also reads DB state when rules require time-window checks
4. If a rule triggers:
   - cooldown check (last fire within `cooldown_seconds` blocks repeat) via `alert_history`
   - write `alert_history` row
   - publish a dispatch event to the `alert_dispatch_events` Redis stream, one per active linked notification channel
   - the relevant integration plugin (running inside the plugins worker) consumes its own consumer group on that stream and calls its `send()` method

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
- on startup, applies TimescaleDB columnar compression settings + (re-)installs the compression and retention policies from `nodelens.config.settings` (idempotent). Owns these policies — other workers do not reapply them.
- runs a periodic disk-budget enforcer (`workers/ingestor/retention.py`): every `RETENTION_CHECK_INTERVAL_SECONDS`, drops the oldest chunks if total telemetry size exceeds `DISK_BUDGET_GB` (with a 5% headroom to avoid oscillation). Complements — does not replace — the time-based retention policy.
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

Mechanism:
- Each integration plugin runs as a subprocess inside the plugins worker (same supervisor as device plugins).
- The plugin's `start()` typically calls `run_dispatch_loop(self, self.ctx.plugin_id)` from the SDK, which subscribes to the `alert_dispatch_events` Redis stream via a per-plugin consumer group (`dispatch_<module_name>`), filters by `plugin_id`, decodes the channel config + `AlertMessage`, and invokes `self.send(channel_config, message)`.

Examples:
- `email` (built-in) — plain SMTP via aiosmtplib (no auth, no TLS verification). Channel config: `to`, `smtp_host`, `smtp_port`, `from`, `subject` (optional).

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
- See "Integration plugins" above and "Alert dispatch stream" under `nodelens/redis`. Concretely: the alert worker `xadd`s one event per linked channel to `alert_dispatch_events`; each integration plugin subprocess (running inside the plugins worker) consumes its own per-plugin consumer group, filters by `plugin_id`, and invokes its `send()` method via the SDK helper `run_dispatch_loop`.

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
- `nodelens/config.py` → env-sourced defaults (connection strings + the seeds for every DB-overridable runtime setting). Connection strings (`DATABASE_URL`, `REDIS_URL`, `API_HOST`, `API_PORT`, `PLUGINS_DIR`, `LOG_LEVEL`) stay env-only.
- `nodelens/constants.py` → stream/group constants for `telemetry_events`, `registration_events`, and `alert_dispatch_events`
- `nodelens/db` → SQLAlchemy base, async session, models (Plugin, Device, Sensor, TelemetryRecord, AlertRule, AlertHistory, NotificationChannel, AlertRuleChannel, Dashboard, DashboardWidget, SystemSetting)
- `nodelens/system_settings` → DB-backed runtime configuration: `REGISTRY` (declarative metadata per setting), `RuntimeSettings` (per-process TTL cache over `system_settings` table, falls back to `config.settings` defaults), module-level singleton `runtime_settings`. Hot-loop call sites (`workers/ingestor/retention.py`, `api/routes/devices.py`, etc.) read through this cache so changes apply within the cache TTL; settings consumed once-at-startup are flagged `requires_restart` in the registry.
- `nodelens/auth` → password hashing (`bcrypt`), session-cookie auth dependencies (`get_current_user`, `get_current_user_optional`). Uses Starlette's `SessionMiddleware` (signed cookie) — no session table; `users.is_active=False` or row deletion is what locks a user out.
- `nodelens/redis` → Redis client + stream helpers + shared `parse_telemetry_event`
- `nodelens/schemas/events.py` → TelemetryEvent, AlertMessage, RegisterPluginEvent, RegisterDeviceEvent, RegisterSensorEvent
- `nodelens/sdk` → plugin SDK (BasePlugin, DevicePlugin, IntegrationPlugin, PluginContext, exceptions, `run_dispatch_loop`)
- `nodelens/workers/ingestor` → telemetry consumer, registration consumer, writer with validation
- `nodelens/workers/alerts` → alert engine (consumer + evaluator + dispatcher) plus a periodic `no_data` scanner co-routine; supports `instant`, `aggregated`, and `no_data` rule kinds with cooldown
- `nodelens/workers/plugin_runner` → plugin supervisor, loader, single-plugin subprocess runner

- `tests/` → unit tests (pytest + pytest-asyncio); covers event parsing, writer validation pipeline, registration coercion, plugin loader/discovery, alert evaluator + dispatcher, email plugin, and API route logic (alerts, channels, telemetry, dashboards)
- `alembic/` → schema migrations (async-aware env.py reading `DATABASE_URL` from `nodelens.config.settings`). The ingestor runs `alembic upgrade head` on startup via `init_models`. Pre-Alembic deployments are auto-stamped to baseline before upgrade, so existing DBs upgrade cleanly without recreating tables.

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

**Auth** `auth.py` *(public — `/setup` and `/login`; the rest require a session)*
- `GET /api/auth/status` — `{setup_required, authenticated, user}` (drives the SPA's login/setup gate)
- `POST /api/auth/setup` — create the first user (409 if any user already exists); also opens a session
- `POST /api/auth/login` — authenticate; sets the `nodelens_session` signed cookie
- `POST /api/auth/logout` — clear `request.session`
- `GET /api/auth/me` — current user
- `POST /api/auth/password` — change own password (verifies old)

**Users** `users.py` *(all auth-gated; no roles — every signed-in user can manage users)*
- `GET /api/users` — list
- `POST /api/users` — create
- `PATCH /api/users/{user_id}` — update `username` / `is_active` (rejects deactivating self or the last active user)
- `DELETE /api/users/{user_id}` — hard delete (rejects deleting self or the last active user)
- `POST /api/users/{user_id}/password` — admin password reset (no old-password check)

**Health** `health.py` *(public — uptime probes)*
- `GET /api/health` — liveness
- `GET /api/health/db` — DB check
- `GET /api/health/redis` — Redis check
- `GET /api/health/storage` — telemetry hypertable size, compression breakdown, and configured retention/compression/disk-budget policy

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
- `GET /api/alerts/rules/{rule_id}/channels` — list channels linked to rule
- `PUT /api/alerts/rules/{rule_id}/channels` — replace the linked-channel set
- `GET /api/alerts/history` — list fired alerts (paginated, filterable)
- `POST /api/alerts/history/{history_id}/acknowledge` — mark acknowledged

**Channels** `channels.py`
- `GET /api/alerts/channels` — list (filter by `plugin_id`, `is_active`)
- `POST /api/alerts/channels` — create (validates plugin is `type=integration`)
- `GET /api/alerts/channels/{channel_id}` — get single
- `PATCH /api/alerts/channels/{channel_id}` — partial update
- `DELETE /api/alerts/channels/{channel_id}` — delete (cascades to `alert_rule_channels`)

**Dashboards** `dashboards.py`
- `GET /api/dashboards` — list dashboards
- `POST /api/dashboards` — create dashboard
- `GET /api/dashboards/{dashboard_id}` — detail with widgets
- `PATCH /api/dashboards/{dashboard_id}` — partial update
- `DELETE /api/dashboards/{dashboard_id}` — delete dashboard
- `POST /api/dashboards/{dashboard_id}/widgets` — add widget
- `PATCH /api/dashboards/{dashboard_id}/widgets/{widget_id}` — update widget config/layout
- `DELETE /api/dashboards/{dashboard_id}/widgets/{widget_id}` — remove widget

**System settings** `system_settings.py`
- `GET /api/system/settings` — list all registered settings with current value, default, metadata, and `is_default` flag
- `GET /api/system/settings/{key}` — single setting
- `PATCH /api/system/settings` — bulk update (`{updates: {key: value, …}}`); validates per-key + cross-field; returns `{updated, requires_restart_keys}`
- `DELETE /api/system/settings/{key}` — drop the override row, value reverts to the registry default

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
  - TimescaleDB hypertable on `time`; columnar compression enabled with `segmentby=sensor_id, orderby=time DESC`. The ingestor calls `apply_storage_policies()` on startup, which (re-)installs Timescale's compression policy (`compress_after = COMPRESSION_AFTER_DAYS`) and retention policy (`drop_after = RETENTION_DAYS`). A separate ingestor task (`workers/ingestor/retention.py`) enforces the `DISK_BUDGET_GB` ceiling.

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

- `notification_channels`
  - `id: UUID` (PK)
  - `name: VARCHAR` (unique)
  - `plugin_id: UUID` (FK → `plugins.id`, integration plugin)
  - `config: JSONB`
  - `is_active: BOOLEAN`
  - `created_at`, `updated_at: TIMESTAMPTZ`

- `alert_rule_channels` (M2M)
  - `rule_id: UUID` (FK → `alert_rules.id`, ON DELETE CASCADE)
  - `channel_id: UUID` (FK → `notification_channels.id`, ON DELETE CASCADE)
  - composite PK

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

- `system_settings`
  - `key: VARCHAR(100)` (PK)
  - `value: JSONB`
  - `updated_at: TIMESTAMPTZ`
  - Sparse: a row's presence means an operator override; a missing key means "use registry default" (which is itself sourced from `nodelens.config.settings`). Authoritative metadata (label, type, default, validation, `requires_restart`) lives in the Python registry — only user-set values live in the DB.

- `users`
  - `id: UUID` (PK)
  - `username: VARCHAR(64)` (unique, indexed; pattern `^[A-Za-z0-9_.\-]+$`)
  - `password_hash: VARCHAR(255)` (bcrypt, 72-byte input cap enforced via Pydantic schema)
  - `is_active: BOOLEAN` (false locks the user out without deleting the row; deactivation/deletion of the last active user is rejected by the API)
  - `created_at, updated_at, last_login_at: TIMESTAMPTZ`
  - No session table — sessions are signed cookies via Starlette's `SessionMiddleware`. Cookie name `nodelens_session`, default lifetime 30 days; signing key from `SESSION_SECRET` env var (or an ephemeral random one with a startup warning).

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

**Alert dispatch stream:**
- stream name: `alert_dispatch_events`
- one consumer group per integration plugin: `dispatch_<module_name>` (e.g. `dispatch_email`)
- consumer name: `<module_name>-1`
- fields: `plugin_id`, `channel_id`, `channel_config_json`, `alert_message_json`
- integration plugins skip + ack events whose `plugin_id` does not match their own; on matches they decode the JSON fields and call `IntegrationPlugin.send(channel_config, message)`

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
- Rules are persisted via Web Backend API as either `instant` (single realtime value vs threshold), `aggregated` (agg function over a time window `duration_seconds`), or `no_data` (sensor silence detector — keyed off `condition='no_data'`, ignores `rule_type`).
- `instant` rules compare each incoming `value` against `threshold` using `condition` ∈ {gt, lt, gte, lte, eq, neq}.
- `aggregated` rules run `aggregation` ∈ {avg, min, max, sum, count} over `duration_seconds` of `telemetry` history for the sensor on every received event, then compare to `threshold`.
- `condition='no_data'` rules fire when the rule's sensor has produced no telemetry within `duration_seconds`. A scanner co-routine in the alerts worker runs every `NO_DATA_SCAN_INTERVAL_SECONDS` (default 5s). The API rejects `no_data` with `duration_seconds <= 0` (422) and rejects `aggregation` set together with `condition='no_data'` (422). The scanner suppresses fires when (a) the sensor has never reported any telemetry, (b) `now - scanner_start_time < duration_seconds` (post-restart grace), or (c) the engine has not processed any event within `duration_seconds` (pipeline-liveness guard). Triggered_value is set to the elapsed silence in seconds. Re-fires obey `cooldown_seconds`.

Cooldown / acknowledgement behavior:
- Cooldown is enforced by querying `MAX(alert_history.triggered_at) WHERE rule_id=?` on every potential fire; if the last fire was within `cooldown_seconds`, the fire is suppressed.
- On fire: one `alert_history` row is written; one dispatch event is published per active linked channel.
- Acknowledgement: `POST /api/alerts/history/{id}/acknowledge` sets `acknowledged_at`.

Dedup beyond cooldown / dead-letter for failed `send()` / per-channel templating:
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
  - `mosquitto`
  - `ingestor`
  - `alerts`
  - `plugins`
  - `api`
  - `frontend`

Current relevant env vars:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL` *(env-only — connection string)*
- `REDIS_URL` *(env-only — connection string)*
- `LOG_LEVEL` *(env-only)*
- `PLUGINS_DIR` *(env-only — startup discovery path)*
- `API_HOST`, `API_PORT` *(env-only — socket binding)*
- `SESSION_SECRET` *(env-only — signing key for the `nodelens_session` cookie; if unset, an ephemeral one is generated at startup and sessions invalidate on every API restart)*
- `SESSION_COOKIE_NAME`, `SESSION_LIFETIME_DAYS`, `SESSION_COOKIE_SECURE` *(env-only — auth cookie attributes; defaults: `nodelens_session`, 30, false)*
- `CORS_ALLOWED_ORIGINS` *(env-only list — both the CORS allow-list and the CSRF Origin-check allow-list; default `http://localhost,http://localhost:5173`)*

The values below are seed defaults — when a row is present in the `system_settings` table it overrides the env value. Edit them at runtime via `GET/PATCH /api/system/settings` or the System Settings UI:
- `NO_DATA_SCAN_INTERVAL_SECONDS` (alerts worker; default 5; restart required)
- `RETENTION_DAYS` (telemetry retention policy; default 365 — diploma NF-6; restart required)
- `COMPRESSION_AFTER_DAYS` (compress chunks older than this; default 7; must be `< RETENTION_DAYS`; restart required)
- `DISK_BUDGET_GB` (hard upper bound on telemetry on-disk size; default 30 — diploma NF-7; applies live within the runtime-settings cache TTL)
- `RETENTION_CHECK_INTERVAL_SECONDS` (disk-budget enforcer cadence; default 3600; restart required)
- `ONLINE_THRESHOLD_MINUTES` (device online-status cutoff; default 30; applies live)
- `FRONTEND_POLLING_INTERVAL_SECONDS` (dashboard poll cadence; default 10; applies live — frontend updates `QueryClient` on save)

Current useful commands:
- `make up`
- `make down` / `make down-v`
- `make seed`
- `make logs` / `make logs-ingestor` / `make logs-plugins` / `make logs-api` / `make logs-alerts`
- `make restart` / `make restart-api` / `make restart-alerts`
- `make ps`
- `make query-telemetry`
- `make query-devices`
- `make query-sensors`
- `make query-plugins`
- `make redis-stream`
- `make redis-registration`
- `make migrate` / `make migration MSG="..."` / `make migrate-down` (Alembic schema migrations)

Current 8-service compose layout:
- All 8 target services run today (`postgres`, `redis`, `mosquitto`, `ingestor`, `alerts`, `plugins`, `api`, `frontend`). The MQTT broker (Eclipse Mosquitto 2.0) is reachable on the compose network at `mosquitto:1883` (anonymous, no TLS) and persists to the `mosquitto_data` named volume. No MQTT device plugin exists yet, so the broker has no producers or consumers in the current iteration.
- Total `deploy.resources.limits.memory` across the 8 services sums to **5824 MiB**, leaving ~320 MiB headroom under the diploma's 6 GiB runtime cap (NF-8: «до 50 устройств, до 5 активных плагинов»).

---

## What future agents should NOT assume

Do not assume any of the following already exist unless they are explicitly implemented in code:
- finalized full application database schema beyond the implemented subset (ingestion + alerts + dashboards + users)
- finalized Redis/event contracts beyond telemetry, registration, and alert-dispatch
- plugin hot-reloading
- plugin security sandboxing
- retries / dead-letter for failed integration `send()`
- per-channel message templating
- observability stack
- production hardening
- rate limiting on the login endpoint
- "log out everywhere" / per-user session invalidation on password change
- password reset via email
- role-based access control (every authenticated user has full admin rights)

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
- Redis Streams (telemetry, registration, alert dispatch)
- Web Backend (FastAPI, 7 domains: health, plugins, devices, telemetry, alerts, channels, dashboards)
- Ingestor worker (telemetry consumer + registration consumer)
- Alert worker (instant + aggregated event-driven evaluation plus a periodic `no_data` scanner with restart-grace and pipeline-liveness guards, cooldown, dispatch via Redis stream)
- Plugins worker (supervisor + subprocess launcher)
- Plugin SDK (BasePlugin, DevicePlugin, IntegrationPlugin, PluginContext, `run_dispatch_loop`)
- Built-in `demo_sender` device plugin (generates synthetic telemetry)
- Built-in `email` integration plugin (plain SMTP via aiosmtplib)
- Authentication: signed-cookie sessions (Starlette `SessionMiddleware`), bcrypt password hashing, single-role multi-user model, first-run `/setup` gate, defence-in-depth `Origin`-check middleware on state-changing requests
- Frontend MVP (dashboard, devices, plugins, alerts, **system settings**, **users** pages, **/login** + **/setup** gates)
- DB-backed runtime configuration (`system_settings` table + `nodelens.system_settings` registry/service)
- Registration stream for idempotent plugin/device/sensor metadata upserts

Anything not explicitly fixed above should be treated as:

> [this part is not currently implemented, will be replaced with details of internals later]
