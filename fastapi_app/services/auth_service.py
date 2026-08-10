import os
from datetime import datetime, timedelta
import jwt
import bcrypt

# Configuration
_DEV_FALLBACK_SECRET = "development-only-change-before-deployment"
_PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        _DEV_FALLBACK_SECRET,
        "replace-with-a-long-random-secret",
        "changeme",
        "secret",
        "your-secret-here",
    }
)
_ENVIRONMENT = os.getenv("AQUAMIND_ENVIRONMENT", "development").lower()


def _resolve_jwt_secret() -> str:
    raw = (os.getenv("JWT_SECRET_KEY") or "").strip()
    if _ENVIRONMENT in ("staging", "production"):
        if raw in _PLACEHOLDER_SECRETS or len(raw) < 32:
            raise RuntimeError(
                "JWT_SECRET_KEY must be a long random secret (≥32 chars) when "
                f"AQUAMIND_ENVIRONMENT={_ENVIRONMENT!r}. Do not use the development "
                "fallback or .env.example placeholders."
            )
        return raw
    if raw in _PLACEHOLDER_SECRETS:
        # Safe for local development / pytest only.
        return _DEV_FALLBACK_SECRET
    return raw


SECRET_KEY = _resolve_jwt_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hashes a password using bcrypt directly (prevents Python 3.14 passlib wrap bugs).
        """
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a plain password matches its bcrypt hash.
        """
        try:
            pwd_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(pwd_bytes, hashed_bytes)
        except Exception:
            return False

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
        """
        Creates a JWT access token containing arbitrary payload data.
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> dict:
        """
        Decodes a JWT access token. Returns payload dict if valid, raises jwt exception otherwise.
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Invalid or expired credentials")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid or expired credentials")
