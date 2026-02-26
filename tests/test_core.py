import pytest
import requests
from unittest.mock import patch, MagicMock
from agent.core import UyuniAIAgent

@pytest.fixture
def agent():
    return UyuniAIAgent("http://mock-prometheus:9090", "test-minion", 2.0)

@patch("agent.core.requests.get")
def test_fetch_node_load_success(mock_get, agent):
    # Mocking a successful Prometheus response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {"result": [{"value": [167890, "2.5"]}]}
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    load = agent.fetch_node_load()
    assert load == 2.5
    mock_get.assert_called_once()

@patch("agent.core.requests.get")
def test_fetch_node_load_failure(mock_get, agent):
    # Mocking a network failure with the correct exception type
    mock_get.side_effect = requests.exceptions.RequestException("Network Error")
    load = agent.fetch_node_load()
    assert load is None

@patch("agent.core.subprocess.run")
def test_execute_mgrctl_inspection_success(mock_run, agent):
    # Mocking successful mgrctl execution
    mock_result = MagicMock()
    mock_result.stdout = "PID CMD %CPU\n123 python 99.9"
    mock_run.return_value = mock_result

    output = agent.execute_mgrctl_inspection()
    assert "99.9" in output
    mock_run.assert_called_once()

@patch.object(UyuniAIAgent, "fetch_node_load")
@patch.object(UyuniAIAgent, "execute_mgrctl_inspection")
def test_run_check_cycle_triggers_alert(mock_exec, mock_fetch, agent):
    # Load is 3.0, threshold is 2.0 -> should trigger alert and execution
    mock_fetch.return_value = 3.0
    mock_exec.return_value = "Mocked State"
    
    triggered = agent.run_check_cycle()
    
    assert triggered is True
    mock_exec.assert_called_once()
