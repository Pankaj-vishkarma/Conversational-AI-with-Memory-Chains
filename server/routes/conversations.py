from flask import Blueprint, current_app, request, jsonify
from services.conversation_service import (
    create_conversation,
    get_all_conversations,
    serialize_conversation,
)

from flask_jwt_extended import jwt_required, get_jwt_identity

conversations_bp = Blueprint("conversations", __name__)


# CREATE CONVERSATION
@conversations_bp.route("/", methods=["POST"])
@jwt_required()
def create():
    try:
        user_id = get_jwt_identity()

        data = request.get_json(silent=True) or {}
        data["user_id"] = user_id

        convo = create_conversation(data)
        serialized = serialize_conversation(convo)

        return jsonify({"success": True, "id": convo.id, "conversation": serialized})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception:
        current_app.logger.exception("Failed to create conversation")
        return jsonify({"success": False, "error": "Failed to create conversation"}), 500


# GET USER CONVERSATIONS
@conversations_bp.route("/", methods=["GET"])
@jwt_required()
def list_conversations():
    try:
        user_id = get_jwt_identity()

        convos = get_all_conversations(user_id)
        serialized = [serialize_conversation(c) for c in convos]

        return jsonify(
            {
                "success": True,
                "data": serialized,
                "conversations": serialized,
            }
        )

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception:
        current_app.logger.exception("Failed to fetch conversations")
        return jsonify({"success": False, "error": "Failed to fetch conversations"}), 500
