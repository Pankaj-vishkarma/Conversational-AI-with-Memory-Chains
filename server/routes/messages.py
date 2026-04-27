from flask import Blueprint, current_app, request, jsonify
from services.message_service import save_message, get_conversation_messages
from services.conversation_service import update_default_title_from_message
from services.chain_service import run_conversation_chain
from services.memory_service import update_summary
from services.entity_service import extract_entities_from_text, save_entities
from services.graph_service import extract_triples, save_triples

from concurrent.futures import ThreadPoolExecutor

from flask_jwt_extended import jwt_required, get_jwt_identity
from models.conversation import Conversation
from extensions import db

messages_bp = Blueprint("messages", __name__)

# Thread pool (global)
executor = ThreadPoolExecutor(max_workers=1)


PERSONAL_INFO_MARKERS = [
    "my ",
    "name is",
    "i am",
    "i work",
    "i live",
    "i prefer",
    "i like",
    "i'm",
]


def _has_meaningful_content(text):
    return len((text or "").strip().split()) > 3


def _contains_personal_info(text):
    lowered = (text or "").lower()
    return any(marker in lowered for marker in PERSONAL_INFO_MARKERS)


@messages_bp.route("/", methods=["POST"], strict_slashes=False)
@jwt_required()
def send_message():
    try:
        user_id = get_jwt_identity()

        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        conversation_id = data.get("conversation_id")
        user_message = data.get("message") or data.get("content")

        if not conversation_id or not user_message:
            return jsonify({"error": "Missing fields"}), 400

        # IMPORTANT: Check conversation ownership
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        # Save user message
        user_msg = save_message(conversation_id, "user", user_message)

        if not user_msg:
            return jsonify({"error": "Failed to save message"}), 500

        update_default_title_from_message(conversation, user_message)

        try:
            # Run AI chain
            ai_response = run_conversation_chain(conversation_id, user_message)

            # Save AI response
            ai_msg = save_message(conversation_id, "assistant", ai_response)

            if not ai_msg:
                raise Exception("Failed to save AI response")

        except Exception as e:
            try:
                db.session.delete(user_msg)
                db.session.commit()
            except Exception as rollback_error:
                print(f"[CRITICAL] Rollback failed: {str(rollback_error)}")

            print(f"[ERROR] AI generation failed: {str(e)}")
            return jsonify({"error": "Failed to generate response"}), 500

        app = current_app._get_current_object()
        should_extract_memory = _has_meaningful_content(
            user_message
        ) or _contains_personal_info(user_message)
        message_count = len(get_conversation_messages(conversation_id))
        should_update_summary = message_count >= 3 and message_count % 4 == 0

        # Background enrichment (throttled)
        def run_memory_tasks():
            with app.app_context():
                try:
                    if should_extract_memory:
                        entities = extract_entities_from_text(user_message)
                        print("Extracted entities:", entities)
                        if entities:
                            save_entities(conversation_id, entities)
                            triples = extract_triples(user_message)
                            if triples:
                                save_triples(conversation_id, triples)

                    if should_update_summary:
                        update_summary(conversation_id)
                except Exception as e:
                    print(f"[WARNING] Memory task failed: {str(e)}")

        executor.submit(run_memory_tasks)

        # Return response immediately
        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "conversation_id": conversation_id,
                        "response": ai_response,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[ERROR] send_message: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@messages_bp.route("/<conversation_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
def list_messages(conversation_id):
    try:
        user_id = get_jwt_identity()

        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        messages = get_conversation_messages(conversation_id)

        data = [
            {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "role": message.role,
                "content": message.content,
                "created_at": (
                    message.created_at.isoformat() if message.created_at else None
                ),
            }
            for message in messages
        ]

        return jsonify({"success": True, "data": data, "messages": data}), 200

    except Exception as e:
        print(f"[ERROR] list_messages: {str(e)}")
        return jsonify({"error": "Failed to fetch messages"}), 500
