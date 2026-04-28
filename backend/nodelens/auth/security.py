"""Password hashing primitives. Pure functions, no DB or app state.

bcrypt has a hard 72-byte input limit (it's a property of the algorithm, not
the library). Schemas cap password fields at 72 chars so a too-long password
fails validation with a clean 422 instead of escaping to here.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False
