import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .config import settings
from .db.database import get_db
from .db.models import User


# Password hashing utilities
def hash_password(password: str) -> str:
    """Hash a password for storing."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a stored password against one provided by user."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# JWT utilities
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ARGUS_JWT_EXPIRES_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.ARGUS_JWT_SECRET, algorithm="HS256")
    return encoded_jwt

def decode_token(token: str):
    """Decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.ARGUS_JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# FastAPI dependencies
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get the current user from the JWT token."""
    payload = decode_token(token)
    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
):
    """Get the current active user."""
    if not current_user:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def admin_required(
    current_user: User = Depends(get_current_active_user)
):
    """Dependency to check if the current user is an admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user

async def seed_admin_user(db: AsyncSession):
    """Seed the default admin user if it doesn't exist."""
    result = await db.execute(select(User).where(User.username == settings.ARGUS_ADMIN_USERNAME))
    admin_user = result.scalars().first()
    
    if not admin_user:
        hashed_password = hash_password(settings.ARGUS_ADMIN_PASSWORD)
        admin_user = User(
            username=settings.ARGUS_ADMIN_USERNAME,
            email=settings.ARGUS_ADMIN_EMAIL,
            password_hash=hashed_password,
            role="admin",
        )
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)


# ======================================================================
# HTTP routes (auth + teams)
# ======================================================================

from fastapi import APIRouter
from pydantic import BaseModel
from .db.models import Team


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@auth_router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalars().first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
    }


@auth_router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
    }


@auth_router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.password_hash or not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"status": "ok"}


# ---- Teams (admin-managed roster) ----

teams_router = APIRouter(prefix="/api/teams", tags=["teams"])


class TeamCreate(BaseModel):
    name: str


class MemberAdd(BaseModel):
    email: str


@teams_router.post("")
async def create_team(
    body: TeamCreate,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    team = Team(name=body.name)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return {"id": team.id, "name": team.name}


@teams_router.get("")
async def list_teams(
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Team))
    teams = result.scalars().all()
    return [{"id": t.id, "name": t.name} for t in teams]


@teams_router.get("/{team_id}")
async def get_team(
    team_id: int,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    members = [{"id": u.id, "username": u.username, "email": u.email} for u in team.users]
    return {"id": team.id, "name": team.name, "members": members}


@teams_router.post("/{team_id}/members")
async def add_member(
    team_id: int,
    body: MemberAdd,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()
    if not user:
        username = body.email.split("@")[0] or "user"
        user = User(username=username, email=body.email, password_hash=None, role="user")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    user.team_id = team.id
    await db.commit()
    return {"status": "ok", "user": {"id": user.id, "username": user.username, "email": user.email}}


@teams_router.delete("/{team_id}/members/{user_id}")
async def kick_member(
    team_id: int,
    user_id: int,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.team_id = None
    await db.commit()
    return {"status": "ok"}


@teams_router.delete("/{team_id}")
async def delete_team(
    team_id: int,
    _admin: User = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    team = await db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await db.delete(team)
    await db.commit()
    return {"status": "ok"}