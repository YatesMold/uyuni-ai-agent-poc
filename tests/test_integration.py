"""Integration tests: full pipeline from metric evaluation to AlertManager.

Exercises evaluate_metrics → run_investigation → build_alert → send_to_alertmanager
with every external call (Prometheus, Gemini REST, AlertManager HTTP) mocked.
No live servers required.
"""

from unittest.mock import MagicMock, patch

from agent.alerting import build_alert, send_to_alertmanager
from agent.ai_agent import run_investigation
from agent.evaluator import MetricThreshold, evaluate_metrics

_RCA_TEXT = (
    "ROOT CAUSE ANALYSIS\n"
    "RESPONSIBLE PROCESS: salt-minion\n"
    "REMEDIATION STEPS: Restart the salt-minion service."
)


def _gemini_text_response(text: str) -> MagicMock:
    """Return a mock requests.Response carrying a Gemini text-only reply."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    }
    return resp


def _alertmanager_ok_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    return resp


def _cpu_threshold(value: float) -> list:
    """Return a single-metric threshold list using a mock fetch returning *value*."""
    return [
        MetricThreshold(
            metric_name="cpu",
            fetch_fn=MagicMock(return_value=value),
            default_threshold=90.0,
            scenario="high_cpu",
        )
    ]


class TestFullPipeline:

    def test_anomaly_detected_and_alerted(self):
        """CPU breach triggers investigation and a successful AlertManager POST."""
        thresholds = _cpu_threshold(95.0)

        with (
            patch("agent.ai_agent.requests.post", return_value=_gemini_text_response(_RCA_TEXT)),
            patch("agent.alerting.requests.post", return_value=_alertmanager_ok_response()),
        ):
            # Stage 1: metric evaluation
            anomalies = evaluate_metrics("http://prometheus:9090", "test-minion.suse.de", thresholds)
            assert len(anomalies) == 1
            anomaly = anomalies[0]
            assert anomaly.metric_name == "cpu"
            assert anomaly.current_value == 95.0
            assert anomaly.threshold == 90.0
            assert anomaly.severity in ("alert", "warning", "critical")

            # Stage 2: agentic investigation
            rca = run_investigation(anomaly, api_key="fake-key-for-test")
            assert isinstance(rca, str)
            assert len(rca) > 0

            # Stage 3: build alert
            alert = build_alert(anomaly, rca)
            assert alert["labels"]["alertname"] == "cpu_threshold_breach"
            assert alert["labels"]["severity"] == anomaly.severity
            assert alert["annotations"]["description"] == rca

            # Stage 4: send to AlertManager
            result = send_to_alertmanager("http://alertmanager:9093", [alert])
            assert result is True

    def test_no_anomaly_skips_pipeline(self):
        """When no metric breaches its threshold, evaluate_metrics returns an empty list."""
        thresholds = _cpu_threshold(50.0)

        anomalies = evaluate_metrics("http://prometheus:9090", "test-minion.suse.de", thresholds)
        assert anomalies == []

    def test_no_api_key_falls_back_to_raw_output(self):
        """Without an API key, run_investigation returns the raw mgrctl output."""
        thresholds = _cpu_threshold(95.0)

        with patch(
            "agent.ai_agent.tools.execute_mgrctl_inspection",
            return_value="raw ps output from minion",
        ):
            anomalies = evaluate_metrics("http://prometheus:9090", "test-minion.suse.de", thresholds)
            assert len(anomalies) == 1

            rca = run_investigation(anomalies[0], api_key="")
            assert rca == "raw ps output from minion"
