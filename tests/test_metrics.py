import requests
from unittest.mock import patch, MagicMock

from agent.metrics import (
    fetch_node_load,
    fetch_memory_usage_percent,
    fetch_cpu_usage_percent,
    fetch_disk_usage_percent,
)

PROMETHEUS_URL = "http://mock-prometheus:9090"
MINION_ID = "test-minion"


def _mock_success(value: str = "42.5") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "data": {"result": [{"value": [1700000000, value]}]}
    }
    resp.raise_for_status.return_value = None
    return resp


def _mock_empty() -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": {"result": []}}
    resp.raise_for_status.return_value = None
    return resp


# ── fetch_node_load ──────────────────────────────────────────────────────

@patch("agent.metrics.requests.get")
def test_fetch_node_load_happy_path(mock_get):
    mock_get.return_value = _mock_success()
    result = fetch_node_load(PROMETHEUS_URL, MINION_ID)
    assert result == 42.5
    assert isinstance(result, float)


@patch("agent.metrics.requests.get")
def test_fetch_node_load_empty_result(mock_get):
    mock_get.return_value = _mock_empty()
    result = fetch_node_load(PROMETHEUS_URL, MINION_ID)
    assert result is None


@patch("agent.metrics.requests.get")
def test_fetch_node_load_network_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("refused")
    result = fetch_node_load(PROMETHEUS_URL, MINION_ID)
    assert result is None


# ── fetch_memory_usage_percent ───────────────────────────────────────────

@patch("agent.metrics.requests.get")
def test_fetch_memory_usage_percent_happy_path(mock_get):
    mock_get.return_value = _mock_success()
    result = fetch_memory_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result == 42.5
    assert isinstance(result, float)


@patch("agent.metrics.requests.get")
def test_fetch_memory_usage_percent_empty_result(mock_get):
    mock_get.return_value = _mock_empty()
    result = fetch_memory_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result is None


@patch("agent.metrics.requests.get")
def test_fetch_memory_usage_percent_network_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("refused")
    result = fetch_memory_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result is None


# ── fetch_cpu_usage_percent ──────────────────────────────────────────────

@patch("agent.metrics.requests.get")
def test_fetch_cpu_usage_percent_happy_path(mock_get):
    mock_get.return_value = _mock_success()
    result = fetch_cpu_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result == 42.5
    assert isinstance(result, float)


@patch("agent.metrics.requests.get")
def test_fetch_cpu_usage_percent_empty_result(mock_get):
    mock_get.return_value = _mock_empty()
    result = fetch_cpu_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result is None


@patch("agent.metrics.requests.get")
def test_fetch_cpu_usage_percent_network_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("refused")
    result = fetch_cpu_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result is None


# ── fetch_disk_usage_percent ─────────────────────────────────────────────

@patch("agent.metrics.requests.get")
def test_fetch_disk_usage_percent_happy_path(mock_get):
    mock_get.return_value = _mock_success()
    result = fetch_disk_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result == 42.5
    assert isinstance(result, float)


@patch("agent.metrics.requests.get")
def test_fetch_disk_usage_percent_empty_result(mock_get):
    mock_get.return_value = _mock_empty()
    result = fetch_disk_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result is None


@patch("agent.metrics.requests.get")
def test_fetch_disk_usage_percent_network_failure(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("refused")
    result = fetch_disk_usage_percent(PROMETHEUS_URL, MINION_ID)
    assert result is None
