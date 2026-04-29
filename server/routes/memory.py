from flask import Blueprint, jsonify
from models.summary import Summary
from models.entity import Entity
from models.kg_triple import KGTriple
from services.message_service import get_conversation_messages
import tiktoken

from services.llm_service import generate_response
from services.memory_service import build_buffer_memory, get_summary
from services.chain_service import get_merged_entities
from services.graph_service import get_graph_context, get_graph_payload

from flask_jwt_extended import jwt_required, get_jwt_identity
from models.conversation import Conversation

memory_bp = Blueprint("memory", __name__)


def _entity_type(name, description):
    text = f"{name or ''} {description or ''}".lower()
    if any(word in text for word in ["company", "organization", "org"]):
        return "organization"
    if any(word in text for word in ["project", "product"]):
        return "project"
    if any(word in text for word in ["city", "country", "location"]):
        return "location"
    if any(word in text for word in ["date", "time", "birthday", "deadline"]):
        return "date"
    if any(word in text for word in ["role", "job", "employer"]):
        return "role"
    if any(word in text for word in ["person", "name", "employee"]):
        return "person"
    return "entity"


# ---------------- ENTITIES ----------------
@memory_bp.route("/<conversation_id>/entities", methods=["GET"])
@jwt_required()
def get_entities_api(conversation_id):
    try:
        user_id = get_jwt_identity()

        # ownership check
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        user_facts, merged_context = get_merged_entities(conversation_id)
        entity_lines = [f"{label}: {value}" for label, value in user_facts]
        entity_lines.extend(merged_context)

        return jsonify(
            {
                "success": True,
                "data": [
                    {
                        "name": line.split(":", 1)[0].strip() if ":" in line else line,
                        "type": _entity_type(
                            line.split(":", 1)[0].strip() if ":" in line else line,
                            line.split(":", 1)[1].strip() if ":" in line else "",
                        ),
                        "description": (
                            line.split(":", 1)[1].strip() if ":" in line else ""
                        ),
                        "updated_at": None,
                    }
                    for line in entity_lines
                ],
            }
        )

    except Exception as e:
        print(f"[ERROR] get_entities_api: {str(e)}")
        return jsonify({"error": "Failed to fetch entities"}), 500


# ---------------- KNOWLEDGE GRAPH ----------------
@memory_bp.route("/<conversation_id>/graph", methods=["GET"])
@jwt_required()
def get_graph_api(conversation_id):
    try:
        user_id = get_jwt_identity()

        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        payload = get_graph_payload(conversation_id)

        return jsonify(
            {
                "success": True,
                "data": {
                    "nodes": payload["nodes"],
                    "edges": payload["edges"],
                    "relationships": payload["edges"],
                    "triples": payload["triples"],
                },
            }
        )

    except Exception as e:
        print(f"[ERROR] get_graph_api: {str(e)}")
        return jsonify({"error": "Failed to fetch graph"}), 500


# ---------------- SUMMARY ----------------
@memory_bp.route("/<conversation_id>/summary", methods=["GET"])
@jwt_required()
def get_summary_api(conversation_id):
    try:
        user_id = get_jwt_identity()

        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        summary = Summary.query.filter_by(conversation_id=conversation_id).first()

        return jsonify({"success": True, "data": summary.content if summary else ""})

    except Exception as e:
        print(f"[ERROR] get_summary_api: {str(e)}")
        return jsonify({"error": "Failed to fetch summary"}), 500


# ---------------- TOKEN USAGE ----------------
@memory_bp.route("/<conversation_id>/tokens", methods=["GET"])
@jwt_required()
def get_token_usage(conversation_id):
    try:
        user_id = get_jwt_identity()

        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        messages = get_conversation_messages(conversation_id)

        encoder = tiktoken.get_encoding("cl100k_base")

        total_tokens = 0

        for msg in messages:
            total_tokens += len(encoder.encode(msg.content))

        return jsonify(
            {
                "success": True,
                "data": {
                    "total_tokens": total_tokens,
                    "message_count": len(messages),
                },
            }
        )

    except Exception as e:
        print(f"[ERROR] get_token_usage: {str(e)}")
        return jsonify({"error": "Failed to calculate tokens"}), 500


# ================= MEMORY COMPARISON =================
@memory_bp.route("/compare/<conversation_id>", methods=["GET"])
@jwt_required()
def compare_memory(conversation_id):
    try:
        user_id = get_jwt_identity()

        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        user_input = "What do you know about me?"

        # -------- BUFFER --------
        buffer_context = build_buffer_memory(conversation_id)[-5:]
        buffer_messages = [
            {"role": "system", "content": "Answer using conversation history only."}
        ]
        buffer_messages.extend(buffer_context)
        buffer_messages.append({"role": "user", "content": user_input})
        buffer_response = generate_response(buffer_messages)

        # -------- SUMMARY --------
        summary = get_summary(conversation_id)
        summary_messages = [{"role": "system", "content": "Answer using summary only."}]
        if summary:
            summary_messages.append({"role": "system", "content": summary})
        summary_messages.append({"role": "user", "content": user_input})
        summary_response = generate_response(summary_messages)

        # -------- ENTITY --------
        user_facts, merged_context = get_merged_entities(conversation_id)
        entity_lines = [f"{label}: {value}" for label, value in user_facts]
        entity_lines.extend(merged_context)
        entity_messages = [
            {"role": "system", "content": "Answer using known facts only."}
        ]
        if entity_lines:
            entity_messages.append(
                {"role": "system", "content": "\n".join(entity_lines)}
            )
        entity_messages.append({"role": "user", "content": user_input})
        entity_response = generate_response(entity_messages)

        # -------- GRAPH --------
        graph = get_graph_context(conversation_id)
        graph_messages = [
            {"role": "system", "content": "Answer using relationships only."}
        ]
        if graph:
            graph_messages.append({"role": "system", "content": "\n".join(graph)})
        graph_messages.append({"role": "user", "content": user_input})
        graph_response = generate_response(graph_messages)

        # -------- HYBRID --------
        hybrid_messages = [
            {
                "role": "system",
                "content": "Answer using summary, known facts, relationships, and recent messages.",
            }
        ]
        if summary:
            hybrid_messages.append(
                {"role": "system", "content": f"Summary:\n{summary}"}
            )
        if entity_lines:
            hybrid_messages.append(
                {"role": "system", "content": "Entities:\n" + "\n".join(entity_lines)}
            )
        if graph:
            hybrid_messages.append(
                {"role": "system", "content": "Graph:\n" + "\n".join(graph)}
            )
        hybrid_messages.extend(build_buffer_memory(conversation_id)[-5:])
        hybrid_messages.append({"role": "user", "content": user_input})
        hybrid_response = generate_response(hybrid_messages)

        return jsonify(
            {
                "success": True,
                "data": {
                    "input": user_input,
                    "buffer_memory": buffer_response,
                    "summary_memory": summary_response,
                    "entity_memory": entity_response,
                    "knowledge_graph_memory": graph_response,
                    "hybrid_memory": hybrid_response,
                },
            }
        )

    except Exception as e:
        print(f"[ERROR] compare_memory: {str(e)}")
        return jsonify({"error": "Comparison failed"}), 500
