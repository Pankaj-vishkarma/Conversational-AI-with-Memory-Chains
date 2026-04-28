from flask import Blueprint, current_app, request, jsonify
from services.conversation_service import (
    create_conversation,
    get_all_conversations,
    serialize_conversation,
    update_conversation,
)
from extensions import db
from models.conversation import Conversation
from models.message import Message
from models.summary import Summary
from models.entity import Entity
from models.kg_triple import KGTriple

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
        search = (request.args.get("q") or "").strip() or None

        pinned = request.args.get("pinned")
        if pinned is not None:
            pinned = pinned.strip().lower() in {"1", "true", "yes", "on"}

        archived = request.args.get("archived")
        if archived is not None:
            archived = archived.strip().lower() in {"1", "true", "yes", "on"}

        convos = get_all_conversations(
            user_id,
            search=search,
            pinned=pinned,
            archived=archived,
        )
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


@conversations_bp.route("/<conversation_id>", methods=["PATCH"])
@jwt_required()
def patch_conversation(conversation_id):
    try:
        user_id = get_jwt_identity()
        convo = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()

        if not convo:
            return jsonify({"success": False, "error": "Conversation not found"}), 404

        data = request.get_json(silent=True) or {}
        updated = update_conversation(convo, data)
        return jsonify({"success": True, "conversation": serialize_conversation(updated)})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception:
        current_app.logger.exception("Failed to update conversation")
        return jsonify({"success": False, "error": "Failed to update conversation"}), 500


@conversations_bp.route("/<conversation_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conversation_id):
    try:
        user_id = get_jwt_identity()
        convo = Conversation.query.filter_by(id=conversation_id, user_id=user_id).first()

        if not convo:
            return jsonify({"success": False, "error": "Conversation not found"}), 404

        Message.query.filter_by(conversation_id=conversation_id).delete()
        Summary.query.filter_by(conversation_id=conversation_id).delete()
        Entity.query.filter_by(conversation_id=conversation_id).delete()
        KGTriple.query.filter_by(conversation_id=conversation_id).delete()
        db.session.delete(convo)
        db.session.commit()

        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete conversation")
        return jsonify({"success": False, "error": "Failed to delete conversation"}), 500
