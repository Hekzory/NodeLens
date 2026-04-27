"""Validation tests for notification channel Pydantic schemas."""

import pytest
from pydantic import ValidationError

from nodelens.schemas.notifications import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
    RuleChannelsUpdate,
)
from tests.conftest import PLUGIN_ID


class TestNotificationChannelCreate:
    @pytest.mark.parametrize(
        ("name", "valid"),
        [
            ("ok", True),
            ("", False),
            ("x" * 256, False),
        ],
    )
    def test_name_constraints(self, name, valid):
        if valid:
            ch = NotificationChannelCreate(name=name, plugin_id=PLUGIN_ID)
            assert ch.name == name
        else:
            with pytest.raises(ValidationError):
                NotificationChannelCreate(name=name, plugin_id=PLUGIN_ID)

    def test_defaults(self):
        ch = NotificationChannelCreate(name="ok", plugin_id=PLUGIN_ID)
        assert ch.config == {}
        assert ch.is_active is True

    def test_plugin_id_must_be_uuid(self):
        with pytest.raises(ValidationError):
            NotificationChannelCreate(name="ok", plugin_id="not-a-uuid")


class TestNotificationChannelUpdate:
    def test_all_fields_optional(self):
        u = NotificationChannelUpdate()
        assert u.name is None
        assert u.plugin_id is None
        assert u.config is None
        assert u.is_active is None


class TestRuleChannelsUpdate:
    def test_empty_list_default(self):
        u = RuleChannelsUpdate()
        assert u.channel_ids == []

    def test_invalid_uuid_in_list_rejected(self):
        with pytest.raises(ValidationError):
            RuleChannelsUpdate(channel_ids=["not-a-uuid"])
