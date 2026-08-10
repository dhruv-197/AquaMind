import hashlib
import logging
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from fastapi_app.core.rate_limit import limiter
from fastapi_app.database.connection import get_db
from fastapi_app.database.models import PasswordResetToken, User
from fastapi_app.services.auth_service import AuthService
from fastapi_app.core.security import get_current_user, require_role
from fastapi_app.schemas import (
    UserSignupRequest, UserLoginRequest, ForgotPasswordRequest, RequestPasswordResetRequest,
    PromoteUserRequest, AuthResponse, AuthResponseData,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Role Management"])
logger = logging.getLogger("aquamind.auth")

# Roles a public /auth/signup call may self-assign. "admin" is deliberately
# excluded — elevation happens only through /auth/promote by an existing admin.
PUBLIC_SIGNUP_ROLES = {"government_officer", "industry", "user"}
ALL_ROLES = PUBLIC_SIGNUP_ROLES | {"admin"}
RESET_TOKEN_TTL_MINUTES = 30


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account"
)
@limiter.limit("10/minute")
async def signup(request: Request, payload: UserSignupRequest, db: Session = Depends(get_db)):
    # 1. Check if user already exists
    existing_user = db.query(User).filter((User.email == payload.email) | (User.username == payload.username)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email is already registered"
        )
    
    # 2. Validate role — public signup may only self-assign non-privileged
    # roles. "admin" must be granted afterwards via POST /auth/promote by an
    # existing admin; otherwise any anonymous caller could request
    # role="admin" and receive a working admin token immediately.
    role = payload.role.lower()
    if role not in PUBLIC_SIGNUP_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid role for self-registration. Allowed roles are: "
                f"{', '.join(sorted(PUBLIC_SIGNUP_ROLES))}. Admin access is granted "
                f"by an existing administrator after signup."
            )
        )

    # 3. Create user
    hashed_pwd = AuthService.hash_password(payload.password)
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hashed_pwd,
        role=role
    )
    
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("[Auth] signup database write failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account registration is temporarily unavailable. Please try again.",
        )
    
    # 4. Generate token
    token = AuthService.create_access_token({"sub": user.email, "role": user.role})
    
    return AuthResponse(
        message="User account registered successfully.",
        data=AuthResponseData(
            access_token=token,
            role=user.role,
            username=user.username,
            email=user.email
        )
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate credentials and obtain access token"
)
@limiter.limit("10/minute")
async def login(request: Request, payload: UserLoginRequest, db: Session = Depends(get_db)):
    # 1. Fetch user
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password credentials"
        )
        
    # 2. Check password
    if not AuthService.verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password credentials"
        )
        
    # 3. Generate token
    token = AuthService.create_access_token({"sub": user.email, "role": user.role})
    
    return AuthResponse(
        message="Authentication completed successfully.",
        data=AuthResponseData(
            access_token=token,
            role=user.role,
            username=user.username,
            email=user.email
        )
    )


@router.post(
    "/request-password-reset",
    status_code=status.HTTP_200_OK,
    summary="Issue a one-time, 30-minute password-reset token",
    description=(
        "PILOT LIMITATION: no outbound email/SMS provider is wired up, so the "
        "token cannot be delivered to the user's inbox. It is logged server-side "
        "(uvicorn console) for local/demo use — production deployments must plug "
        "in a real mail provider here before going live. The response never "
        "reveals whether the email exists, to avoid account enumeration."
    ),
)
@limiter.limit("5/minute")
async def request_password_reset(request: Request, payload: RequestPasswordResetRequest, db: Session = Depends(get_db)):
    generic_response = {
        "success": True,
        "message": "If that email is registered, a reset token has been issued.",
        "timestamp": datetime.utcnow().isoformat(),
    }
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return generic_response

    raw_token = secrets.token_urlsafe(24)
    reset_row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.add(reset_row)
    db.commit()

    # PILOT: stand-in for a real email/SMS delivery channel.
    # Never log plaintext reset tokens outside development/demo — production
    # must deliver them through a mail provider instead.
    from fastapi_app.core.config import get_settings

    settings = get_settings()
    allow_token_log = settings.environment in {"development", "test", "demo"} or settings.demo_mode
    if allow_token_log:
        logger.warning(
            "[PasswordReset] token for %s (expires in %sm): %s",
            user.email,
            RESET_TOKEN_TTL_MINUTES,
            raw_token,
        )
    else:
        logger.info(
            "[PasswordReset] reset token issued for user_id=%s (expires in %sm); "
            "plaintext token not logged in this environment",
            user.id,
            RESET_TOKEN_TTL_MINUTES,
        )
    return generic_response


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Complete a password reset using a token from /auth/request-password-reset"
)
@limiter.limit("10/minute")
async def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # Same client-facing error whether the email is unknown or the token is
    # wrong — avoids account enumeration via this endpoint.
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired password reset token. Request a new one.",
    )
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise invalid_token

    token_hash = _hash_token(payload.reset_token)
    reset_row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if not reset_row or reset_row.expires_at < datetime.utcnow():
        raise invalid_token

    try:
        user.password_hash = AuthService.hash_password(payload.new_password)
        user.updated_at = datetime.utcnow()
        reset_row.used_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[Auth] password reset database write failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset is temporarily unavailable. Please try again.",
        )

    return {
        "success": True,
        "message": "Password reset completed successfully. You can now login with your new password.",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post(
    "/promote",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="[Admin only] Change another user's role",
    description="The only way to grant the admin role — public signup cannot self-assign it.",
)
async def promote_user(
    payload: PromoteUserRequest,
    db: Session = Depends(get_db),
    _admin: User = require_role(["admin"]),
):
    role = payload.role.lower()
    if role not in ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed roles are: {', '.join(sorted(ALL_ROLES))}"
        )
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = role
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = AuthService.create_access_token({"sub": user.email, "role": user.role})
    return AuthResponse(
        message=f"User role updated to '{role}'.",
        data=AuthResponseData(
            access_token=token,
            role=user.role,
            username=user.username,
            email=user.email,
        ),
    )
