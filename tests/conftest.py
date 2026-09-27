import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DB_PATH = Path("/tmp/oxygen-pred-tests.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{DB_PATH}")
os.environ.setdefault("REQUIRE_INGEST_AUTH", "true")
os.environ.setdefault("INGEST_API_KEY", "test-key")
os.environ.setdefault("DEBUG", "false")

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def device_headers():
    return {"X-Device-Key": "test-key"}
