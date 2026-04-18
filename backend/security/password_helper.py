import hashlib
import hmac
import secrets


PBKDF2_ITERATIONS = 100_000
HASH_NAME = "sha256"
ENCODING = "utf-8"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode(ENCODING),
        salt.encode(ENCODING),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_{HASH_NAME}${PBKDF2_ITERATIONS}${salt}${password_hash}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        algorithm, iterations, salt, expected_hash = stored_password.split("$", maxsplit=3)
    except ValueError:
        return False

    if algorithm != f"pbkdf2_{HASH_NAME}":
        return False

    candidate_hash = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode(ENCODING),
        salt.encode(ENCODING),
        int(iterations),
    ).hex()
    return hmac.compare_digest(candidate_hash, expected_hash)
