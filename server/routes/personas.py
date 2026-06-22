from flask import Blueprint, request, jsonify
from services.persona_service import get_all_personas, create_persona
from flask_jwt_extended import jwt_required

personas_bp = Blueprint("personas", __name__)


@personas_bp.route("/", methods=["GET"])
def list_personas():
    personas = get_all_personas()

    return jsonify(
        [{"id": p.id, "name": p.name, "memory_type": p.memory_type} for p in personas]
    )


@personas_bp.route("/", methods=["POST"])
@jwt_required()
def create():
    data = request.json
    persona = create_persona(data)

    return jsonify({"id": persona.id})
