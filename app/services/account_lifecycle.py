"""Account export and hard-delete for the signed-in user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import User
from app.services.conversation_store import list_conversations_for_user, list_messages_for_conversation
from app.services.object_storage import ObjectStorage
from app.services.vector_store import VectorStore


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    conversations_payload: list[dict[str, Any]] = []
    for conversation, message_count in list_conversations_for_user(db, user.id):
        messages = list_messages_for_conversation(db, user.id, conversation.id) or []
        conversations_payload.append(
            {
                "id": str(conversation.id),
                "title": conversation.title,
                "mode": conversation.mode,
                "pinned": conversation.pinned_at is not None,
                "message_count": message_count,
                "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                "messages": [
                    {
                        "id": str(message.id),
                        "role": message.role.value if hasattr(message.role, "value") else str(message.role),
                        "content": message.content,
                        "created_at": message.created_at.isoformat() if message.created_at else None,
                        "metadata": message.metadata_json or {},
                    }
                    for message in messages
                ],
            }
        )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": getattr(user, "role", None) or "user",
        },
        "conversations": conversations_payload,
    }


def delete_user_account(
    *,
    db: Session,
    user: User,
    vector_store: VectorStore,
    object_storage: ObjectStorage,
) -> dict[str, Any]:
    user_id = str(user.id)
    vector_deleted = False
    try:
        vector_store.delete_for_user(user_id)
        vector_deleted = True
    except Exception:
        # Still delete the Postgres row so the account cannot sign in again.
        pass

    uploads_removed = 0
    delete_uploads = getattr(object_storage, "delete_user_prefix", None)
    if callable(delete_uploads):
        try:
            uploads_removed = int(delete_uploads(user_id) or 0)
        except Exception:
            uploads_removed = 0

    db.delete(user)
    db.commit()
    return {
        "deleted_user_id": user_id,
        "vector_store_cleared": vector_deleted,
        "uploads_removed": uploads_removed,
    }
