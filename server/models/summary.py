from extensions import db
import uuid
from datetime import datetime


class Summary(db.Model):
    __tablename__ = "summaries"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = db.Column(db.String, index=True)
    content = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
