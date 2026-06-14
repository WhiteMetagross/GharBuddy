"""
AuthService - lightweight JWT authentication for GharBuddy IoT control API.
Uses python-jose for JWT and passlib for password hashing.
Falls back to a pure-stdlib HS256 implementation when dependencies are not installed.
"""
import os
import json
import hmac
import hashlib
import base64
import time as _time
import datetime
from Backend.Config.AppConfig import AppConfig

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_USERNAME = os.getenv("GHARBUDDY_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("GHARBUDDY_PASSWORD", "gharbuddy2024")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "gharbuddy-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
TOKEN_EXPIRY_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60

# ---------------------------------------------------------------------------
# Demo multi-user store (Issue #6)
# ---------------------------------------------------------------------------
DEMO_USERS = {
    "admin": {"password": "gharbuddy123", "role": "parent"},
    "child": {"password": "child123", "role": "child"},
}
# Merge env-configured admin (may differ from the demo "admin" entry)
if DEFAULT_USERNAME not in DEMO_USERS:
    DEMO_USERS[DEFAULT_USERNAME] = {"password": DEFAULT_PASSWORD, "role": "parent"}

# ---------------------------------------------------------------------------
# Registered users — populated via POST /api/auth/register.
# Keeps PBKDF2 password hash + salt + role + created_at timestamp.
# Backed by Postgres Users table when live; in-memory dict in mock mode.
# ---------------------------------------------------------------------------
REGISTERED_USERS: dict[str, dict] = {}

# Allowed roles for self-registration. "parent" maps to admin-level access.
ALLOWED_ROLES = ("parent", "child", "family")

# PBKDF2 parameters — stdlib-only, no new deps.
_PBKDF2_ITERATIONS = 120_000
_PBKDF2_SALT_BYTES = 16
_PBKDF2_HASH_NAME = "sha256"

# ---------------------------------------------------------------------------
# Try to import JWT dependencies; fall back to pure-stdlib HS256 if unavailable
# ---------------------------------------------------------------------------
try:
    from jose import JWTError, jwt as _jose_jwt
    from passlib.context import CryptContext
    _JWT_AVAILABLE = True
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    _JWT_AVAILABLE = False
    _pwd_context = None

# Mock token store for demo when JWT libs not available
_MOCK_VALID_TOKENS: set = set()


# ---------------------------------------------------------------------------
# Pure-stdlib HS256 helpers (used when python-jose is not installed)
# ---------------------------------------------------------------------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (padding % 4))


def _stdlib_generate_token(username: str, role: str = "parent") -> str:
    """Pure-stdlib HS256 JWT generation."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sub": username,
        "role": role,
        "iat": int(_time.time()),
        "exp": int(_time.time()) + TOKEN_EXPIRY_SECONDS,
    }).encode())
    sig = _b64url(
        hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{sig}"


def _stdlib_verify_token(token: str) -> dict | None:
    """Pure-stdlib HS256 JWT verification. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload_b64, signature = parts
        expected_sig = _b64url(
            hmac.new(SECRET_KEY.encode(), f"{header}.{payload_b64}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_sig, signature):
            return None
        data = json.loads(_b64url_decode(payload_b64))
        if data.get("exp", 0) < _time.time():
            return None
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API - kept backward-compatible with existing MainFastApi.py callers
# ---------------------------------------------------------------------------

def verifyPassword(plainPassword: str, hashedPassword: str) -> bool:
    if _JWT_AVAILABLE and _pwd_context:
        try:
            return _pwd_context.verify(plainPassword, hashedPassword)
        except Exception:
            pass
    return plainPassword == hashedPassword


def hashPassword(password: str) -> str:
    if _JWT_AVAILABLE and _pwd_context:
        return _pwd_context.hash(password)
    return password


def authenticate(username: str, password: str) -> bool:
    """Validate credentials. Returns True if valid (legacy behaviour for MainFastApi login)."""
    user = DEMO_USERS.get(username)
    if user:
        return user["password"] == password
    # Fall back to env-configured single-user check
    if username != DEFAULT_USERNAME:
        return False
    return verifyPassword(password, DEFAULT_PASSWORD)


def createAccessToken(username: str) -> str:
    """Create a JWT token for username (legacy caller: MainFastApi /api/auth/login)."""
    # Registered users (real signup) take precedence over the seeded demo store.
    reg = REGISTERED_USERS.get(username)
    if reg:
        role = reg.get("role", "family")
    else:
        role = DEMO_USERS.get(username, {}).get("role", "parent")
    if _JWT_AVAILABLE:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": username, "role": role, "exp": expire}
        return _jose_jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return _stdlib_generate_token(username, role)


def verifyToken(token: str) -> str | None:
    """
    Verify JWT token and return username string, or None if invalid/expired.
    In mock mode bypasses validation entirely.
    """
    if AppConfig.mockMode:
        # In mock mode, bypass auth entirely - return "admin" for any non-empty token
        return "admin" if token else None

    if _JWT_AVAILABLE:
        try:
            payload = _jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub")
        except Exception:
            return None

    # Pure-stdlib path
    data = _stdlib_verify_token(token)
    if data:
        return data.get("sub")
    return None


def verifyTokenFull(token: str) -> dict | None:
    """
    Verify JWT token and return full payload dict (sub, role, exp ...), or None.
    Used by /api/auth/verify endpoint (Issue #6).
    """
    if AppConfig.mockMode:
        return {"sub": "admin", "role": "parent"} if token else None

    if _JWT_AVAILABLE:
        try:
            payload = _jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except Exception:
            return None

    return _stdlib_verify_token(token)


def loginUser(username: str, password: str) -> dict | None:
    """
    Issue #6 - Full login returning token dict, or None on bad credentials.
    Returns {"token", "username", "role", "expiresIn"}.
    Looks up registered users (PBKDF2) first, then DEMO_USERS (plaintext).
    """
    # Registered users (real PBKDF2 hash)
    reg = REGISTERED_USERS.get(username)
    if reg and _pbkdf2_verify(password, reg["password_hash"], reg["salt"]):
        token = createAccessToken(username)
        return {
            "token": token,
            "username": username,
            "role": reg.get("role", "family"),
            "expiresIn": TOKEN_EXPIRY_SECONDS,
        }

    # Legacy demo users (kept for backward compat with existing tests/docs)
    user = DEMO_USERS.get(username)
    if not user or user["password"] != password:
        return None
    token = createAccessToken(username)
    return {
        "token": token,
        "username": username,
        "role": user["role"],
        "expiresIn": TOKEN_EXPIRY_SECONDS,
    }


# ---------------------------------------------------------------------------
# PBKDF2 password hashing (stdlib only — no new dependencies)
# ---------------------------------------------------------------------------

def _pbkdf2_hash(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """
    Hash *password* with PBKDF2-HMAC-SHA256 and return (hash_hex, salt_hex).
    Generates a fresh random salt when none is provided.
    """
    if salt is None:
        salt = os.urandom(_PBKDF2_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH_NAME, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return derived.hex(), salt.hex()


def _pbkdf2_verify(password: str, expected_hash_hex: str, salt_hex: str) -> bool:
    """Constant-time PBKDF2 verification."""
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate, _ = _pbkdf2_hash(password, salt)
    return hmac.compare_digest(candidate, expected_hash_hex)


# ---------------------------------------------------------------------------
# Registration (Issue: proper auth flow)
# ---------------------------------------------------------------------------

class RegistrationError(Exception):
    """Raised when registration fails validation (duplicate username, weak password, ...)."""


def _validate_registration(username: str, password: str, role: str) -> str:
    """Return cleaned role on success or raise RegistrationError."""
    if not username or not username.strip():
        raise RegistrationError("Username is required")
    uname = username.strip()
    if len(uname) < 3 or len(uname) > 32:
        raise RegistrationError("Username must be 3-32 characters")
    if not all(c.isalnum() or c in ("_", "-", ".") for c in uname):
        raise RegistrationError("Username may contain letters, digits, _ - . only")
    if not password or len(password) < 6:
        raise RegistrationError("Password must be at least 6 characters")
    if len(password) > 128:
        raise RegistrationError("Password is too long")

    cleaned_role = (role or "family").strip().lower()
    if cleaned_role not in ALLOWED_ROLES:
        raise RegistrationError(
            f"Role must be one of: {', '.join(ALLOWED_ROLES)}"
        )

    if uname in DEMO_USERS or uname in REGISTERED_USERS:
        raise RegistrationError("Username already taken")

    return cleaned_role


def registerUser(
    username: str,
    password: str,
    role: str = "family",
    pgService=None,
) -> dict:
    """
    Register a new user. Persists to Postgres `Users` table when *pgService* is
    provided and live; otherwise stores in REGISTERED_USERS in-memory.

    Returns {"token", "username", "role", "expiresIn"} on success.
    Raises RegistrationError on validation failure.
    """
    cleaned_role = _validate_registration(username, password, role)
    uname = username.strip()
    pwd_hash, salt_hex = _pbkdf2_hash(password)
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    record = {
        "password_hash": pwd_hash,
        "salt": salt_hex,
        "role": cleaned_role,
        "created_at": created_at,
    }

    # In-memory store (always populated so loginUser sees it immediately).
    REGISTERED_USERS[uname] = record

    # Best-effort persistence to Postgres if a service is provided.
    if pgService is not None:
        try:
            pgService.insertUser(uname, pwd_hash, salt_hex, cleaned_role, created_at)
        except Exception as e:  # noqa: BLE001
            # Non-fatal — registration still succeeds in-memory.
            print(f"[AuthService] Persisting user '{uname}' to DB failed: {e}")

    token = createAccessToken(uname)
    return {
        "token": token,
        "username": uname,
        "role": cleaned_role,
        "expiresIn": TOKEN_EXPIRY_SECONDS,
    }


def loadRegisteredUsers(pgService) -> int:
    """
    Hydrate REGISTERED_USERS from Postgres on startup. Returns count loaded.
    Safe to call when pgService is None or in mock mode (returns 0).
    """
    if pgService is None:
        return 0
    try:
        rows = pgService.getUsers()
    except Exception as e:  # noqa: BLE001
        print(f"[AuthService] Could not load Users table: {e}")
        return 0
    count = 0
    for row in rows:
        username = row.get("username")
        if not username or username in REGISTERED_USERS:
            continue
        REGISTERED_USERS[username] = {
            "password_hash": row.get("password_hash", ""),
            "salt": row.get("salt", ""),
            "role": row.get("role", "family"),
            "created_at": row.get("created_at", ""),
        }
        count += 1
    return count
