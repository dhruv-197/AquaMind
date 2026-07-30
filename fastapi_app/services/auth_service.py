import os
from datetime import datetime, timedelta
import jwt
import bcrypt

# Configuration
_DEV_FALLBACK_SECRET = "development-only-change-before-deployment"
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
_ENVIRONMENT = os.getenv("AQUAMIND_ENVIRONMENT", "development").lower()

if not SECRET_KEY:
    if _ENVIRONMENT not in ("development", "test", "testing"):
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Refusing to start with the hardcoded "
            "development fallback outside a development/test environment — "
            "set JWT_SECRET_KEY to a long random secret in .env.local."
        )
    # Safe for local development only.
    SECRET_KEY = _DEV_FALLBACK_SECRET
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
            raise ValueError("Token signature has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid credentials token")
