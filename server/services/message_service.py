from models.message import Message
from extensions import db


def save_message(conversation_id: str, role: str, content: str):
    """
    Save a message to the database
    """

    try:
        if not conversation_id or not role or not content:
            raise ValueError("Missing required fields")

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        db.session.add(message)
        db.session.commit()

        return message

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] save_message: {str(e)}")
        return None


def get_conversation_messages(conversation_id: str):
    """
    Get all messages for a conversation (ordered)
    """

    try:
        if not conversation_id:
            return []

        messages = (
            Message.query.filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        return messages

    except Exception as e:
        print(f"[ERROR] get_conversation_messages: {str(e)}")
        return []
