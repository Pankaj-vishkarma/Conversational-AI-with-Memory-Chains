from services.llm_service import generate_response
from models.kg_triple import KGTriple
from models.conversation import Conversation
from extensions import db
from pydantic import BaseModel, Field

try:
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_GRAPH_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    ChatPromptTemplate = None  # type: ignore
    LANGCHAIN_GRAPH_AVAILABLE = False

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

ALLOWED_PREDICATES = {
    "works_at",
    "employed_by",
    "likes",
    "dislikes",
    "prefers",
    "lives_in",
    "located_in",
    "born_in",
    "born_on",
    "studies_at",
    "uses",
    "owns",
    "is_a",
    "has_role",
    "has_name",
}

PREDICATE_ALIASES = {
    "work_at": "works_at",
    "worksat": "works_at",
    "employed": "employed_by",
    "employer": "employed_by",
    "live_in": "lives_in",
    "lives": "lives_in",
    "located": "located_in",
    "born": "born_in",
    "studies": "studies_at",
    "name": "has_name",
    "called": "has_name",
    "role": "has_role",
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


def _normalize_predicate(value):
    predicate = _clean(value).lower().replace("-", "_").replace(" ", "_")
    return PREDICATE_ALIASES.get(predicate, predicate)


def _is_meaningful_graph_entity(value):
    token = _normalize_entity(value)
    lower = token.lower()

    if not token:
        return False
    if lower in GENERIC_ENTITIES:
        return False
    if lower == "user":
        return True
    if len(token) < 2:
        return False
    return True


def _is_meaningful_triple(subject, predicate, obj):
    s = _normalize_entity(subject)
    p = _normalize_predicate(predicate)
    o = _normalize_entity(obj)
    ls, lp, lo = s.lower(), p.lower(), o.lower()

    if not s or not p or not o:
        return False

    # Keep graph edges factual and non-trivial.
    if not _is_meaningful_graph_entity(s) or not _is_meaningful_graph_entity(o):
        return False

    if lp in VAGUE_PREDICATES:
        return False

    # allow meaningful predicate hints also
    if lp not in ALLOWED_PREDICATES and not any(
        h in lp for h in MEANINGFUL_PREDICATE_HINTS
    ):
        return False

    if len(p) < 2:
        return False

    if len(s) < 2 and ls != "user":
        return False

    if len(o) < 2 and lo != "user":
        return False

    if ls == lo:
        return False

    return True


def _coerce_triple_fields(triple):
    if isinstance(triple, dict):
        return triple.get("subject"), triple.get("predicate"), triple.get("object")
    return (
        getattr(triple, "subject", None),
        getattr(triple, "predicate", None),
        getattr(triple, "object", None),
    )


def _clean_triples(raw_triples):
    cleaned = []
    seen = set()

    for triple in raw_triples or []:
        subject, predicate, obj = _coerce_triple_fields(triple)
        subject = _normalize_entity(subject)
        predicate = _normalize_predicate(predicate)
        obj = _normalize_entity(obj)

        if not _is_meaningful_triple(subject, predicate, obj):
            continue

        key = (subject.lower(), predicate.lower(), obj.lower())
        if key in seen:
            continue

        seen.add(key)
        cleaned.append({"subject": subject, "predicate": predicate, "object": obj})

        # FIX: link user with entities for cross-memory
        if subject != "user" and obj != "user":
            user_key = ("user", "related_to", subject.lower())
            if user_key not in seen:
                seen.add(user_key)
                cleaned.append(
                    {"subject": "user", "predicate": "related_to", "object": subject}
                )

    return cleaned


class ExtractedTriple(BaseModel):
    subject: str = Field(..., description="Subject entity of the fact")
    predicate: str = Field(
        ..., description="Normalized relationship label such as works_at or likes"
    )
    object: str = Field(..., description="Object entity or value of the fact")


class TripleExtractionResult(BaseModel):
    triples: list[ExtractedTriple] = Field(default_factory=list)


def extract_triples(text):
    print("GRAPH_EXTRACTION_START")
    """
    Extract subject-predicate-object triples using LangChain structured output.
    """

    # SAFE FALLBACK FUNCTION
    def fallback_extraction():
        try:
            fallback_prompt = [
                {
                    "role": "system",
                    "content": (
                        "Extract relationships as triples. "
                        "Only include factual, meaningful relationships "
                        "(for example works_at, likes, lives_in, prefers, owns). "
                        "Do NOT include vague conversational triples like "
                        "(user, said, hello). "
                        'Return ONLY valid JSON in this format: {"triples":[{"subject":"","predicate":"","object":""}]}'
                    ),
                },
                {"role": "user", "content": text},
            ]

            data = generate_response(fallback_prompt, expect_json=True)

            if not isinstance(data, dict):
                return []

            raw_triples = data.get("triples", [])
            if not isinstance(raw_triples, list):
                return []

            return _clean_triples(raw_triples)

        except Exception as e:
            print(f"[ERROR] fallback triple extraction: {str(e)}")
            return []

    # LangChain unavailable → direct fallback
    if not LANGCHAIN_GRAPH_AVAILABLE:
        print("[WARNING] LangChain graph not available → fallback")
        return fallback_extraction()

    try:
        from services.llm_service import get_chat_model

        chat_model = get_chat_model(temperature=0.1, max_tokens=512)

        if chat_model is None:
            print("[WARNING] chat_model None → fallback")
            return fallback_extraction()

        if not hasattr(chat_model, "with_structured_output"):
            print("[WARNING] structured output not supported → fallback")
            return fallback_extraction()

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract relationships as triples. "
                    "Only include factual, meaningful relationships "
                    "(for example works_at, likes, lives_in, prefers, owns). "
                    "Do not include vague conversational triples like "
                    "(user, said, hello).",
                ),
                ("human", "{text}"),
            ]
        )

        chain = prompt | chat_model.with_structured_output(TripleExtractionResult)
        parsed = chain.invoke({"text": text})

        raw_triples = parsed.triples if parsed else []
        return _clean_triples(raw_triples)

    except Exception as exc:
        print(f"[WARNING] structured triple extraction failed → fallback: {exc}")
        return fallback_extraction()


