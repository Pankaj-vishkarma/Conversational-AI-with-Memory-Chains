from services.message_service import get_conversation_messages
from services.llm_service import generate_response
from models.summary import Summary
from extensions import db


SUMMARY_TRIGGER_COUNT = 3  # delay summary for better performance


def build_buffer_memory(conversation_id):
    messages = get_conversation_messages(conversation_id)

    history = []
    for msg in messages:
        history.append({"role": msg.role, "content": msg.content})

    return history


def get_summary(conversation_id):
    summary = Summary.query.filter_by(conversation_id=conversation_id).first()
    return summary.content if summary else None


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

    prompt = [
        {
            "role": "system",
            "content": "Summarize the conversation with key facts, decisions, and context.",
        },
        {"role": "user", "content": chat_text},
    ]

    summary_text = generate_response(prompt)
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
