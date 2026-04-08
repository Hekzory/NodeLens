.PHONY: up down down-v logs logs-ingestor logs-plugins logs-api ps restart restart-api seed api-docs curl-health test pytest loadtest-up loadtest loadtest-down

test:
	uv run --project backend python scripts/test_report.py

pytest:
	cd backend && uv run pytest tests/ -v

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

ps:
	docker compose ps

restart:
	docker compose restart ingestor plugins api

restart-api:
	docker compose restart api

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
		-c "SELECT id, external_id, name, is_online, last_seen FROM devices;"

query-sensors:
	docker compose exec postgres psql -U nodelens -d nodelens \
		-c "SELECT s.id, s.key, s.unit, d.name AS device \
		    FROM sensors s JOIN devices d ON d.id = s.device_id;"

query-plugins:
	docker compose exec postgres psql -U nodelens -d nodelens \
		-c "SELECT id, module_name, display_name, version, is_active FROM plugins;"

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
