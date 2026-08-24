"""Token issuing/verification and password hashing.

Xano's own JWTs are not verifiable here (different secret), and its password
hashes are not exportable (`user.password` is access=internal). Both facts are
settled — see the migration plan's Phase 7.
"""
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import settings

# Explicit rather than PasswordHash.recommended(): that helper changes algorithm
# depending on which extras happen to be installed, which is not a property you
# want in password hashing. Argon2id is chosen deliberately — nothing is being
# migrated in, since Xano's hashes are not exportable.
_hasher = PasswordHash((Argon2Hasher(),))


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)


def create_access_token(user_id: int, expires_in: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expiry = expires_in or timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "iat": now, "exp": now + expiry}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on anything invalid — callers turn that into a 401."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
