.PHONY: up down down-v logs logs-ingestor logs-plugins logs-api logs-alerts ps restart restart-api restart-alerts seed api-docs curl-health test pytest lint lint-fix loadtest-up loadtest loadtest-down build migrate migration migrate-down

# ── BuildKit / Compose settings ──────────────────────────────────
export DOCKER_BUILDKIT       := 1
export COMPOSE_DOCKER_CLI_BUILD := 1

test:
	uv run --project backend python scripts/test_report.py

pytest:
	cd backend && uv run pytest tests/ -v

lint:
	cd backend && uv run ruff check .

lint-fix:
	cd backend && uv run ruff check --fix .

build:
	docker compose build --parallel

up:
	docker compose up -d --build

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

seed:
	docker compose run --rm seed

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

loadtest-up:
	$(LOADTEST_COMPOSE) up -d --build postgres redis ingestor

loadtest:
	uv run --project backend python scripts/loadtest.py $(ARGS)

loadtest-down:
	$(LOADTEST_COMPOSE) down -v
