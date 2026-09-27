import pytest

from app.services.ingestion_service import DepletionEngine
from app.workers.tasks import _predict


def test_depletion_engine_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        DepletionEngine.calculate_time_to_empty(100, 90, 0)


def test_depletion_engine_returns_remaining_minutes():
    assert DepletionEngine.calculate_time_to_empty(100, 80, 10) == 40


def test_worker_predicts_linear_drop():
    remaining, confidence = _predict([(100.0, 1000), (90.0, 1060)])
    assert remaining == 9.0
    assert confidence > 0


def test_worker_marks_stable_pressure():
    remaining, confidence = _predict([(100.0, 1000), (100.0, 1060)])
    assert remaining is None
    assert confidence > 0
