"""Authentication service. Passwords are always hashed with bcrypt —
never stored or compared in plaintext, per architecture doc Section 2.
"""
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select

from app.models.user import User


def create_user(session, username: str, password: str) -> User:
    if not username or not username.strip():
        raise ValueError("Username is required")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters")

    existing = session.execute(select(User).where(User.username == username.strip())).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"Username '{username}' already exists")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(username=username.strip(), password_hash=password_hash)
    session.add(user)
    session.commit()
    return user


def authenticate(session, username: str, password: str) -> User:
    """Returns the User on success. Raises ValueError with a deliberately
    generic message on failure — never reveal whether the username or
    the password was the wrong part, standard practice against
    username-enumeration.
    """
    user = session.execute(select(User).where(User.username == (username or "").strip())).scalar_one_or_none()
    if user is None:
        raise ValueError("Invalid username or password")
    if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise ValueError("Invalid username or password")

    user.last_login = datetime.now(timezone.utc)
    session.commit()
    return user


def any_user_exists(session) -> bool:
    """Used to decide whether to show a first-run 'create account'
    screen instead of a login screen."""
    return session.execute(select(User)).scalars().first() is not None
