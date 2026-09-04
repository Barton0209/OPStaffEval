import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import DomainEvent


def emit_event(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    entity_type: str,
    entity_id: int | None,
    action: str,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    event = DomainEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(event)
    return event
