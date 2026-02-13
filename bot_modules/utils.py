from datetime import datetime, timezone, timedelta
import hashlib
import secrets as secrets_lib
from os import getenv


def now() -> float:
    utc_plus_3 = timezone(timedelta(hours=3))
    return datetime.now(utc_plus_3).timestamp()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()


def is_admin_password_valid(password: str) -> bool:
    password_hash = getenv("ADMIN_PASSWORD_HASH")
    password_salt = getenv("ADMIN_PASSWORD_SALT")
    if password_hash and password_salt:
        return secrets_lib.compare_digest(
            _hash_password(password, password_salt), password_hash
        )
    admin_password = getenv("ADMIN_PASSWORD")
    if not admin_password:
        return False
    return secrets_lib.compare_digest(password, admin_password)
