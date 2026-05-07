"""
Authentication: login endpoint + JWT verification dependency.

JWT payload fields:
    user_id       (int)    PK of users table
    tenant_id     (int)    PK of tenants table
    tenant_type   (str)    internal / processor / material
    username      (str)
    role          (str)    admin / manager / operator / ...
    exp           (int)    standard JWT exp (24h)
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from mvp import db

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    tenant_id: int
    tenant_type: str
    tenant_name: str
    username: str
    display_name: str
    role: str | None


class CurrentUser(BaseModel):
    user_id: int
    tenant_id: int
    tenant_type: str
    tenant_name: str | None = None
    username: str
    role: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(payload: dict[str, Any]) -> str:
    to_encode = dict(payload)
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = int(expire.timestamp())
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid token: {e}")


# ---------------------------------------------------------------------------
# Dependency: current_user
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """Extract user from Authorization: Bearer <token> OR cookie 'access_token'."""
    token: str | None = None
    if cred and cred.scheme.lower() == "bearer":
        token = cred.credentials
    else:
        # Fallback: allow token in cookie for simple HTML pages
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing access token")

    payload = decode_token(token)
    return CurrentUser(
        user_id=payload["user_id"],
        tenant_id=payload["tenant_id"],
        tenant_type=payload["tenant_type"],
        tenant_name=payload.get("tenant_name"),
        username=payload["username"],
        role=payload.get("role"),
    )


def require_tenant_type(*allowed: str):
    """Dependency factory: only allow certain tenant_types."""
    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.tenant_type not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for tenant_type={user.tenant_type}; "
                       f"allowed={allowed}",
            )
        return user
    return _dep


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    row = db.fetch_one(
        """
        SELECT u.id AS user_id, u.username, u.password_hash, u.display_name,
               u.role, u.is_active,
               u.tenant_id, t.tenant_type, t.name AS tenant_name
        FROM users u
        JOIN tenants t ON u.tenant_id = t.id
        WHERE u.username = %s
        """,
        (payload.username,),
    )
    if row is None or not row["is_active"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "user_id": row["user_id"],
        "tenant_id": row["tenant_id"],
        "tenant_type": row["tenant_type"],
        "tenant_name": row["tenant_name"],
        "username": row["username"],
        "role": row["role"],
    })

    return LoginResponse(
        access_token=token,
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        tenant_type=row["tenant_type"],
        tenant_name=row["tenant_name"],
        username=row["username"],
        display_name=row["display_name"],
        role=row["role"],
    )


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Return info about the current logged-in user (for frontend sanity check)."""
    return user
