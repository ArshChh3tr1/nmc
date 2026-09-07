from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.database.models import AuditLog

def log_action(
    db: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[str] = None
) -> AuditLog:
    """
    Appends an immutable audit log record to the database.
    """
    log_entry = AuditLog(
        timestamp=datetime.now(),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
