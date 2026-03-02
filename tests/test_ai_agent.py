"""Tests for the agentic tool-use investigation loop (agent/ai_agent.py)."""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from agent.ai_agent import (
    TOOL_REGISTRY,
    _MAX_TOOL_ROUNDS,
    _build_function_declarations,
    _execute_tool,
    run_investigation,
)
from agent.evaluator import Anomaly


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_anomaly():
    return Anomaly(
        minion_id="test-minion",
        metric_name="cpu",
        current_value=95.0,
        threshold=90.0,
        scenario="high_cpu",
        severity="alert",
    )


@pytest.fixture
def apache_anomaly():
    return Anomaly(
        minion_id="test-minion",
        metric_name="apache_workers",
        current_value=180.0,
        threshold=150.0,
        scenario="high_apache_load",
        severity="warning",
    )


# ---------------------------------------------------------------------------
# Mock Gemini response helpers
# ---------------------------------------------------------------------------


def _gemini_function_call_response(name, args=None):
    """Build a mock Gemini response containing a single functionCall."""
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"functionCall": {"name": name, "args": args or {}}}
                    ]
                }
            }
        ]
    }


def _gemini_text_response(text):
    """Build a mock Gemini response containing a text answer."""
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _gemini_multi_call_response(calls):
    """Build a mock Gemini response with multiple functionCall parts.

    *calls* is a list of (name, args) tuples.
    """
    parts = [
        {"functionCall": {"name": name, "args": args or {}}}
        for name, args in calls
    ]
    return {"candidates": [{"content": {"parts": parts}}]}


