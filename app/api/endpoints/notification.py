from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.db import get_db
from app.models.notification import (
    NotificationResponse,
    NotificationPreferences,
    NotificationStatus
)
from app.services.notification import notification_service

router = APIRouter()

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[NotificationStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for the current user."""
    notifications = await notification_service.get_notifications(
        db=db,
        user_id=current_user["id"],
        skip=skip,
        limit=limit,
        status=status
    )
    
    return [n.to_response() for n in notifications]

@router.post("/notifications/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mark a notification as read."""
    success = await notification_service.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user["id"]
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}

@router.get("/notifications/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get notification preferences for the current user."""
    prefs = await notification_service._get_user_notification_preferences(
        current_user["id"]
    )
    return NotificationPreferences(**prefs)

@router.put("/notifications/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: dict = Depends(get_current_user)
):
    """Update notification preferences for the current user."""
    # TODO: Implement preference update in database
    return preferences

@router.get("/notifications/unread/count")
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread notifications."""
    notifications = await notification_service.get_notifications(
        db=db,
        user_id=current_user["id"],
        limit=1000
    )
    
    unread_count = sum(1 for n in notifications if not n.read)
    return {"unread_count": unread_count}

@router.post("/notifications/mark-all-read")
async def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Mark all notifications as read."""
    notifications = await notification_service.get_notifications(
        db=db,
        user_id=current_user["id"],
        limit=1000
    )
    
    for notification in notifications:
        if not notification.read:
            await notification_service.mark_as_read(
                db=db,
                notification_id=notification.id,
                user_id=current_user["id"]
            )
    
    return {"message": "All notifications marked as read"}
