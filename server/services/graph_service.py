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
    if lp not in ALLOWED_PREDICATES:
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


class ExtractedTriple(BaseModel):
    subject: str = Field(..., description="Subject entity of the fact")
    predicate: str = Field(
        ..., description="Normalized relationship label such as works_at or likes"
    )
    object: str = Field(..., description="Object entity or value of the fact")


class TripleExtractionResult(BaseModel):
    triples: list[ExtractedTriple] = Field(default_factory=list)


def extract_triples(text):
    """
    Extract subject-predicate-object triples using LangChain structured output.
    """
    if not LANGCHAIN_GRAPH_AVAILABLE:
        raise_runtime = RuntimeError("LangChain graph extraction unavailable")
        print(f"[WARNING] structured triple extraction failed: {raise_runtime}")
        try:
            fallback_prompt = [
                {
                    "role": "system",
                    "content": (
                        "Extract relationships as triples. "
                        "Only include factual, meaningful relationships "
                        "(e.g. works_at, likes, lives_in, prefers, owns). "
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

            triples = data.get("triples", [])
            return triples if isinstance(triples, list) else []
        except Exception as e:
            print(f"[ERROR] extract_triples: {str(e)}")
            return []

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

    try:
        from services.llm_service import get_chat_model

        chat_model = get_chat_model(temperature=0.1, max_tokens=512)
        if chat_model is None or not hasattr(chat_model, "with_structured_output"):
            raise RuntimeError("Structured output model unavailable")

        chain = prompt | chat_model.with_structured_output(TripleExtractionResult)
        parsed = chain.invoke({"text": text})
        triples = parsed.triples if parsed else []
        return [
            {
                "subject": item.subject,
                "predicate": item.predicate,
                "object": item.object,
            }
            for item in triples
        ]

    except Exception as exc:
        print(f"[WARNING] structured triple extraction failed: {exc}")
        try:
            fallback_prompt = [
                {
                    "role": "system",
                    "content": (
                        "Extract relationships as triples. "
                        "Only include factual, meaningful relationships "
                        "(e.g. works_at, likes, lives_in, prefers, owns). "
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

            triples = data.get("triples", [])
            return triples if isinstance(triples, list) else []
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
            predicate = _normalize_predicate(t.get("predicate"))
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


def get_user_graph_context_by_conversation(conversation_id):
    try:
        conversation = Conversation.query.filter_by(id=conversation_id).first()
        if not conversation:
            return []

        triples = (
            KGTriple.query.join(
                Conversation, KGTriple.conversation_id == Conversation.id
            )
            .filter(Conversation.user_id == conversation.user_id)
            .order_by(KGTriple.created_at.asc())
            .all()
        )

        return [f"{t.subject} {t.predicate} {t.object}" for t in triples]

    except Exception as e:
        print(f"[ERROR] get_user_graph_context_by_conversation: {str(e)}")
        return []


def get_graph_payload(conversation_id):
    triples = KGTriple.query.filter_by(conversation_id=conversation_id).all()
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
