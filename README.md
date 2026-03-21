# How to run


```bash
cd NodeLens

# 1. Start postgres + redis + ingestor (tables created automatically)
make up

# 2. Seed the test plugin, devices, and sensors
make seed

# 3. Watch telemetry flow (fake publisher → redis → ingestor → postgres)
make logs-ingestor
#   … Ingested batch: 5 written / 5 received.
#   … Ingested batch: 5 written / 5 received.

# 4. Verify data
make query-devices
make query-sensors
make query-telemetry

# 5. Check stream backlog
make redis-stream

# Tear down (add -v to also wipe postgres volume)
make down
```