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
    """
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