def save_triples(conversation_id, triples):
    """
    Save triples to DB
    """

    try:
        seen = set()
        for t in triples:
            subject = _normalize_entity(t.get("subject"))
            predicate = _normalize_predicate(t.get("predicate"))
            obj = _normalize_entity(t.get("object"))

            if not _is_meaningful_triple(subject, predicate, obj):
                continue

            key = (subject.lower(), predicate.lower(), obj.lower())
            if key in seen:
                continue
            seen.add(key)

            existing = KGTriple.query.filter_by(
                conversation_id=conversation_id,
                subject=subject,
                predicate=predicate,
                object=obj,
            ).first()
            if existing:
                continue

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
    Convert user-level triples to prompt text.
    """

    try:
        conversation = Conversation.query.filter_by(id=conversation_id).first()
        if not conversation:
            return []

        return get_user_graph_context(conversation.user_id)

    except Exception as e:
        print(f"[ERROR] get_graph_context: {str(e)}")
        return []


def get_user_graph_context(user_id):
    if not user_id:
        return []

    try:
        triples = (
            KGTriple.query.join(
                Conversation, KGTriple.conversation_id == Conversation.id
            )
            .filter(Conversation.user_id == user_id)
            .order_by(KGTriple.created_at.asc())
            .all()
        )

        filtered = []
        for t in triples:
            subject = (t.subject or "").lower()
            obj = (t.object or "").lower()

            # FIX: only include user-related triples
            if subject == "user" or obj == "user":
                filtered.append(f"{t.subject} {t.predicate} {t.object}")

        return filtered

    except Exception as e:
        print(f"[ERROR] get_user_graph_context: {str(e)}")
        return []


def get_graph_payload(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id).first()
    if not conversation:
        return {"nodes": [], "edges": [], "triples": []}

    triples = (
        KGTriple.query.join(Conversation, KGTriple.conversation_id == Conversation.id)
        .filter(Conversation.user_id == conversation.user_id)
        .order_by(KGTriple.created_at.asc())
        .all()
    )
    node_map = {}
    links = []

    for triple in triples:
        if triple.subject and triple.subject not in node_map:
            node_map[triple.subject] = {"id": triple.subject, "name": triple.subject}
        if triple.object and triple.object not in node_map:
            node_map[triple.object] = {"id": triple.object, "name": triple.object}

        links.append(
            {
                "source": triple.subject,
                "target": triple.object,
                "label": triple.predicate,
                "subject": triple.subject,
                "predicate": triple.predicate,
                "object": triple.object,
            }
        )

    return {
        "nodes": list(node_map.values()),
        "edges": links,
        "triples": [
            {"subject": t.subject, "predicate": t.predicate, "object": t.object}
            for t in triples
        ],
    }
