"""
Plugin-runner supervisor entry-point.

    python -m nodelens.workers.plugin_runner

Discovers device (and, eventually, integration) plugins under the configured
plugins directory, spawns each one as a separate subprocess, and
monitors / restarts them on failure.
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

from nodelens.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("nodelens.plugin_runner")

RESTART_DELAY_S = 3.0
MONITOR_INTERVAL_S = 2.0

_REQUIRED_MANIFEST_FIELDS = ("id", "name", "type", "entry_point", "display_name", "version")


def discover_plugins(base_dir: Path) -> list[Path]:
    """Return directories that contain a valid ``manifest.yaml``."""
    from nodelens.workers.plugin_runner.loader import load_manifest

    plugins: list[Path] = []

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
                plugins.append(plugin_dir)
            except Exception as exc:
                logger.warning("Skipping %s — invalid manifest: %s", plugin_dir.name, exc)

    return plugins


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


def main() -> None:
    base_dir = Path(settings.PLUGINS_DIR)
    plugin_dirs = discover_plugins(base_dir)

    if not plugin_dirs:
        logger.warning("No valid plugins found in %s — supervisor will idle.", base_dir)
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
        return

    logger.info(
        "Discovered %d plugin(s): %s",
        len(plugin_dirs),
        [p.name for p in plugin_dirs],
    )

    processes: dict[Path, subprocess.Popen] = {}
    for plugin_dir in plugin_dirs:
        proc = start_plugin(plugin_dir)
        processes[plugin_dir] = proc
        logger.info("Started plugin %s (pid=%d)", plugin_dir.name, proc.pid)

    try:
        while True:
            time.sleep(MONITOR_INTERVAL_S)
            for plugin_dir, proc in list(processes.items()):
                ret = proc.poll()
                if ret is not None:
                    logger.warning(
                        "Plugin %s (pid=%d) exited with code %d — restarting in %.0fs …",
                        plugin_dir.name,
                        proc.pid,
                        ret,
                        RESTART_DELAY_S,
                    )
                    time.sleep(RESTART_DELAY_S)
                    new_proc = start_plugin(plugin_dir)
                    processes[plugin_dir] = new_proc
                    logger.info(
                        "Restarted plugin %s (pid=%d)",
                        plugin_dir.name,
                        new_proc.pid,
                    )
    except KeyboardInterrupt:
        logger.info("Shutting down plugins …")
        for plugin_dir, proc in processes.items():
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
