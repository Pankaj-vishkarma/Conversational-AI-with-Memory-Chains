from flask import Blueprint, request, jsonify
from services.auth_service import register_user, login_user
from flask_jwt_extended import create_access_token, jwt_required, get_jwt


from models.token_blocklist import TokenBlocklist
from extensions import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        user, error = register_user(name, email, password)

        if error:
            return jsonify({"error": error}), 400

        return (
            jsonify(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "user_id": user.id,
                }
            ),
            201,
        )

    except Exception as e:
        print(f"[ERROR] register route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        email = data.get("email")
        password = data.get("password")

        user = login_user(email, password)

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        token = create_access_token(identity=user.id)

        return jsonify({"success": True, "token": token, "user_id": user.id}), 200

    except Exception as e:
        print(f"[ERROR] login route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


# LOGOUT ROUTE
@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        jwt_data = get_jwt()
        jti = jwt_data["jti"]

        blocked_token = TokenBlocklist(jti=jti)
        db.session.add(blocked_token)
        db.session.commit()

        return jsonify({"success": True, "message": "Logged out successfully"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] logout route: {str(e)}")
        return jsonify({"error": "Logout failed"}), 500
