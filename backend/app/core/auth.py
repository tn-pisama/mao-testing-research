from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.config import get_settings

settings = get_settings()
security = HTTPBearer()


class TokenData(BaseModel):
    tenant_id: str
    exp: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify API key using bcrypt."""
    return bcrypt.checkpw(plain_key.encode("utf-8"), hashed_key.encode("utf-8"))


def hash_api_key(key: str) -> str:
    """Hash API key using bcrypt."""
    return bcrypt.hashpw(key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(tenant_id: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=settings.jwt_expiration_hours))
    to_encode = {"tenant_id": tenant_id, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return TokenData(tenant_id=payload["tenant_id"], exp=payload["exp"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_tenant(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token_data = decode_access_token(credentials.credentials)
    return token_data.tenant_id
