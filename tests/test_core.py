import pytest
import requests
from unittest.mock import patch, MagicMock
from agent.core import UyuniAIAgent


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


@patch("agent.core.execute_mgrctl_inspection", return_value="Mocked State")
@patch("agent.core.fetch_node_load", return_value=3.0)
def test_run_check_cycle_triggers_alert(mock_fetch, mock_exec, agent):
    # Load is 3.0, threshold is 2.0 -> should trigger alert and execution.
    # No LLM key on this agent, so analyze_with_llm returns raw output (no mock needed).
    triggered = agent.run_check_cycle()

    assert triggered is True
    mock_exec.assert_called_once_with("test-minion")


@patch.object(UyuniAIAgent, "analyze_with_llm", return_value="AI RCA summary")
@patch("agent.core.execute_mgrctl_inspection", return_value="Raw ps output")
@patch("agent.core.fetch_node_load", return_value=3.0)
def test_run_check_cycle_calls_llm_analysis(mock_fetch, mock_exec, mock_analyze, agent_with_llm):
    # When load exceeds threshold, analyze_with_llm must be called with the inspection output.
    triggered = agent_with_llm.run_check_cycle()

    assert triggered is True
    mock_analyze.assert_called_once_with("Raw ps output", scenario="high_cpu")
