"""Tests for agent.evaluator — threshold evaluation engine."""

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from agent.evaluator import (
    DEFAULT_THRESHOLDS,
    Anomaly,
    MetricThreshold,
    _compute_severity,
    evaluate_metrics,
)


# --- _compute_severity ---


def test_severity_alert():
    assert _compute_severity(91.0, 90.0) == "alert"


def test_severity_warning():
    assert _compute_severity(108.0, 90.0) == "warning"


def test_severity_critical():
    assert _compute_severity(135.0, 90.0) == "critical"


# --- Dataclass basics ---


def test_metric_threshold_is_frozen():
    mt = MetricThreshold(
        metric_name="cpu",
        fetch_fn=lambda u, m: 0.0,
        default_threshold=90.0,
        scenario="high_cpu",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        mt.metric_name = "changed"


def test_anomaly_fields():
    a = Anomaly(
        minion_id="m1",
        metric_name="cpu",
        current_value=95.0,
        threshold=90.0,
        scenario="high_cpu",
        severity="alert",
    )
    assert a.minion_id == "m1"
    assert a.current_value == 95.0
    assert a.severity == "alert"


# --- DEFAULT_THRESHOLDS ---


def test_default_thresholds_has_six_entries():
    assert len(DEFAULT_THRESHOLDS) == 6
    names = {mt.metric_name for mt in DEFAULT_THRESHOLDS}
    assert names == {"cpu", "memory", "disk", "load", "apache_workers", "postgres_connections"}


# --- evaluate_metrics ---


def test_evaluate_metrics_detects_breach():
    mock_fetch = MagicMock(return_value=95.0)
    thresholds = [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=mock_fetch,
            default_threshold=90.0,
            scenario="high_cpu",
        )
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", thresholds)

    assert len(anomalies) == 1
    a = anomalies[0]
    assert a.minion_id == "test-minion"
    assert a.metric_name == "cpu"
    assert a.current_value == 95.0
    assert a.threshold == 90.0
    assert a.scenario == "high_cpu"
    assert a.severity == "alert"
    mock_fetch.assert_called_once_with("http://mock:9090", "test-minion")


def test_evaluate_metrics_no_breach():
    mock_fetch = MagicMock(return_value=80.0)
    thresholds = [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=mock_fetch,
            default_threshold=90.0,
            scenario="high_cpu",
        )
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", thresholds)

    assert len(anomalies) == 0


def test_evaluate_metrics_skips_none():
    mock_fetch = MagicMock(return_value=None)
    thresholds = [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=mock_fetch,
            default_threshold=90.0,
            scenario="high_cpu",
        )
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", thresholds)

    assert len(anomalies) == 0


def test_evaluate_metrics_multiple_anomalies():
    thresholds = [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=MagicMock(return_value=95.0),
            default_threshold=90.0,
            scenario="high_cpu",
        ),
        MetricThreshold(
            metric_name="memory",
            fetch_fn=MagicMock(return_value=90.0),
            default_threshold=85.0,
            scenario="high_memory",
        ),
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", thresholds)

    assert len(anomalies) == 2
    assert anomalies[0].metric_name == "cpu"
    assert anomalies[1].metric_name == "memory"


def test_evaluate_metrics_uses_default_thresholds():
    mocks = {mt.metric_name: MagicMock(return_value=0.0) for mt in DEFAULT_THRESHOLDS}
    patched = [
        MetricThreshold(
            metric_name=mt.metric_name,
            fetch_fn=mocks[mt.metric_name],
            default_threshold=mt.default_threshold,
            scenario=mt.scenario,
        )
        for mt in DEFAULT_THRESHOLDS
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", patched)

    assert len(anomalies) == 0
    for name, mock_fn in mocks.items():
        mock_fn.assert_called_once_with("http://mock:9090", "test-minion")


# --- Env var overrides ---


def test_env_var_override_lowers_threshold(monkeypatch):
    monkeypatch.setenv("THRESHOLD_CPU", "50")
    mock_fetch = MagicMock(return_value=60.0)
    thresholds = [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=mock_fetch,
            default_threshold=90.0,
            scenario="high_cpu",
        )
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", thresholds)

    assert len(anomalies) == 1
    assert anomalies[0].threshold == 50.0
    assert anomalies[0].severity == "warning"  # 60/50 = 1.2


def test_env_var_override_raises_threshold(monkeypatch):
    monkeypatch.setenv("THRESHOLD_CPU", "99")
    mock_fetch = MagicMock(return_value=91.0)
    thresholds = [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=mock_fetch,
            default_threshold=90.0,
            scenario="high_cpu",
        )
    ]

    anomalies = evaluate_metrics("http://mock:9090", "test-minion", thresholds)

    assert len(anomalies) == 0
