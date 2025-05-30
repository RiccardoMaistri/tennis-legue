from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services import notification_service, auth_service
from app.models import user as user_model
from app.schemas import notification_schemas
from app.api.dependencies import get_db

router = APIRouter()

@router.get("/", response_model=List[notification_schemas.NotificationRead])
async def get_user_notifications_endpoint(
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    notifications = notification_service.get_user_notifications(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )
    return notifications

@router.post("/", response_model=notification_schemas.NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_notification_endpoint(
    notification_in: notification_schemas.NotificationCreate,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user), # Add authorization logic if needed
):
    # Basic check: current_user can create notifications for other users specified in notification_in.user_id
    # More complex logic (e.g. admin only, or system-triggered) would go here.
    # For now, any authenticated user can create a notification for any user_id specified in the payload.
    # This is a simplification as per instructions.
    
    # Optional: If only admins should create notifications, or if users can only create for themselves (which is less common for this type of POST)
    # if not current_user.is_admin and current_user.id != notification_in.user_id:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create this notification")

    created_notification = notification_service.create_notification(db=db, notification_in=notification_in)
    return created_notification

@router.patch("/{notification_id}/read", response_model=notification_schemas.NotificationRead)
async def mark_notification_as_read_endpoint(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    updated_notification = notification_service.mark_notification_as_read(
        db=db, notification_id=notification_id, current_user_id=current_user.id
    )
    if not updated_notification: # Service raises HTTPException for not found or forbidden
        # This path should ideally not be reached if service handles exceptions
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not mark notification as read")
    return updated_notification

@router.post("/read-all", response_model=List[notification_schemas.NotificationRead])
async def mark_all_user_notifications_as_read_endpoint(
    db: Session = Depends(get_db),
    current_user: user_model.User = Depends(auth_service.get_current_user),
):
    updated_notifications = notification_service.mark_all_user_notifications_as_read(
        db=db, current_user_id=current_user.id
    )
    # No explicit error if list is empty, service returns empty list.
    return updated_notifications
