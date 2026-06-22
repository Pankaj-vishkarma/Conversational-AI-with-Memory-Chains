from flask import Blueprint, jsonify, request, Response
from models.message import Message
from models.summary import Summary
from models.entity import Entity
from models.kg_triple import KGTriple

from flask_jwt_extended import jwt_required, get_jwt_identity
from models.conversation import Conversation

export_bp = Blueprint("export", __name__)


def _build_markdown_export(conversation, messages, summary_data, entities_data, graph_data):
    lines = [f"# {conversation.title or 'Conversation'}", ""]
    lines.append("## Metadata")
    lines.append(f"- Conversation ID: {conversation.id}")
    lines.append(f"- Memory Type: {conversation.memory_type}")
    lines.append("")

    lines.append("## Summary")
    lines.append(summary_data or "_No summary available_")
    lines.append("")

    lines.append("## Entities")
    if entities_data:
        for entity in entities_data:
            lines.append(f"- **{entity['name']}**: {entity['description']}")
    else:
        lines.append("_No entities_")
    lines.append("")

    lines.append("## Knowledge Graph")
    if graph_data:
        for triple in graph_data:
            lines.append(
                f"- `{triple['subject']} --{triple['predicate']}--> {triple['object']}`"
            )
    else:
        lines.append("_No graph triples_")
    lines.append("")

    lines.append("## Messages")
    for item in messages:
        lines.append(f"### {item.role.capitalize()}")
        lines.append(item.content or "")
        lines.append("")

    return "\n".join(lines)


@export_bp.route("/<conversation_id>", methods=["GET"])
@jwt_required()
def export_conversation(conversation_id):
    try:
        user_id = get_jwt_identity()
        export_format = (request.args.get("format") or "json").strip().lower()

        # IMPORTANT: ownership check
        conversation = Conversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()

        if not conversation:
            return jsonify({"error": "Unauthorized access"}), 403

        # ---------------- MESSAGES ----------------
        messages = (
            Message.query.filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        messages_data = [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

        # ---------------- SUMMARY ----------------
        summary = Summary.query.filter_by(conversation_id=conversation_id).first()

        summary_data = summary.content if summary else ""

        # ---------------- ENTITIES ----------------
        entities = Entity.query.filter_by(conversation_id=conversation_id).all()

        entities_data = [
            {"name": e.name, "description": e.description} for e in entities
        ]

        # ---------------- GRAPH ----------------
        triples = KGTriple.query.filter_by(conversation_id=conversation_id).all()

        graph_data = [
            {"subject": t.subject, "predicate": t.predicate, "object": t.object}
            for t in triples
        ]

        # ---------------- FINAL RESPONSE ----------------
        payload = {
            "conversation_id": conversation_id,
            "messages": messages_data,
            "summary": summary_data,
            "entities": entities_data,
            "knowledge_graph": graph_data,
        }

        if export_format == "markdown":
            markdown = _build_markdown_export(
                conversation, messages, summary_data, entities_data, graph_data
            )
            return Response(markdown, mimetype="text/markdown")

        return jsonify({"success": True, "data": payload})

    except Exception as e:
        print(f"[ERROR] export_conversation: {str(e)}")
        return jsonify({"error": "Failed to export conversation"}), 500
