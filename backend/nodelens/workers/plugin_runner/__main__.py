"""
Plugin-runner supervisor entry-point.

    python -m nodelens.workers.plugin_runner

Discovers device (and, eventually, integration) plugins under the configured
plugins directory, spawns each one as a separate subprocess, and
monitors / restarts them on failure.

Respects ``Plugin.is_active`` — only starts plugins that are active in the DB.
On each monitor cycle, checks for state changes and stops/starts accordingly.
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

from nodelens.config import settings
from nodelens.workers.plugin_runner.db import get_active_plugin_ids

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("nodelens.plugin_runner")

RESTART_DELAY_S = 3.0
MONITOR_INTERVAL_S = 2.0

_REQUIRED_MANIFEST_FIELDS = ("id", "name", "type", "entry_point", "display_name", "version")


def discover_plugins(base_dir: Path) -> dict[str, Path]:
    """Return ``{plugin_id: plugin_dir}`` for directories with a valid ``manifest.yaml``."""
    from nodelens.workers.plugin_runner.loader import load_manifest

    plugins: dict[str, Path] = {}

    if not base_dir.exists():
        return plugins

    for type_dir in sorted(base_dir.iterdir()):
        if not type_dir.is_dir():
            continue
        for plugin_dir in sorted(type_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            if not (plugin_dir / "manifest.yaml").exists():
                continue
            try:
                manifest = load_manifest(plugin_dir)
                missing = [f for f in _REQUIRED_MANIFEST_FIELDS if f not in manifest]
                if missing:
                    logger.warning(
                        "Skipping %s — missing manifest fields: %s",
                        plugin_dir.name,
                        missing,
                    )
                    continue
                plugins[str(manifest["id"])] = plugin_dir
            except Exception as exc:
                logger.warning("Skipping %s — invalid manifest: %s", plugin_dir.name, exc)

    return plugins


async def _get_active_plugin_ids() -> set[str]:
    """Query the DB for plugin IDs where ``is_active = True``."""
    from sqlalchemy import select

    from nodelens.db.models.plugin import Plugin
    from nodelens.db.session import async_session

    async with async_session() as session:
        result = await session.execute(
            select(Plugin.id).where(Plugin.is_active.is_(True))
        )
        return {str(row.id) for row in result}


def start_plugin(plugin_dir: Path) -> subprocess.Popen:
    """Launch a single plugin as a child process."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "nodelens.workers.plugin_runner.run_single",
            str(plugin_dir),
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    return proc


def stop_plugin(plugin_dir: Path, proc: subprocess.Popen) -> None:
    """Gracefully stop a plugin process."""
    logger.info("Stopping plugin %s (pid=%d)", plugin_dir.name, proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def main() -> None:
    base_dir = Path(settings.PLUGINS_DIR)
    all_plugins = discover_plugins(base_dir)

    if not all_plugins:
        logger.warning("No valid plugins found in %s — supervisor will idle.", base_dir)
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    logger.info(
        "Discovered %d plugin(s): %s",
        len(all_plugins),
        [p.name for p in all_plugins.values()],
    )

    # Check which plugins are active in DB
    try:
        active_ids = get_active_plugin_ids()
    except Exception:
        logger.warning("Could not query DB for active plugins — starting all discovered plugins.")
        active_ids = set(all_plugins.keys())

    processes: dict[str, subprocess.Popen] = {}
    for plugin_id, plugin_dir in all_plugins.items():
        if plugin_id not in active_ids:
            logger.info("Plugin %s (id=%s) is inactive — skipping.", plugin_dir.name, plugin_id[:8])
            continue
        proc = start_plugin(plugin_dir)
        processes[plugin_id] = proc
        logger.info("Started plugin %s (pid=%d)", plugin_dir.name, proc.pid)

    try:
        cycles_since_db_check = 0
        while True:
            time.sleep(MONITOR_INTERVAL_S)
            cycles_since_db_check += 1

            # Check DB for is_active changes every ~10 seconds
            if cycles_since_db_check >= 5:
                cycles_since_db_check = 0
                try:
                    active_ids = get_active_plugin_ids()
                except Exception as e:
                    logger.warning(f"DB check failed — keeping current state: {e}")
                    active_ids = set(processes.keys())

                # Stop plugins that became inactive
                for plugin_id in list(processes.keys()):
                    if plugin_id not in active_ids:
                        plugin_dir = all_plugins[plugin_id]
                        stop_plugin(plugin_dir, processes[plugin_id])
                        del processes[plugin_id]
                        logger.info("Deactivated plugin %s", plugin_dir.name)

                # Start plugins that became active
                for plugin_id in active_ids:
                    if plugin_id in all_plugins and plugin_id not in processes:
                        plugin_dir = all_plugins[plugin_id]
                        proc = start_plugin(plugin_dir)
                        processes[plugin_id] = proc
                        logger.info("Activated plugin %s (pid=%d)", plugin_dir.name, proc.pid)

            # Monitor running processes and restart crashed ones
            for plugin_id, proc in list(processes.items()):
                ret = proc.poll()
                if ret is not None:
                    plugin_dir = all_plugins[plugin_id]
                    logger.warning(
                        "Plugin %s (pid=%d) exited with code %d — restarting in %.0fs …",
                        plugin_dir.name,
                        proc.pid,
                        ret,
                        RESTART_DELAY_S,
                    )
                    time.sleep(RESTART_DELAY_S)
                    new_proc = start_plugin(plugin_dir)
                    processes[plugin_id] = new_proc
                    logger.info(
                        "Restarted plugin %s (pid=%d)",
                        plugin_dir.name,
                        new_proc.pid,
                    )
    except KeyboardInterrupt:
        logger.info("Shutting down plugins …")
        for plugin_id, proc in processes.items():
            plugin_dir = all_plugins[plugin_id]
            logger.info("Terminating %s (pid=%d)", plugin_dir.name, proc.pid)
            proc.terminate()
        for proc in processes.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        logger.info("All plugins stopped.")


if __name__ == "__main__":
    main()
