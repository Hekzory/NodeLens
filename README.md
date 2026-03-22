# How to run


```bash
cd NodeLens

# 1. Start postgres + redis + ingestor + plugins worker (tables created automatically)
make up

# 2. Watch telemetry flow (plugin → redis → ingestor → postgres)
make logs-ingestor
#   … Ingested batch: 5 written / 5 received.
#   … Ingested batch: 5 written / 5 received.

# 3. Verify data
make query-devices
make query-sensors
make query-telemetry
make query-plugins

# 4. Check stream backlog
make redis-stream

# Tear down (add -v to also wipe postgres volume)
make down
```