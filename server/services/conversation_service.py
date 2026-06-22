from models.conversation import Conversation
from models.message import Message
from extensions import db
from sqlalchemy.exc import SQLAlchemyError
import re


DEFAULT_TITLE = "New Chat"


def generate_conversation_title(message):
    text = re.sub(r"\s+", " ", (message or "").strip())
    if not text:
        return DEFAULT_TITLE

    text = re.sub(r"^(hi|hello|hey)\b[\s,!.]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(please|pls)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ,.!?-")

    name_work_match = re.search(
        r"\bmy name is\s+(.+?)\s+and\s+i\s+(?:work|am working)\s+(?:at|for)\s+(.+?)(?:[.!?]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if name_work_match:
        name = name_work_match.group(1).strip(" ,.!?")
        company = name_work_match.group(2).strip(" ,.!?")
        title = f"{_clean_entity_title(name)} at {_clean_entity_title(company)}"
    else:
        text = re.sub(r"^(can|could|would)\s+you\s+", "", text, flags=re.IGNORECASE)
        words = text.split()
        title = " ".join(words[:6]).strip(" ,.!?")

    if not title:
        return DEFAULT_TITLE

    return title[0].upper() + title[1:]


def _clean_entity_title(value):
    words = value.split()[:3]
    cleaned = " ".join(words).strip(" ,.!?")
    return cleaned.title() if cleaned.islower() else cleaned


def update_default_title_from_message(conversation, message):
    if not conversation or conversation.title != DEFAULT_TITLE:
        return

    conversation.title = generate_conversation_title(message)
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"[WARNING] Title update failed: {str(e)}")


def create_conversation(data):
    user_id = data.get("user_id")

    if not user_id:
        raise ValueError("user_id is required")

    convo = Conversation(
        user_id=user_id,
        title=data.get("title") or DEFAULT_TITLE,
        persona_id=data.get("persona_id"),
        memory_type=data.get("memory_type", "buffer"),
    )
    try:
        db.session.add(convo)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    return convo


def get_all_conversations(user_id, search=None, pinned=None, archived=None):
    if not user_id:
        raise ValueError("user_id is required")

    query = Conversation.query.filter_by(user_id=user_id)

    if search:
        like = f"%{search.strip()}%"
        query = query.outerjoin(
            Message, Message.conversation_id == Conversation.id
        ).filter(
            (Conversation.title.ilike(like)) | (Message.content.ilike(like))
        )

    if pinned is not None:
        query = query.filter_by(is_pinned=bool(pinned))

    if archived is not None:
        query = query.filter_by(is_archived=bool(archived))

    return query.distinct().order_by(
        Conversation.is_pinned.desc(),
        Conversation.updated_at.desc(),
        Conversation.created_at.desc(),
    ).all()


def update_conversation(conversation, data):
    if not conversation:
        raise ValueError("conversation is required")

    allowed_fields = {
        "title",
        "persona_id",
        "memory_type",
        "is_pinned",
        "is_archived",
    }

    for key, value in (data or {}).items():
        if key not in allowed_fields:
            continue
        setattr(conversation, key, value)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    return conversation


def serialize_conversation(conversation):
    return {
        "id": conversation.id,
        "title": conversation.title,
        "persona_id": conversation.persona_id,
        "memory_type": conversation.memory_type,
        "is_pinned": conversation.is_pinned,
        "is_archived": conversation.is_archived,
        "created_at": conversation.created_at.isoformat()
        if conversation.created_at
        else None,
        "updated_at": conversation.updated_at.isoformat()
        if conversation.updated_at
        else None,
    }
