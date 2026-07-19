"""Tests for app.services.auth."""
import pytest

from app.models.base import make_session_factory
from app.services.auth import create_user, authenticate, any_user_exists


@pytest.fixture
def session():
    Session = make_session_factory(":memory:")
    s = Session()
    yield s
    s.close()


def test_no_user_exists_initially(session):
    assert any_user_exists(session) is False


def test_create_user_then_exists(session):
    create_user(session, "jayram.owner", "secret123")
    assert any_user_exists(session) is True


def test_password_is_hashed_not_plaintext(session):
    user = create_user(session, "jayram.owner", "secret123")
    assert user.password_hash != "secret123"
    assert user.password_hash.startswith("$2b$")  # bcrypt hash prefix


def test_authenticate_with_correct_password(session):
    create_user(session, "jayram.owner", "secret123")
    user = authenticate(session, "jayram.owner", "secret123")
    assert user.username == "jayram.owner"
    assert user.last_login is not None


def test_authenticate_rejects_wrong_password(session):
    create_user(session, "jayram.owner", "secret123")
    with pytest.raises(ValueError, match="Invalid username or password"):
        authenticate(session, "jayram.owner", "wrongpass")


def test_authenticate_rejects_unknown_username(session):
    with pytest.raises(ValueError, match="Invalid username or password"):
        authenticate(session, "nobody", "whatever")


def test_error_message_identical_for_bad_username_vs_bad_password(session):
    # Security property: don't leak which part was wrong.
    create_user(session, "jayram.owner", "secret123")
    try:
        authenticate(session, "jayram.owner", "wrongpass")
        assert False, "should have raised"
    except ValueError as e1:
        msg1 = str(e1)
    try:
        authenticate(session, "nobody", "whatever")
        assert False, "should have raised"
    except ValueError as e2:
        msg2 = str(e2)
    assert msg1 == msg2


def test_create_user_rejects_duplicate_username(session):
    create_user(session, "jayram.owner", "secret123")
    with pytest.raises(ValueError, match="already exists"):
        create_user(session, "jayram.owner", "different123")


def test_create_user_rejects_short_password(session):
    with pytest.raises(ValueError, match="at least 4 characters"):
        create_user(session, "jayram.owner", "abc")
