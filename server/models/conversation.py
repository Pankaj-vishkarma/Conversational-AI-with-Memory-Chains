from extensions import db
import uuid
from datetime import datetime


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))

   
    user_id = db.Column(db.String, db.ForeignKey("users.id"), nullable=False)

    # Basic Info
    title = db.Column(db.String, default="New Chat")

    # Persona
    persona_id = db.Column(db.String, db.ForeignKey("personas.id"), nullable=True)

    # Memory Type (buffer, summary, entity, kg, hybrid)
    memory_type = db.Column(db.String, default="buffer")

    # Conversation State
    is_pinned = db.Column(db.Boolean, default=False)
    is_archived = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
