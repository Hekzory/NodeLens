#!/usr/bin/env python
"""
Seed script — now a lightweight DB-schema initialiser.

Plugin, device, and sensor registration is handled at runtime by the plugins
themselves via the ``registration_events`` Redis stream.  This script only
ensures the database tables and hypertable exist.

    docker compose run --rm seed          (via Makefile: make seed)
"""

import asyncio
import sys
from pathlib import Path

# Ensure the backend package is importable when run from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


async def main() -> None:
    from nodelens.db import init_models
    from nodelens.db.session import engine

    await init_models(engine)
    await engine.dispose()
    print("✔ Database schema initialised.  Plugin data is registered at runtime by plugins.")


if __name__ == "__main__":
    asyncio.run(main())
