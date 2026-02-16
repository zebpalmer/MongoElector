import mongomock
import pytest


@pytest.fixture
def db():
    """Provide a mongomock database for testing."""
    client = mongomock.MongoClient()
    database = client["ml_unittest"]
    yield database
    client.close()
