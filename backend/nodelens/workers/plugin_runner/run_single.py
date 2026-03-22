"""
Subprocess entry-point for running a single plugin.

    python -m nodelens.workers.plugin_runner.run_single <plugin_dir>

Loads the manifest, imports the plugin class, creates a ``PluginContext``,
and drives the configure → start → stop lifecycle.
"""

import asyncio
import logging
import sys
from pathlib import Path

from nodelens.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


async def _run(plugin_dir: Path) -> None:
    from nodelens.sdk.context import PluginContext
    from nodelens.workers.plugin_runner.loader import load_manifest, load_plugin_class

    manifest = load_manifest(plugin_dir)
    plugin_name = manifest["name"]
    logger = logging.getLogger(f"nodelens.plugin.{plugin_name}")

    logger.info("Loading plugin from %s", plugin_dir)
    plugin_cls = load_plugin_class(plugin_dir, manifest["entry_point"])
    plugin = plugin_cls()

    ctx = PluginContext(
        redis_url=settings.REDIS_URL,
        plugin_id=str(manifest["id"]),
        plugin_type=manifest["type"],
        module_name=manifest["name"],
        display_name=manifest["display_name"],
        version=manifest["version"],
    )
    await ctx.connect()
    plugin._set_context(ctx)

    logger.info("Configuring plugin %s v%s …", plugin_name, manifest["version"])
    await plugin.configure({})

    logger.info("Starting plugin %s …", plugin_name)
    try:
        await plugin.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Plugin %s interrupted.", plugin_name)
    finally:
        logger.info("Stopping plugin %s …", plugin_name)
        await plugin.stop()
        await ctx.close()
        logger.info("Plugin %s stopped.", plugin_name)


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m nodelens.workers.plugin_runner.run_single <plugin_dir>",
            file=sys.stderr,
        )
        sys.exit(1)

    plugin_dir = Path(sys.argv[1])
    if not plugin_dir.is_dir():
        print(f"Not a directory: {plugin_dir}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_run(plugin_dir))


if __name__ == "__main__":
    main()