def _mock_gemini_response(json_data):
    """Create a MagicMock that behaves like a requests.Response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# TOOL_REGISTRY tests
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_contains_all_eight_tools(self):
        expected = {
            "execute_mgrctl_inspection",
            "get_top_cpu_processes",
            "get_top_memory_processes",
            "get_disk_usage_breakdown",
            "get_running_services",
            "get_service_logs",
            "get_apache_error_log",
            "get_postgres_slow_queries",
        }
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_entries_have_required_keys(self):
        for name, entry in TOOL_REGISTRY.items():
            assert entry["name"] == name
            assert "description" in entry
            assert "parameters" in entry

    def test_only_get_service_logs_has_required_params(self):
        for name, entry in TOOL_REGISTRY.items():
            params = entry["parameters"]
            if name == "get_service_logs":
                assert "required" in params
                assert "service_name" in params["properties"]
            else:
                assert not params.get("properties")


class TestBuildFunctionDeclarations:
    def test_returns_eight_declarations(self):
        decls = _build_function_declarations()
        assert len(decls) == 8

    def test_declaration_names_match_registry(self):
        decls = _build_function_declarations()
        names = {d["name"] for d in decls}
        assert names == set(TOOL_REGISTRY.keys())


# ---------------------------------------------------------------------------
# _execute_tool tests
# ---------------------------------------------------------------------------


class TestExecuteTool:
    @patch(
        "agent.ai_agent.tools.get_top_cpu_processes",
        return_value="PID CPU\n123 99.9",
    )
    def test_injects_minion_id(self, mock_fn):
        result = _execute_tool("get_top_cpu_processes", {}, "test-minion")
        assert "99.9" in result
        mock_fn.assert_called_once_with("test-minion")

    @patch(
        "agent.ai_agent.tools.get_service_logs",
        return_value="journal output",
    )
    def test_passes_extra_args(self, mock_fn):
        result = _execute_tool(
            "get_service_logs",
            {"service_name": "sshd.service"},
            "test-minion",
        )
        assert result == "journal output"
        mock_fn.assert_called_once_with(
            "test-minion", service_name="sshd.service"
        )

    def test_unknown_tool(self):
        result = _execute_tool("nonexistent_tool", {}, "test-minion")
        assert "ERROR" in result
        assert "Unknown tool" in result

    @patch(
        "agent.ai_agent.tools.get_service_logs",
        side_effect=ValueError("Invalid service name"),
    )
    def test_catches_exception(self, mock_fn):
        result = _execute_tool(
            "get_service_logs",
            {"service_name": "bad;name"},
            "test-minion",
        )
        assert "ERROR" in result
        assert "ValueError" in result


# ---------------------------------------------------------------------------
# run_investigation tests
# ---------------------------------------------------------------------------


class TestRunInvestigation:
    """Tests for the main agentic loop."""

    @patch("agent.ai_agent.requests.post")
    def test_direct_text_response(self, mock_post, sample_anomaly):
        """Gemini returns text immediately without calling any tools."""
        mock_post.return_value = _mock_gemini_response(
            _gemini_text_response("Root Cause: salt-minion PID 1842")
        )

        result = run_investigation(sample_anomaly, "fake-key")

        assert "Root Cause" in result
        mock_post.assert_called_once()

    @patch(
        "agent.ai_agent.tools.get_top_cpu_processes",
        return_value="PID CMD %CPU\n1842 salt 95.4",
    )
    @patch("agent.ai_agent.requests.post")
    def test_one_tool_call_then_text(
        self, mock_post, mock_tool, sample_anomaly
    ):
        """Gemini calls one tool, then returns text RCA."""
        mock_post.side_effect = [
            _mock_gemini_response(
                _gemini_function_call_response("get_top_cpu_processes")
            ),
            _mock_gemini_response(
                _gemini_text_response("RCA: salt-minion is the root cause")
            ),
        ]

        result = run_investigation(sample_anomaly, "fake-key")

        assert "salt-minion" in result
        assert mock_post.call_count == 2
        mock_tool.assert_called_once_with("test-minion")

    @patch(
        "agent.ai_agent.tools.get_service_logs",
        return_value="salt-minion log output",
    )
    @patch(
        "agent.ai_agent.tools.get_top_cpu_processes",
        return_value="PID CPU\n1842 salt 95.4",
    )
    @patch("agent.ai_agent.requests.post")
    def test_multi_round(
        self, mock_post, mock_cpu, mock_logs, sample_anomaly
    ):
        """Gemini calls two tools across two rounds, then returns text."""
        mock_post.side_effect = [
            _mock_gemini_response(
                _gemini_function_call_response("get_top_cpu_processes")
            ),
            _mock_gemini_response(
                _gemini_function_call_response(
                    "get_service_logs",
                    {"service_name": "salt-minion.service"},
                )
            ),
            _mock_gemini_response(
                _gemini_text_response("Final RCA: authentication failure")
            ),
        ]

        result = run_investigation(sample_anomaly, "fake-key")

        assert "authentication failure" in result
        assert mock_post.call_count == 3
        mock_cpu.assert_called_once_with("test-minion")
        mock_logs.assert_called_once_with(
            "test-minion", service_name="salt-minion.service"
        )

    @patch(
        "agent.ai_agent.tools.get_running_services",
        return_value="service list",
    )
    @patch(
        "agent.ai_agent.tools.get_apache_error_log",
        return_value="Apache error log content",
    )
    @patch("agent.ai_agent.requests.post")
    def test_parallel_tool_calls(
        self, mock_post, mock_apache, mock_services, apache_anomaly
    ):
        """Gemini requests two tools simultaneously in one response."""
        mock_post.side_effect = [
            _mock_gemini_response(
                _gemini_multi_call_response(
                    [
                        ("get_apache_error_log", {}),
                        ("get_running_services", {}),
                    ]
                )
            ),
            _mock_gemini_response(
                _gemini_text_response("RCA: MaxRequestWorkers exhausted")
            ),
        ]

        result = run_investigation(apache_anomaly, "fake-key")

        assert "MaxRequestWorkers" in result
        assert mock_post.call_count == 2
        mock_apache.assert_called_once_with("test-minion")
        mock_services.assert_called_once_with("test-minion")

    @patch(
        "agent.ai_agent.tools.get_top_cpu_processes",
        return_value="process data",
    )
    @patch("agent.ai_agent.requests.post")
    def test_max_rounds_forces_final_rca(
        self, mock_post, mock_tool, sample_anomaly
    ):
        """After _MAX_TOOL_ROUNDS, sends a final request without tools."""
        fc_resp = _mock_gemini_response(
            _gemini_function_call_response("get_top_cpu_processes")
        )
        final_resp = _mock_gemini_response(
            _gemini_text_response("Forced RCA after max rounds")
        )
        mock_post.side_effect = [fc_resp] * _MAX_TOOL_ROUNDS + [final_resp]

        result = run_investigation(sample_anomaly, "fake-key")

        assert "Forced RCA" in result
        assert mock_post.call_count == _MAX_TOOL_ROUNDS + 1

    @patch(
        "agent.ai_agent.tools.get_top_cpu_processes",
        return_value="process data",
    )
    @patch("agent.ai_agent.requests.post")
    def test_max_rounds_final_request_has_no_tools(
        self, mock_post, mock_tool, sample_anomaly
    ):
        """The forced final request should NOT include the tools parameter."""
        fc_resp = _mock_gemini_response(
            _gemini_function_call_response("get_top_cpu_processes")
        )
        final_resp = _mock_gemini_response(
            _gemini_text_response("Forced RCA")
        )
        mock_post.side_effect = [fc_resp] * _MAX_TOOL_ROUNDS + [final_resp]

        run_investigation(sample_anomaly, "fake-key")

        # The last call (forced final) should have no "tools" key in payload
        final_call_payload = mock_post.call_args_list[-1].kwargs.get(
            "json", mock_post.call_args_list[-1][1].get("json", {})
        )
        assert "tools" not in final_call_payload


class TestRunInvestigationFallback:
    """Tests for graceful fallback behavior."""

    @patch(
        "agent.ai_agent.tools.execute_mgrctl_inspection",
        return_value="simulated ps output",
    )
    def test_no_api_key_empty_string(self, mock_inspect, sample_anomaly):
        result = run_investigation(sample_anomaly, "")

        assert result == "simulated ps output"
        mock_inspect.assert_called_once_with("test-minion")

    @patch(
        "agent.ai_agent.tools.execute_mgrctl_inspection",
        return_value="simulated ps output",
    )
    def test_no_api_key_none(self, mock_inspect, sample_anomaly):
        result = run_investigation(sample_anomaly, None)

        assert result == "simulated ps output"
        mock_inspect.assert_called_once_with("test-minion")

    @patch(
        "agent.ai_agent.tools.execute_mgrctl_inspection",
        return_value="fallback output",
    )
    @patch("agent.ai_agent.requests.post")
    def test_api_connection_error(
        self, mock_post, mock_inspect, sample_anomaly
    ):
        mock_post.side_effect = requests_lib.exceptions.ConnectionError(
            "connection refused"
        )

        result = run_investigation(sample_anomaly, "fake-key")

        assert result == "fallback output"
        mock_inspect.assert_called_once_with("test-minion")

    @patch(
        "agent.ai_agent.tools.execute_mgrctl_inspection",
        return_value="fallback output",
    )
    @patch("agent.ai_agent.requests.post")
    def test_malformed_response(
        self, mock_post, mock_inspect, sample_anomaly
    ):
        mock_post.return_value = _mock_gemini_response(
            {"unexpected": "format"}
        )

        result = run_investigation(sample_anomaly, "fake-key")

        assert result == "fallback output"

    @patch(
        "agent.ai_agent.tools.execute_mgrctl_inspection",
        return_value="fallback",
    )
    @patch("agent.ai_agent.requests.post")
    def test_api_key_redacted_in_logs(
        self, mock_post, mock_inspect, sample_anomaly, caplog
    ):
        api_key = "super-secret-key-12345"
        mock_post.side_effect = requests_lib.exceptions.ConnectionError(
            f"Error with {api_key}"
        )

        with caplog.at_level(logging.ERROR):
            run_investigation(sample_anomaly, api_key)

        for record in caplog.records:
            assert api_key not in record.getMessage()


class TestConversationHistory:
    """Tests that the contents array is built correctly."""

    @patch(
        "agent.ai_agent.tools.get_top_cpu_processes",
        return_value="cpu data",
    )
    @patch("agent.ai_agent.requests.post")
    def test_history_grows_after_tool_call(
        self, mock_post, mock_tool, sample_anomaly
    ):
        """After one tool round, the second POST should have 3 content entries."""
        mock_post.side_effect = [
            _mock_gemini_response(
                _gemini_function_call_response("get_top_cpu_processes")
            ),
            _mock_gemini_response(_gemini_text_response("Final RCA")),
        ]

        run_investigation(sample_anomaly, "fake-key")

        second_payload = mock_post.call_args_list[1].kwargs.get(
            "json", mock_post.call_args_list[1][1].get("json", {})
        )
        contents = second_payload["contents"]
        assert len(contents) == 3
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"
        assert contents[2]["role"] == "user"
        assert "functionResponse" in contents[2]["parts"][0]


class TestMissingScenarioTemplate:
    """Tests prompt fallback when the scenario .md file does not exist."""

    @patch("agent.ai_agent.requests.post")
    def test_uses_generic_prompt(self, mock_post):
        anomaly = Anomaly(
            minion_id="test-minion",
            metric_name="unknown_metric",
            current_value=100.0,
            threshold=50.0,
            scenario="nonexistent_scenario",
            severity="critical",
        )
        mock_post.return_value = _mock_gemini_response(
            _gemini_text_response("RCA for unknown metric")
        )

        result = run_investigation(anomaly, "fake-key")

        assert "RCA" in result
        call_payload = mock_post.call_args.kwargs.get(
            "json", mock_post.call_args[1].get("json", {})
        )
        user_text = call_payload["contents"][0]["parts"][0]["text"]
        assert "unknown_metric" in user_text
