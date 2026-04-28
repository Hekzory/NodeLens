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
from nodelens.heartbeat import touch_heartbeat
from nodelens.workers.plugin_runner.db import ensure_plugin_rows, get_plugin_states

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("nodelens.plugin_runner")

RESTART_DELAY_S = 3.0
MONITOR_INTERVAL_S = 2.0

_REQUIRED_MANIFEST_FIELDS = ("id", "name", "type", "entry_point", "display_name", "version")


def discover_plugins(base_dir: Path) -> tuple[dict[str, Path], dict[str, dict]]:
    """Scan ``base_dir`` for plugins with a valid ``manifest.yaml``.

    Returns a tuple of ``(plugin_dirs_by_id, manifests_by_id)``.
    """
    from nodelens.workers.plugin_runner.loader import load_manifest

    plugin_dirs: dict[str, Path] = {}
    manifests: dict[str, dict] = {}

    if not base_dir.exists():
        return plugin_dirs, manifests

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
                pid = str(manifest["id"])
                plugin_dirs[pid] = plugin_dir
                manifests[pid] = manifest
            except Exception as exc:
                logger.warning("Skipping %s — invalid manifest: %s", plugin_dir.name, exc)

    return plugin_dirs, manifests


def start_plugin(plugin_dir: Path) -> subprocess.Popen:
    """Launch a single plugin as a child process."""
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "nodelens.workers.plugin_runner.run_single",
            str(plugin_dir),
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


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
    all_plugins, manifests = discover_plugins(base_dir)

    if not all_plugins:
        logger.warning("No valid plugins found in %s — supervisor will idle.", base_dir)
        try:
            while True:
                touch_heartbeat()
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    logger.info(
        "Discovered %d plugin(s): %s",
        len(all_plugins),
        [p.name for p in all_plugins.values()],
    )

    # Bootstrap a DB row for every discovered plugin so the is_active gate has
    # something to read on a fresh install. on_conflict preserves any manual
    # toggle from the UI.
    try:
        ensure_plugin_rows(manifests)
    except Exception:
        logger.exception("Failed to bootstrap plugin DB rows — proceeding anyway.")

    # Check which plugins are active in DB
    try:
        states = get_plugin_states()
    except Exception:
        logger.warning("Could not query DB for plugin states — starting all discovered plugins.")
        states = dict.fromkeys(all_plugins, (True, 0))

    active_ids = {pid for pid, (active, _) in states.items() if active}
    last_config_version: dict[str, int] = {pid: ver for pid, (_, ver) in states.items()}

    processes: dict[str, subprocess.Popen] = {}
    for plugin_id, plugin_dir in all_plugins.items():
        if plugin_id not in active_ids:
            logger.info("Plugin %s (id=%s) is disabled in DB — skipping.", plugin_dir.name, plugin_id[:8])
            continue
        proc = start_plugin(plugin_dir)
        processes[plugin_id] = proc
        logger.info("Started plugin %s (pid=%d)", plugin_dir.name, proc.pid)

    try:
        cycles_since_db_check = 0
        while True:
            time.sleep(MONITOR_INTERVAL_S)
            touch_heartbeat()
            cycles_since_db_check += 1

            # Check DB for is_active / config_version changes every ~10 seconds
            if cycles_since_db_check >= 5:
                cycles_since_db_check = 0
                try:
                    states = get_plugin_states()
                except Exception as e:
                    logger.warning(f"DB check failed — keeping current state: {e}")
                    states = {pid: (True, last_config_version.get(pid, 0)) for pid in processes}

                active_ids = {pid for pid, (active, _) in states.items() if active}

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

                # Restart plugins whose config_version has changed
                for plugin_id in list(processes.keys()):
                    new_version = states.get(plugin_id, (True, last_config_version.get(plugin_id, 0)))[1]
                    if new_version != last_config_version.get(plugin_id, 0):
                        plugin_dir = all_plugins[plugin_id]
                        logger.info(
                            "Plugin %s config_version changed (%d → %d) — restarting.",
                            plugin_dir.name,
                            last_config_version.get(plugin_id, 0),
                            new_version,
                        )
                        stop_plugin(plugin_dir, processes[plugin_id])
                        proc = start_plugin(plugin_dir)
                        processes[plugin_id] = proc
                        last_config_version[plugin_id] = new_version
                        logger.info("Restarted plugin %s (pid=%d)", plugin_dir.name, proc.pid)
                    else:
                        # Keep the tracker in sync with newly-activated plugins.
                        last_config_version[plugin_id] = new_version

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
