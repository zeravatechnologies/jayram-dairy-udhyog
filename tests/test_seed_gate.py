"""Seed must not run for packaged builds; source builds may seed."""
import sys
from unittest.mock import patch

from sqlalchemy import select

from app.models import Vendor
from app.models.base import make_session_factory
from app.services.seed import seed_demo_data, should_seed_demo_data


def test_seed_demo_data_inserts_when_empty():
    Session = make_session_factory(":memory:")
    seed_demo_data(Session)
    session = Session()
    vendors = list(session.execute(select(Vendor)).scalars())
    session.close()
    assert len(vendors) >= 2
    assert any(v.name == "Hari Thapa" for v in vendors)


def test_should_seed_false_when_frozen():
    with patch.object(sys, "frozen", True, create=True):
        assert should_seed_demo_data() is False


def test_should_seed_true_when_not_frozen():
    with patch.object(sys, "frozen", False, create=True):
        assert should_seed_demo_data() is True
