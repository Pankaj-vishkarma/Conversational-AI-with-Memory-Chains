from models.persona import Persona
from extensions import db


DEFAULT_PERSONAS = [
    {
        "name": "Assistant",
        "system_prompt": "You are a helpful, clear, and concise AI assistant.",
        "memory_type": "buffer",
        "temperature": 0.7,
    },
    {
        "name": "Summarizer",
        "system_prompt": "You summarize conversations clearly and preserve important context.",
        "memory_type": "summary",
        "temperature": 0.5,
    },
    {
        "name": "Research Helper",
        "system_prompt": "You help analyze information, extract facts, and organize insights.",
        "memory_type": "entity",
        "temperature": 0.6,
    },
]


def get_persona(persona_id):
    return Persona.query.filter_by(id=persona_id).first()


def seed_default_personas():
    if Persona.query.first():
        return

    try:
        for data in DEFAULT_PERSONAS:
            db.session.add(Persona(**data))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] seed_default_personas: {str(e)}")


def get_all_personas():
    seed_default_personas()
    return Persona.query.all()


def create_persona(data):
    persona = Persona(
        name=data.get("name"),
        system_prompt=data.get("system_prompt"),
        memory_type=data.get("memory_type"),
        temperature=data.get("temperature", 0.7),
    )

    db.session.add(persona)
    db.session.commit()

    return persona
