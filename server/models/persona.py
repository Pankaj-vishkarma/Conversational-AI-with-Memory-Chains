from extensions import db
import uuid


class Persona(db.Model):
    __tablename__ = "personas"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, nullable=False)
    system_prompt = db.Column(db.Text)
    memory_type = db.Column(db.String)  # buffer, summary, entity, kg
    temperature = db.Column(db.Float, default=0.7)
