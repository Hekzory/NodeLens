.PHONY: up up-dev down down-v pull build build-dev \
        logs logs-ingestor logs-plugins logs-api logs-alerts logs-frontend \
        ps restart restart-api restart-alerts \
        api-docs curl-health curl-health-db curl-plugins curl-devices \
        test pytest lint lint-fix \
        loadtest-up loadtest-up-dev loadtest loadtest-down \
        migrate migration migrate-down \
        redis-stream redis-registration \
        query-telemetry query-devices query-sensors query-plugins

# ── BuildKit / Compose settings ──────────────────────────────────
export DOCKER_BUILDKIT       := 1
export COMPOSE_DOCKER_CLI_BUILD := 1

COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

test:
	uv run --project backend python scripts/test_report.py

pytest:
	cd backend && uv run pytest tests/ -v

lint:
	cd backend && uv run ruff check .

lint-fix:
	cd backend && uv run ruff check --fix .

# ── Default operator path ────────────────────────────────────────
# Pull pre-built images from GHCR for ingestor/api/alerts/frontend, then
# bring up the stack. The `--build` flag (without a service arg) only builds
# services that have a `build:` directive in compose — after the flip, that's
# only `plugins` (the one service that bakes in per-deployment plugin
# requirements). Everything else uses the just-pulled image.
up:
	docker compose pull
	docker compose up -d --build

# Refresh registry images without restarting anything.
pull:
	docker compose pull

# Backwards-compatible alias for `make build`. Pulls registry images and
# rebuilds the locally-built `plugins` worker. Use `make build-dev` for the
# old "build everything from source" behavior.
build: pull
	docker compose build plugins

# ── Contributor / dev path ───────────────────────────────────────
# Rebuild every service from local source. Use this when you have edits in
# backend/, frontend/, or deploy/ that need to land in the running stack.
up-dev:
	$(COMPOSE_DEV) up -d --build

build-dev:
	$(COMPOSE_DEV) build --parallel

# ── Lifecycle ────────────────────────────────────────────────────

down:
	docker compose down

down-v:
	docker compose down -v

logs:
	docker compose logs -f

logs-ingestor:
	docker compose logs -f ingestor

logs-plugins:
	docker compose logs -f plugins

logs-api:
	docker compose logs -f api

logs-alerts:
	docker compose logs -f alerts

logs-frontend:
	docker compose logs -f frontend

ps:
	docker compose ps

restart:
	docker compose restart ingestor alerts plugins api

restart-api:
	docker compose restart api

restart-alerts:
	docker compose restart alerts

api-docs:
	@echo "Swagger UI: http://localhost:8000/docs"
	@echo "ReDoc:      http://localhost:8000/redoc"

curl-health:
	curl -s http://localhost:8000/api/health | python3 -m json.tool

curl-health-db:
	curl -s http://localhost:8000/api/health/db | python3 -m json.tool

curl-plugins:
	curl -s http://localhost:8000/api/plugins | python3 -m json.tool

curl-devices:
	curl -s http://localhost:8000/api/devices | python3 -m json.tool

query-telemetry:
	docker compose exec postgres psql -U nodelens -d nodelens \
		-c "SELECT t.time, s.key, d.name, t.value_numeric \
		    FROM telemetry t \
		    JOIN sensors s ON s.id = t.sensor_id \
		    JOIN devices d ON d.id = s.device_id \
		    ORDER BY t.time DESC LIMIT 10;"

query-devices:
	docker compose exec postgres psql -U nodelens -d nodelens \
		-c "SELECT id, external_id, name, last_seen FROM devices;"

query-sensors:
	docker compose exec postgres psql -U nodelens -d nodelens \
		-c "SELECT s.id, s.key, s.unit, d.name AS device \
		    FROM sensors s JOIN devices d ON d.id = s.device_id;"

query-plugins:
	docker compose exec postgres psql -U nodelens -d nodelens \
		-c "SELECT id, module_name, display_name, version, is_active FROM plugins;"

# ── Database migrations (Alembic) ──────────────────────────────────
# The ingestor auto-runs `alembic upgrade head` on startup, so a plain
# `make restart` (or `make up` after a pull) is usually enough. The
# targets below are for the cases where you want explicit control.
#
# NOTE: these targets exec inside the running ingestor. After `make up`
# that's the *published* image — your locally-added migration files won't
# exist inside it. To test new migrations against your local code, run
# `make up-dev` first so the ingestor was built from your tree.

# Apply pending migrations now, without restarting workers.
# Use after: pulling code that adds a new versions/*.py and you don't
# want to wait for the next ingestor restart. Idempotent — no-op if
# the DB is already at head.
migrate:
	docker compose exec ingestor alembic upgrade head

# Generate a new migration file from current model changes.
# Use after: editing a SQLAlchemy model (add/drop/rename a column,
# change nullability, etc.). Alembic diffs your models against the
# live DB and writes a versions/<rev>_<slug>.py with the upgrade()
# and downgrade() ops pre-filled. ALWAYS read the generated file
# before committing — autogenerate misses TimescaleDB hypertables,
# server defaults, and some constraint changes.
# Example: make migration MSG="add severity to alert_rules"
migration:
	@if [ -z "$(MSG)" ]; then echo "Usage: make migration MSG=\"description\""; exit 1; fi
	docker compose exec ingestor alembic revision --autogenerate -m "$(MSG)"

# Roll back the most recent migration.
# Use after: applying a migration you regret (bad autogenerate, wrong
# column type, etc.). Runs the migration's downgrade() function and
# moves alembic_version back one step. Then fix the model + regenerate.
migrate-down:
	docker compose exec ingestor alembic downgrade -1

redis-stream:
	docker compose exec redis redis-cli XLEN telemetry_events

redis-registration:
	docker compose exec redis redis-cli XLEN registration_events

# ── Load testing (isolated stack, ephemeral volumes) ───────────────

LOADTEST_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.loadtest.yml
LOADTEST_COMPOSE_DEV = $(LOADTEST_COMPOSE) -f docker-compose.dev.yml

# Loadtest against the *published* ingestor image (matches what operators run).
loadtest-up:
	$(LOADTEST_COMPOSE) pull ingestor
	$(LOADTEST_COMPOSE) up -d postgres redis ingestor

# Opt-in: loadtest against the *locally-built* ingestor (use when you have
# unmerged ingestor changes you want to benchmark).
loadtest-up-dev:
	$(LOADTEST_COMPOSE_DEV) up -d --build postgres redis ingestor

loadtest:
	uv run --project backend python scripts/loadtest.py $(ARGS)

loadtest-down:
	$(LOADTEST_COMPOSE) down -v
