import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OPENAI_API_KEY", "")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from asgi import app

    return TestClient(app, raise_server_exceptions=False)
