import pytest
from src.decision_engine.layer2_decision.pillar2_ml.anomaly_detector import AnomalyDetector

@pytest.fixture
def detector():
    return AnomalyDetector()

def test_normal_signals_return_low_anomaly_score(detector):
    signals = {
        "cac_vs_baseline_ratio": 1.05,
        "roas_7d": 2.4,
        "overdue_ratio": 1.25,
    }
    result = detector.detect(signals)
    assert result["anomaly_score"] < 0.3
    assert result["anomalous_signals"] == []

def test_extreme_signal_flagged_as_anomalous(detector):
    signals = {
        "cac_vs_baseline_ratio": 2.50,  # 10 std devs above mean
        "roas_7d": 2.5,
    }
    result = detector.detect(signals)
    assert "cac_vs_baseline_ratio" in result["anomalous_signals"]
    assert result["anomaly_score"] > 0.0

def test_unknown_signals_do_not_crash(detector):
    signals = {
        "unknown_metric_xyz": 999.0,
        "cac_vs_baseline_ratio": 1.0,
    }
    result = detector.detect(signals)
    assert "anomaly_score" in result
    assert result["signal_confidence"] < 1.0

def test_empty_signals_return_zero_anomaly(detector):
    result = detector.detect({})
    assert result["anomaly_score"] == 0.0
    assert result["anomalous_signals"] == []

def test_import_dimension_state_from_contracts():
    from src.decision_engine.contracts import DimensionState
    assert DimensionState.CRITICAL == "CRITICAL"
    assert DimensionState.HEALTHY == "HEALTHY"
