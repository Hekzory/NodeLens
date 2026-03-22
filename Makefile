.PHONY: up down down-v logs logs-ingestor logs-plugins ps restart seed

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

ps:
	docker compose ps

restart:
	docker compose restart ingestor plugins

seed:
	docker compose run --rm seed

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
