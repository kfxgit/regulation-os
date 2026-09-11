import os

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import engine

# Tests that call the real Anthropic API (cost money, need network, can be
# slow/flaky). Skipped by default; run with RUN_LIVE_API_TESTS=1 set.
live_api = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_API_TESTS") != "1",
    reason="live API test skipped by default (set RUN_LIVE_API_TESTS=1 to run)",
)


@pytest.fixture()
def db_session():
    """A session bound to one connection + one outer transaction.
    session.commit() inside a test only releases a SAVEPOINT; the outer
    transaction is rolled back at the end, so tests never leave data
    behind in the real database."""
    connection = engine.connect()
    outer_transaction = connection.begin()

    TestSession = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint"
    )
    session: Session = TestSession()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
