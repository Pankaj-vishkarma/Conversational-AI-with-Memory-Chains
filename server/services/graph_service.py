from services.llm_service import generate_response
from models.kg_triple import KGTriple
from extensions import db

GENERIC_ENTITIES = {
    "assistant",
    "ai",
    "bot",
    "someone",
    "something",
    "thing",
    "it",
    "this",
    "that",
    "hello",
    "hi",
}

VAGUE_PREDICATES = {
    "said",
    "says",
    "tell",
    "told",
    "asked",
    "ask",
    "mentioned",
    "speak",
    "talked",
    "is",
    "are",
    "was",
    "were",
}

MEANINGFUL_PREDICATE_HINTS = {
    "work",
    "works_at",
    "employed",
    "likes",
    "dislikes",
    "prefers",
    "lives",
    "lives_in",
    "located",
    "born",
    "studies",
    "uses",
    "owns",
    "name",
    "called",
}


def _clean(value):
    return (value or "").strip()


def _normalize_entity(value):
    token = _clean(value)
    lower = token.lower()
    # Normalize first-person references so user facts can be retained.
    if lower in {"i", "me", "my", "myself"}:
        return "user"
    return token


def _is_meaningful_triple(subject, predicate, obj):
    s = _normalize_entity(subject)
    p = _clean(predicate)
    o = _normalize_entity(obj)
    ls, lp, lo = s.lower(), p.lower(), o.lower()

    if not s or not p or not o:
        return False

    # Keep graph edges factual and non-trivial.
    if ls in GENERIC_ENTITIES or lo in GENERIC_ENTITIES:
        return False
    if lp in VAGUE_PREDICATES:
        return False
    if len(p) < 2:
        return False
    if len(s) < 2 and ls != "user":
        return False
    if len(o) < 2 and lo != "user":
        return False
    if ls == lo:
        return False

    if any(hint in lp for hint in MEANINGFUL_PREDICATE_HINTS):
        return True

    # Predicate can still be meaningful even if not in hints, as long as
    # both ends look like concrete entities and predicate is not vague.
    if len(s.split()) >= 1 and len(o.split()) >= 1:
        return True

    return False


def extract_triples(text):
    """
    Extract subject-predicate-object triples using LLM
    """

    prompt = [
        {
            "role": "system",
            "content": (
                "Extract relationships as triples. "
                "Only include factual, meaningful relationships "
                "(e.g. works_at, likes, lives_in, prefers, owns). "
                "Do NOT include vague conversational triples like "
                "(user, said, hello). "
                "Return ONLY valid JSON in this format: "
                '{"triples":[{"subject":"","predicate":"","object":""}]}'
            ),
        },
        {"role": "user", "content": text},
    ]

    try:
        # CHANGE: expect_json=True
        data = generate_response(prompt, expect_json=True)

        if not isinstance(data, dict):
            return []

        return data.get("triples", [])

    except Exception as e:
        print(f"[ERROR] extract_triples: {str(e)}")
        return []


def save_triples(conversation_id, triples):
    """
    Save triples to DB
    """

    try:
        seen = set()
        for t in triples:
            subject = _normalize_entity(t.get("subject"))
            predicate = _clean(t.get("predicate"))
            obj = _normalize_entity(t.get("object"))

            if not _is_meaningful_triple(subject, predicate, obj):
                continue

            key = (subject.lower(), predicate.lower(), obj.lower())
            if key in seen:
                continue
            seen.add(key)

            new_triple = KGTriple(
                subject=subject,
                predicate=predicate,
                object=obj,
                conversation_id=conversation_id,
            )

            db.session.add(new_triple)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] save_triples: {str(e)}")


def get_graph_context(conversation_id):
    """
    Convert triples to prompt text
    """

    try:
        triples = KGTriple.query.filter_by(conversation_id=conversation_id).all()

        return [f"{t.subject} {t.predicate} {t.object}" for t in triples]

    except Exception as e:
        print(f"[ERROR] get_graph_context: {str(e)}")
        return []