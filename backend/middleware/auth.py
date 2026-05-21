"""PRISM — JWT Authentication"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from backend.config.settings import get_settings

settings = get_settings()
import bcrypt
oauth2   = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def hash_password(password: str) -> str:
    # bcrypt requires bytes
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def create_token(data: dict, expire_minutes: int = None) -> str:
    # Ensure all data values are serializable (convert Enums/UUIDs to strings)
    to_encode = {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v for k, v in data.items()}
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes or settings.jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def get_current_user(token: str = Depends(oauth2)) -> dict:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"user_id": user_id, "email": payload.get("email"), "role": payload.get("role","patient"), "subscription": payload.get("subscription","free")}

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
