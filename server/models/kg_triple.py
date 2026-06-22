from extensions import db
import uuid
from datetime import datetime


class KGTriple(db.Model):
    __tablename__ = "kg_triples"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subject = db.Column(db.String, index=True)
    predicate = db.Column(db.String)
    object = db.Column(db.String)
    conversation_id = db.Column(db.String, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
