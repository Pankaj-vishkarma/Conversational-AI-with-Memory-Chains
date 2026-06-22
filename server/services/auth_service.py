from models.user import User
from extensions import db
from flask_bcrypt import generate_password_hash, check_password_hash


def register_user(name, email, password):
    try:
        # VALIDATION
        if not name or not email or not password:
            return None, "All fields are required"

        # DUPLICATE CHECK
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return None, "Email already exists"

        # HASH PASSWORD
        hashed_password = generate_password_hash(password).decode("utf-8")

        user = User(name=name, email=email, password=hashed_password)

        db.session.add(user)
        db.session.commit()

        return user, None

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] register_user: {str(e)}")
        return None, "Registration failed"


def login_user(email, password):
    try:
        if not email or not password:
            return None

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            return user

        return None

    except Exception as e:
        print(f"[ERROR] login_user: {str(e)}")
        return None
