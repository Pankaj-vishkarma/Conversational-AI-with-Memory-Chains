from services.llm_service import generate_response
from models.entity import Entity
from extensions import db

INVALID_VALUES = {
    "",
    "user",
    "your name",
    "unknown",
    "i don't know",
    "i dont know",
}


def _clean(value):
    return (value or "").strip()


def _is_invalid(value):
    return _clean(value).lower() in INVALID_VALUES


def extract_entities_from_text(text):
    """
    Use LLM to extract entities from user message
    """

    prompt = [
        {
            "role": "system",
            "content": (
                "Extract important entities from the text. "
                "Return ONLY valid JSON in this format: "
                '{"entities": [{"name": "...", "description": "..."}]}'
            ),
        },
        {"role": "user", "content": text},
    ]

    try:
        # CHANGE: expect_json=True
        data = generate_response(prompt, expect_json=True)

        if not isinstance(data, dict):
            return []
        raw_entities = data.get("entities", [])
        if not isinstance(raw_entities, list):
            return []

        cleaned = []
        seen = set()
        for ent in raw_entities:
            if not isinstance(ent, dict):
                continue
            name = _clean(ent.get("name"))
            desc = _clean(ent.get("description"))
            if _is_invalid(name) or _is_invalid(desc):
                continue
            key = (name.lower(), desc.lower())
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({"name": name, "description": desc})
        return cleaned

    except Exception as e:
        print(f"[ERROR] extract_entities: {str(e)}")
        return []


def save_entities(conversation_id, entities):
    """
    Save or update entities in DB
    """

    try:
        for ent in entities:
            name = _clean(ent.get("name"))
            desc = _clean(ent.get("description"))

            if _is_invalid(name) or _is_invalid(desc):
                continue

            existing = Entity.query.filter_by(
                conversation_id=conversation_id, name=name
            ).first()

            if existing:
                existing.description = desc
            else:
                new_entity = Entity(
                    name=name, description=desc, conversation_id=conversation_id
                )
                db.session.add(new_entity)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] save_entities: {str(e)}")


def get_entities(conversation_id):
    """
    Fetch entities for prompt injection
    """

    try:
        entities = Entity.query.filter_by(conversation_id=conversation_id).all()

        return [f"{e.name}: {e.description}" for e in entities]

    except Exception as e:
        print(f"[ERROR] get_entities: {str(e)}")
        return []