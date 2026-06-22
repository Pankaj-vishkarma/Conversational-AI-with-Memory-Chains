from extensions import db
import uuid
from datetime import datetime


class Entity(db.Model):
    __tablename__ = "entities"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, index=True)
    description = db.Column(db.Text)
    conversation_id = db.Column(db.String, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
