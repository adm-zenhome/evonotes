import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_app_imports():
    """Regressão: bec5a39 removeu um símbolo importado pelo app e quebrou o boot."""
    from dashboard.app import app

    assert app is not None
