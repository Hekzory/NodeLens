"""Email integration plugin — SMTP delivery via aiosmtplib.

Channel config keys (all but `to` optional):
    to:        str   — recipient address (required)
    smtp_host: str   — empty/missing → look up the recipient's MX record and
                       deliver direct (no auth, no TLS). Set explicitly to
                       use a relay (your provider's submission server, a
                       local catcher, etc.).
    smtp_port: int   — defaults: 25 (MX), 465 (use_tls), 587 (start_tls), else 25.
    from:      str   — defaults to "alerts@nodelens.local".
    subject:   str   — defaults to "[NodeLens] <rule_name>".
    username:  str   — SMTP auth username (omit for no auth).
    password:  str   — SMTP auth password / app password (omit for no auth).
    use_tls:   bool  — implicit TLS from connect (typical port 465).
    start_tls: bool  — STARTTLS upgrade after greeting (typical port 587).

Direct-MX caveats (when smtp_host is empty):
    - Outbound port 25 must not be blocked by your ISP / cloud provider.
    - Mail will likely land in spam (no SPF/DKIM, no rDNS).
    - Many big providers (Gmail, Yandex, Outlook) tarpit unauthenticated
      connections from residential IPs — use authenticated submission instead.

Authenticated submission example (Yandex):
    smtp_host: smtp.yandex.ru
    smtp_port: 465
    username:  your-email@yandex.ru
    password:  <app password from id.yandex.ru>
    use_tls:   true
"""

from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage
from typing import Any

import aiosmtplib

from nodelens.schemas.events import AlertMessage
from nodelens.sdk.integration_plugin import IntegrationPlugin
from nodelens.sdk.integration_runtime import run_dispatch_loop

logger = logging.getLogger("nodelens.plugin.email")


def _resolve_mx_sync(domain: str) -> str | None:
    """Return the lowest-preference MX hostname for ``domain``, or None on failure."""
    import dns.resolver

    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
    except Exception as exc:
        logger.warning("MX lookup failed for %s: %s", domain, exc)
        return None
    records = sorted(answers, key=lambda r: r.preference)
    if not records:
        return None
    return str(records[0].exchange).rstrip(".")


async def _resolve_mx(domain: str) -> str | None:
    return await asyncio.to_thread(_resolve_mx_sync, domain)


def _default_port(use_tls: bool, start_tls: bool) -> int:
    if use_tls:
        return 465
    if start_tls:
        return 587
    return 25


class EmailIntegrationPlugin(IntegrationPlugin):
    name = "email"
    version = "0.1.0"

    def __init__(self) -> None:
        super().__init__()
        # Plugin-level defaults populated by ``configure``. Each key here may
        # be filled in by the operator via the plugin-config UI; channel-level
        # config still wins on a per-key basis.
        self._defaults: dict[str, Any] = {}

    async def configure(self, settings: dict[str, Any]) -> None:
        self._defaults = dict(settings or {})
        if self._defaults:
            logger.info(
                "Email defaults loaded: from=%s host=%s port=%s use_tls=%s password=%s",
                self._defaults.get("default_from") or "(unset)",
                self._defaults.get("smtp_host") or "(unset)",
                self._defaults.get("smtp_port") or "(auto)",
                bool(self._defaults.get("use_tls")),
                "(set)" if self._defaults.get("smtp_password") else "(unset)",
            )

    async def start(self) -> None:
        await run_dispatch_loop(self, self.ctx.plugin_id)

    async def stop(self) -> None:
        return

    async def send(self, channel_config: dict[str, Any], message: AlertMessage) -> bool:
        try:
            to_addr = channel_config["to"]
        except KeyError:
            logger.error("Channel config missing required 'to' field")
            return False

        # Channel config wins; fall back to plugin-level defaults; final
        # fallback to the historical hard-coded values so unconfigured
        # deployments behave exactly as before.
        defaults = self._defaults
        host = (
            channel_config.get("smtp_host")
            or defaults.get("smtp_host")
            or ""
        ).strip()
        port = int(
            channel_config.get("smtp_port")
            or defaults.get("smtp_port")
            or 0
        )
        from_addr = (
            channel_config.get("from")
            or defaults.get("default_from")
            or "alerts@nodelens.local"
        )
        subject = channel_config.get("subject") or f"[NodeLens] {message.rule_name}"
        username = channel_config.get("username") or None
        password = (
            channel_config.get("password")
            or defaults.get("smtp_password")
            or None
        )
        # Treat a missing key as "use plugin default"; an explicit False on
        # the channel disables TLS even if the plugin default has it on.
        if "use_tls" in channel_config:
            use_tls = bool(channel_config["use_tls"])
        else:
            use_tls = bool(defaults.get("use_tls", False))
        start_tls = bool(channel_config.get("start_tls", False))

        if not host:
            domain = to_addr.rsplit("@", 1)[-1]
            resolved = await _resolve_mx(domain)
            if resolved is None:
                logger.error("Could not resolve MX for domain %s — cannot deliver", domain)
                return False
            host = resolved
            port = port or 25
            # Direct-MX path is plain SMTP; ignore TLS/auth flags.
            use_tls = False
            start_tls = False
            username = None
            password = None
            logger.info("Auto-resolved MX for %s → %s:%d", domain, host, port)
        elif not port:
            port = _default_port(use_tls, start_tls)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(
            f"Rule: {message.rule_name}\n"
            f"Device: {message.device_name}\n"
            f"Value: {message.triggered_value}\n"
            f"At: {message.triggered_at.isoformat()}\n\n"
            f"{message.message}\n"
        )

        smtp_kwargs: dict[str, Any] = {
            "hostname": host,
            "port": port,
            "use_tls": use_tls,
            "start_tls": start_tls,
            "timeout": 15,
        }
        if username and password:
            smtp_kwargs["username"] = username
            smtp_kwargs["password"] = password

        try:
            await aiosmtplib.send(msg, **smtp_kwargs)
        except Exception:
            logger.exception("Failed to send alert email to %s via %s:%s", to_addr, host, port)
            return False

        logger.info("Sent alert email to %s via %s:%d (rule=%s)", to_addr, host, port, message.rule_name)
        return True
