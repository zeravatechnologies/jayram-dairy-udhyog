"""User — local login accounts. Single/few users expected (the owner,
maybe one staff member later) — no external auth provider needed.
"""
from sqlalchemy import Column, Integer, String, DateTime

from app.models.base import Base


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.user_id} {self.username}>"
