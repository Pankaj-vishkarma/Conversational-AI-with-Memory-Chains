from extensions import db
from datetime import datetime
import uuid


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String, db.ForeignKey("conversations.id"))
    role = db.Column(db.String)  # user / assistant
    content = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
