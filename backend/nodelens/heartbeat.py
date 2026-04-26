"""Worker liveness heartbeat — touched by background loops, read by docker healthcheck."""

from pathlib import Path

HEARTBEAT_PATH = Path("/tmp/.healthcheck")


def touch_heartbeat() -> None:
    """Update mtime of the heartbeat file. Workers should call this each loop iteration."""
    HEARTBEAT_PATH.touch()
