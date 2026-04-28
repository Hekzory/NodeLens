"""Unit tests for auth password primitives."""

from __future__ import annotations

import pytest

from nodelens.auth.security import hash_password, verify_password


class TestHashPassword:
    def test_produces_different_hashes_each_call(self):
        a = hash_password("changeme123")
        b = hash_password("changeme123")
        assert a != b  # bcrypt salt randomness

    def test_hash_format_is_bcrypt(self):
        h = hash_password("changeme123")
        assert h.startswith(("$2a$", "$2b$", "$2y$"))


class TestVerifyPassword:
    def test_correct_password_round_trips(self):
        h = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", h) is True

    def test_wrong_password_rejected(self):
        h = hash_password("correct horse battery staple")
        assert verify_password("wrong password", h) is False

    @pytest.mark.parametrize("garbage", ["", "not-a-hash", "$2b$broken"])
    def test_malformed_hash_returns_false(self, garbage):
        assert verify_password("anything", garbage) is False
