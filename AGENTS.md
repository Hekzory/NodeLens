# AGENTS.md

## Project identity

**Name:** NodeLens
**Type:** Diploma project
**Official theme:** “A web application for monitoring IoT telemetry with intelligent alert processing”

## Current status

This repository is currently a **scaffold / structure-first project**.

Important:
- Many files may exist but be empty.
- File presence does **not** imply implementation exists.
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

---

## Core design intent

### Stack
- Backend/workers: Python
- Web API: FastAPI
- Database: PostgreSQL + TimescaleDB extension
- Event bus: Redis Streams
- MQTT: Mosquitto
- Frontend: React + TypeScript
- Deployment: Docker Compose

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
Shared Python codebase:
- `nodelens/api` → FastAPI service
- `nodelens/workers/ingestor` → ingest worker
- `nodelens/workers/alerts` → alert worker
- `nodelens/workers/plugin_runner` → plugin supervisor/runner
- `nodelens/db` → DB layer
- `nodelens/redis` → Redis helpers
- `nodelens/schemas` → API/internal contracts
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
Utility scripts for setup/seed/health

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

Expected concerns:
- SQLAlchemy models
- sessions/engines
- telemetry storage model
- app metadata model

Exact schema:
- [this part is not currently implemented, will be replaced with details of internals later]

### `backend/nodelens/redis`
Redis connection and stream helpers.

Expected concerns:
- stream read/write helpers
- consumer-group handling
- event serialization support

Exact stream structure:
- [this part is not currently implemented, will be replaced with details of internals later]

### `backend/nodelens/schemas`
Shared Pydantic/data contracts.

Expected concerns:
- API request/response schemas
- telemetry event contract
- plugin config schemas
- alert schemas

Exact schema definitions:
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

Exact compose service definitions and env vars:
- [this part is not currently implemented, will be replaced with details of internals later]

---

## What future agents should NOT assume

Do not assume any of the following already exist unless they are explicitly implemented in code:
- authentication system
- finalized database schema
- finalized Redis event schema
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

Most of the repository is currently structure only.

Anything not explicitly fixed above should be treated as:

> [this part is not currently implemented, will be replaced with details of internals later]