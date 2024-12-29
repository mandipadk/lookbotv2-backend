from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies.auth import get_current_admin_user
from app.core.security import get_password_hash
from app.db.supabase import get_supabase_client
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import logging
from uuid import UUID

logger = logging.getLogger(__name__)
router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr
    is_active: bool = True
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    is_active: bool
    is_admin: bool

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_in: UserCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Create new user (admin only).
    """
    try:
        supabase = get_supabase_client()
        
        # Check if username already exists
        result = await supabase.table("users").select("*").eq("username", user_in.username).execute()
        if result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Create new user
        user_data = user_in.dict()
        user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
        
        result = await supabase.table("users").insert(user_data).execute()
        return result.data[0]
        
    except Exception as e:
        logger.error(f"User creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create user"
        )

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all users (admin only).
    """
    try:
        supabase = get_supabase_client()
        result = await supabase.table("users").select("*").execute()
        return result.data
        
    except Exception as e:
        logger.error(f"User listing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not list users"
        )

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Update user (admin only).
    """
    try:
        supabase = get_supabase_client()
        
        # Check if user exists
        result = await supabase.table("users").select("*").eq("id", str(user_id)).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update user
        update_data = user_in.dict(exclude_unset=True)
        result = await supabase.table("users").update(update_data).eq("id", str(user_id)).execute()
        return result.data[0]
        
    except Exception as e:
        logger.error(f"User update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update user"
        )

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Delete user (admin only).
    """
    try:
        supabase = get_supabase_client()
        
        # Check if user exists
        result = await supabase.table("users").select("*").eq("id", str(user_id)).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Delete user
        await supabase.table("users").delete().eq("id", str(user_id)).execute()
        return {"message": "User deleted successfully"}
        
    except Exception as e:
        logger.error(f"User deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete user"
        )

@router.post("/generate-key")
async def generate_new_key(
    current_admin: dict = Depends(get_current_admin_user)
) -> dict:
    """Generate a new 32-bit key."""
    from app.core.security import generate_random_key
    return {"key": generate_random_key()}
