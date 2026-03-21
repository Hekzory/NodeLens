#!/usr/bin/env python
"""
Standalone DB bootstrap — creates tables + hypertable without seeding data.

    docker compose exec ingestor python scripts/init_db.py

In normal operation the ingestor performs this automatically on startup,
so running this manually is optional.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


async def main() -> None:
    from nodelens.db import init_models
    from nodelens.db.session import engine

    await init_models(engine)
    await engine.dispose()
    print("✔ Database initialised (tables + hypertable).")


if __name__ == "__main__":
    asyncio.run(main())
