from services.message_service import get_conversation_messages
from services.llm_service import generate_response, get_chat_model
from models.summary import Summary
from models.entity import Entity
from models.conversation import Conversation
from extensions import db

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_MEMORY_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    StrOutputParser = ChatPromptTemplate = None  # type: ignore
    LANGCHAIN_MEMORY_AVAILABLE = False


BUFFER_MESSAGE_LIMIT = 20
SUMMARY_TRIGGER_COUNT = 5
SUMMARY_RECENT_TAIL = 5


def build_buffer_memory(conversation_id, max_messages=None):
    messages = get_conversation_messages(conversation_id)
    if max_messages is None:
        max_messages = BUFFER_MESSAGE_LIMIT
    if max_messages and max_messages > 0:
        messages = messages[-max_messages:]

    history = []
    for msg in messages:
        history.append({"role": msg.role, "content": msg.content})

    return history


def get_summary(conversation_id):
    summary = Summary.query.filter_by(conversation_id=conversation_id).first()
    return summary.content if summary else None


def get_user_entities_by_conversation(conversation_id):
    """
    Resolve user by conversation and fetch entities by user scope.
    Returned latest-first for "latest value wins" merging.
    """
    conversation = Conversation.query.filter_by(id=conversation_id).first()
    if not conversation:
        return []

    return get_user_entities(conversation.user_id)


def get_user_entities(user_id):
    """
    Fetch all entities belonging to a user across conversations.
    """
    return (
        Entity.query.join(Conversation, Entity.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id)
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .all()
    )


def get_user_summaries_by_conversation(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id).first()
    if not conversation:
        return []

    return (
        Summary.query.join(Conversation, Summary.conversation_id == Conversation.id)
        .filter(Conversation.user_id == conversation.user_id)
        .order_by(Summary.updated_at.desc())
        .all()
    )


def update_summary(conversation_id):
    """
    Generate or update summary after N messages
    """
    print(f"[DEBUG] update_summary triggered for conversation_id={conversation_id}")

    messages = get_conversation_messages(conversation_id)
    message_count = len(messages)
    print(f"[DEBUG] update_summary message_count={message_count}")

    if message_count < SUMMARY_TRIGGER_COUNT:
        print(
            f"[DEBUG] update_summary skipped: need {SUMMARY_TRIGGER_COUNT}, got {message_count}"
        )
        return

    # Prepare text for summarization
    chat_text = "\n".join([f"{m.role}: {m.content}" for m in messages])
    print(f"[DEBUG] update_summary chat_text_length={len(chat_text)}")

    summary_text = ""

    if LANGCHAIN_MEMORY_AVAILABLE:
        try:
            chat_model = get_chat_model(temperature=0.2, max_tokens=512)
            if chat_model is not None:
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "Create a factual summary of the conversation. "
                            "Use ONLY information explicitly stated in the chat messages. "
                            "Do NOT infer, assume, speculate, or add external knowledge. "
                            "If a detail is uncertain or not explicitly stated, do not include it. "
                            "Prefer concise bullet points covering confirmed facts and decisions.",
                        ),
                        ("human", "{chat_text}"),
                    ]
                )
                summary_chain = prompt | chat_model | StrOutputParser()
                summary_text = summary_chain.invoke({"chat_text": chat_text})
        except Exception as exc:
            print(f"[WARNING] update_summary LangChain path failed: {exc}")

    if not summary_text:
        fallback_prompt = [
            {
                "role": "system",
                "content": (
                    "Create a factual summary of the conversation. "
                    "Use ONLY information explicitly stated in the chat messages. "
                    "Do NOT infer, assume, speculate, or add external knowledge. "
                    "If a detail is uncertain or not explicitly stated, do not include it. "
                    "Prefer concise bullet points covering confirmed facts and decisions."
                ),
            },
            {"role": "user", "content": chat_text},
        ]
        summary_text = generate_response(fallback_prompt)
    print(f"[DEBUG] update_summary generated={bool(summary_text)}")

    if not summary_text:
        print("[WARNING] update_summary skipped: empty summary response")
        return

    try:
        existing = Summary.query.filter_by(conversation_id=conversation_id).first()

        if existing:
            existing.content = summary_text
            print("[DEBUG] update_summary updating existing summary")
        else:
            new_summary = Summary(conversation_id=conversation_id, content=summary_text)
            db.session.add(new_summary)
            print("[DEBUG] update_summary creating new summary")

        db.session.commit()
        print("[DEBUG] update_summary saved successfully")

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] update_summary: {str(e)}")
