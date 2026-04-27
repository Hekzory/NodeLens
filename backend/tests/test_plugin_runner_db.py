"""Tests for the synchronous plugin-runner DB helpers."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import nodelens.workers.plugin_runner.db as db_module
from tests.conftest import PLUGIN_ID_STR


def _make_session_factory():
    """Mock the SQLAlchemy ``Session(_engine)`` context manager.

    Returns ``(Session_callable_mock, session_mock)`` so callers can drive
    ``session.execute`` and assert on it.
    """
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    begin_ctx = MagicMock()
    begin_ctx.__enter__ = MagicMock(return_value=session)
    begin_ctx.__exit__ = MagicMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)

    Session = MagicMock(return_value=session)
    return Session, session


class TestGetActivePluginIds:
    def test_returns_set_of_string_ids(self):
        Session, session = _make_session_factory()

        plugin_a = uuid.uuid4()
        plugin_b = uuid.uuid4()
        rows = [MagicMock(id=plugin_a), MagicMock(id=plugin_b)]
        session.execute = MagicMock(return_value=iter(rows))

        with patch("sqlalchemy.orm.Session", Session):
            result = db_module.get_active_plugin_ids()

        assert result == {str(plugin_a), str(plugin_b)}
        session.execute.assert_called_once()

    def test_empty_when_no_active_plugins(self):
        Session, session = _make_session_factory()
        session.execute = MagicMock(return_value=iter([]))

        with patch("sqlalchemy.orm.Session", Session):
            result = db_module.get_active_plugin_ids()

        assert result == set()


class TestEnsurePluginRows:
    def test_no_op_for_empty_manifests(self):
        Session, session = _make_session_factory()
        with patch("sqlalchemy.orm.Session", Session):
            db_module.ensure_plugin_rows({})
        Session.assert_not_called()
        session.execute.assert_not_called() if hasattr(session.execute, "assert_not_called") else None

    def test_executes_one_upsert_per_manifest(self):
        Session, session = _make_session_factory()
        session.execute = MagicMock()

        manifests = {
            PLUGIN_ID_STR: {
                "type": "device",
                "name": "demo_sender",
                "display_name": "Demo Sender",
                "description": "  hello  ",
                "version": "0.1.0",
            },
            "20000000-0000-0000-0000-000000000099": {
                "type": "integration",
                "name": "email",
                "display_name": "Email",
                "description": "",
                "version": "0.2.0",
            },
        }

        with patch("sqlalchemy.orm.Session", Session):
            db_module.ensure_plugin_rows(manifests)

        # One execute() call per manifest, all inside one session.
        assert session.execute.call_count == 2
        Session.assert_called_once()

    def test_blank_description_becomes_none(self):
        # The function strips & nulls out empty descriptions; we exercise that branch
        # by inspecting the compiled statement values.
        Session, session = _make_session_factory()
        captured: list = []
        session.execute = MagicMock(side_effect=captured.append)

        manifests = {
            PLUGIN_ID_STR: {
                "type": "device",
                "name": "demo_sender",
                "display_name": "Demo Sender",
                "description": "   ",  # whitespace-only
                "version": "0.1.0",
            },
        }

        with patch("sqlalchemy.orm.Session", Session):
            db_module.ensure_plugin_rows(manifests)

        assert len(captured) == 1
        # The compiled INSERT should have description=None in its parameters.
        compiled = captured[0].compile().params
        assert compiled["description"] is None

    def test_missing_description_field_becomes_none(self):
        Session, session = _make_session_factory()
        captured: list = []
        session.execute = MagicMock(side_effect=captured.append)

        manifests = {
            PLUGIN_ID_STR: {
                "type": "device",
                "name": "demo_sender",
                "display_name": "Demo Sender",
                # description omitted
                "version": "0.1.0",
            },
        }

        with patch("sqlalchemy.orm.Session", Session):
            db_module.ensure_plugin_rows(manifests)

        compiled = captured[0].compile().params
        assert compiled["description"] is None
