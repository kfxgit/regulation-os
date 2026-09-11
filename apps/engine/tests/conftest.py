import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import engine


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
