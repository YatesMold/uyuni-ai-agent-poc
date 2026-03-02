import pytest
import requests
from unittest.mock import patch, MagicMock
from agent.core import UyuniAIAgent
from agent.evaluator import Anomaly


@pytest.fixture
def agent():
    return UyuniAIAgent("http://mock-prometheus:9090", "test-minion", 2.0)


@pytest.fixture
def agent_with_llm():
    return UyuniAIAgent("http://mock-prometheus:9090", "test-minion", 2.0, llm_api_key="fake-key")


# --- analyze_with_llm ---


@patch("agent.core.requests.post")
def test_analyze_with_llm_returns_rca(mock_post, agent_with_llm):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Root Cause: Python process (PID 123) consuming 99% CPU."}]}}]
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = agent_with_llm.analyze_with_llm("PID CMD %CPU\n123 python 99.9")

    assert "Root Cause" in result
    mock_post.assert_called_once()


def test_analyze_with_llm_skipped_without_key(agent):
    # Without an API key, the raw output must be returned unchanged.
    raw = "PID CMD %CPU\n123 python 99.9"
    result = agent.analyze_with_llm(raw)
    assert result == raw


@patch("agent.core.requests.post")
def test_analyze_with_llm_falls_back_on_api_error(mock_post, agent_with_llm):
    # If the Gemini API raises an exception, raw output is returned unchanged.
    mock_post.side_effect = requests.exceptions.RequestException("API quota exceeded")

    raw = "PID CMD %CPU\n123 python 99.9"
    result = agent_with_llm.analyze_with_llm(raw)
    assert result == raw


# --- run_check_cycle ---


@patch("agent.core.run_investigation", return_value="Mocked RCA")
@patch("agent.core.evaluate_metrics", return_value=[
    Anomaly(minion_id="test-minion", metric_name="load", current_value=3.0,
            threshold=2.0, scenario="high_cpu", severity="warning")
])
def test_run_check_cycle_triggers_alert(mock_evaluate, mock_investigate, agent):
    # evaluate_metrics returns one anomaly -> run_check_cycle should return it.
    anomaly, rca = agent.run_check_cycle()

    assert anomaly is not None
    assert rca == "Mocked RCA"
    mock_evaluate.assert_called_once_with(agent.prometheus_url, agent.minion_id)
    mock_investigate.assert_called_once()


@patch("agent.core.run_investigation", return_value="AI RCA summary")
@patch("agent.core.evaluate_metrics", return_value=[
    Anomaly(minion_id="test-minion", metric_name="load", current_value=3.0,
            threshold=2.0, scenario="high_cpu", severity="warning")
])
def test_run_check_cycle_calls_llm_analysis(mock_evaluate, mock_investigate, agent_with_llm):
    # run_investigation is called with the anomaly and the agent's API key.
    anomaly, rca = agent_with_llm.run_check_cycle()

    assert anomaly is not None
    assert rca == "AI RCA summary"
    mock_investigate.assert_called_once_with(anomaly, agent_with_llm._llm_api_key)
