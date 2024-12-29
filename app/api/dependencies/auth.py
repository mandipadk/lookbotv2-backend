from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.security import verify_token
from app.db.supabase import get_supabase_client
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify JWT token
        user_id = verify_token(token)
        if user_id is None:
            raise credentials_exception
        
        # Get user from database
        supabase = get_supabase_client()
        result = await supabase.table("users").select("*").eq("id", user_id).execute()
        
        if not result.data:
            raise credentials_exception
        
        user = result.data[0]
        if not user.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
            
        return user
        
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise credentials_exception

async def get_current_active_user(
    current_user = Depends(get_current_user)
):
    """Dependency to get current active user."""
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

def check_admin_access(user: dict) -> bool:
    """Check if user has admin access."""
    # TODO: Implement proper role-based access control
    return user.get("is_admin", False)

async def get_current_admin_user(
    current_user = Depends(get_current_user)
):
    """Dependency to get current admin user."""
    if not check_admin_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
