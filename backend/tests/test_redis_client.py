"""Tests for the shared async Redis connection helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nodelens.redis import client as redis_client


@pytest.fixture(autouse=True)
def _reset_pool():
    """Make sure the module-level pool is None before and after each test."""
    redis_client._pool = None
    yield
    redis_client._pool = None


class TestGetRedis:
    async def test_creates_pool_on_first_call(self):
        fake = MagicMock(name="redis-conn")
        with patch("nodelens.redis.client.aioredis.from_url", return_value=fake) as from_url:
            r = await redis_client.get_redis()
        assert r is fake
        from_url.assert_called_once()
        # decode_responses is required so xreadgroup yields plain str dicts
        _, kwargs = from_url.call_args
        assert kwargs.get("decode_responses") is True

    async def test_reuses_existing_pool(self):
        fake = MagicMock(name="redis-conn")
        with patch("nodelens.redis.client.aioredis.from_url", return_value=fake) as from_url:
            first = await redis_client.get_redis()
            second = await redis_client.get_redis()
        assert first is second
        from_url.assert_called_once()

    async def test_uses_settings_redis_url(self):
        with patch("nodelens.redis.client.aioredis.from_url", return_value=MagicMock()) as from_url:
            await redis_client.get_redis()
        args, _ = from_url.call_args
        assert args[0] == redis_client.settings.REDIS_URL


class TestCloseRedis:
    async def test_no_op_when_pool_is_none(self):
        # Should not raise when nothing to close.
        await redis_client.close_redis()
        assert redis_client._pool is None

    async def test_closes_and_clears_pool(self):
        fake = MagicMock()
        fake.aclose = AsyncMock()
        redis_client._pool = fake

        await redis_client.close_redis()

        fake.aclose.assert_awaited_once()
        assert redis_client._pool is None

    async def test_get_after_close_creates_new_pool(self):
        first_conn = MagicMock(name="first")
        first_conn.aclose = AsyncMock()
        second_conn = MagicMock(name="second")

        with patch(
            "nodelens.redis.client.aioredis.from_url",
            side_effect=[first_conn, second_conn],
        ) as from_url:
            r1 = await redis_client.get_redis()
            await redis_client.close_redis()
            r2 = await redis_client.get_redis()

        assert r1 is first_conn
        assert r2 is second_conn
        assert from_url.call_count == 2
