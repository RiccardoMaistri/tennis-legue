from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import notification as notification_model
from app.models import user as user_model # For validation if needed, though not strictly in this step
from app.schemas import notification_schemas

def create_notification(db: Session, notification_in: notification_schemas.NotificationCreate) -> notification_model.Notification:
    # Optional: Validate if notification_in.user_id exists
    # user = db.query(user_model.User).filter(user_model.User.id == notification_in.user_id).first()
    # if not user:
    #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {notification_in.user_id} not found")

    db_notification = notification_model.Notification(
        user_id=notification_in.user_id,
        message=notification_in.message,
        type=notification_in.type
        # read_status and created_at have defaults in the model
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification

def get_user_notifications(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[notification_model.Notification]:
    return db.query(notification_model.Notification)\
        .filter(notification_model.Notification.user_id == user_id)\
        .order_by(notification_model.Notification.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

def mark_notification_as_read(db: Session, notification_id: int, current_user_id: int) -> Optional[notification_model.Notification]:
    db_notification = db.query(notification_model.Notification).filter(notification_model.Notification.id == notification_id).first()

    if not db_notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    
    if db_notification.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to mark this notification as read")

    if not db_notification.read_status: # Avoid unnecessary db write if already read
        db_notification.read_status = True
        db.commit()
        db.refresh(db_notification)
    
    return db_notification

def mark_all_user_notifications_as_read(db: Session, current_user_id: int) -> List[notification_model.Notification]:
    unread_notifications = db.query(notification_model.Notification)\
        .filter(notification_model.Notification.user_id == current_user_id, notification_model.Notification.read_status == False)\
        .all()
    
    updated_notifications = []
    if not unread_notifications:
        return [] # Return empty list if nothing to update

    for notification in unread_notifications:
        notification.read_status = True
        updated_notifications.append(notification)
        
    db.commit()
    # Refresh objects if their state after commit is needed by the caller,
    # but since we only changed read_status and did it in-place, it might not be strictly necessary
    # for this specific operation unless further processing of these objects is expected by the caller.
    # For consistency, let's refresh.
    for notification in updated_notifications:
        db.refresh(notification)
        
    return updated_notifications
