from services.llm_service import generate_response
from models.entity import Entity
from extensions import db
from sqlalchemy import func

INVALID_VALUES = {
    "",
    "user",
    "your name",
    "unknown",
    "i don't know",
    "i dont know",
}

GENERIC_ENTITY_WORDS = {
    "thing",
    "things",
    "something",
    "anything",
    "everything",
    "stuff",
    "work",
    "job",
    "task",
    "tasks",
    "info",
    "information",
    "detail",
    "details",
}

MEANINGFUL_ENTITY_HINTS = {
    "person",
    "name",
    "company",
    "organization",
    "org",
    "project",
    "product",
    "preference",
    "likes",
    "dislikes",
    "date",
    "time",
    "birthday",
    "location",
    "city",
    "country",
    "language",
    "role",
    "employer",
    "works at",
}


def _clean(value):
    return (value or "").strip()


def _is_invalid(value):
    return _clean(value).lower() in INVALID_VALUES


def _is_meaningful_entity(name, description):
    clean_name = _clean(name)
    clean_desc = _clean(description)
    lower_name = clean_name.lower()
    lower_desc = clean_desc.lower()
    combined = f"{lower_name} {lower_desc}"

    if not clean_name or not clean_desc:
        return False

    # Keep explicit memory-instruction fallback notes.
    if lower_name == "memory_note":
        return len(clean_desc.split()) >= 2

    # Drop obvious generic/noisy entities.
    if lower_name in GENERIC_ENTITY_WORDS or lower_desc in GENERIC_ENTITY_WORDS:
        return False
    if len(clean_name) < 2:
        return False

    # Keep entities with meaningful semantic hints.
    if any(hint in combined for hint in MEANINGFUL_ENTITY_HINTS):
        return True

    # Keep likely proper entities (multi-word names, IDs, titled entities).
    if len(clean_name.split()) >= 2:
        return True
    if any(ch.isdigit() for ch in clean_name):
        return True

    return False


def _normalize_entity_name(name):
    return _clean(name).lower()


def extract_entities_from_text(text):
    """
    Use LLM to extract entities from user message
    """

    prompt = [
        {
            "role": "system",
            "content": (
                "Extract important entities from the text. "
                "Only include meaningful entities such as person, company, organization, "
                "project, preference, date/time, role, or location. "
                "Do NOT include generic words like thing, something, work, task, or info. "
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
            if not _is_meaningful_entity(name, desc):
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
        # Normalize incoming updates so latest mention wins per entity name.
        normalized_updates = {}
        for ent in entities:
            name = _clean(ent.get("name"))
            desc = _clean(ent.get("description"))

            if _is_invalid(name) or _is_invalid(desc):
                continue
            if not _is_meaningful_entity(name, desc):
                continue

            normalized_updates[_normalize_entity_name(name)] = {
                "name": name,
                "description": desc,
            }

        for normalized_name, payload in normalized_updates.items():
            existing_entities = (
                Entity.query.filter(
                    Entity.conversation_id == conversation_id,
                    func.lower(Entity.name) == normalized_name,
                )
                .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
                .all()
            )

            if existing_entities:
                canonical = existing_entities[0]
                canonical.name = payload["name"]
                canonical.description = payload["description"]

                # Remove stale duplicates for the same logical entity.
                for duplicate in existing_entities[1:]:
                    db.session.delete(duplicate)
            else:
                new_entity = Entity(
                    name=payload["name"],
                    description=payload["description"],
                    conversation_id=conversation_id,
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