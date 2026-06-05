"""Pytest configuration and fixtures for E.sapiens backend tests.

No mocks, no fakes, no monkeypatching. Tests exercise pure logic only.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


@pytest.fixture(autouse=True)
def _setup_db():
    """Initialize the database before each test session.

    TestClient does not trigger FastAPI's on_event('startup'),
    so we call init_db() explicitly to create all tables.
    """
    init_db()
    yield


@pytest.fixture
def client():
    """FastAPI TestClient fixture pointing to app.main:app."""
    with TestClient(app) as c:
        yield c
