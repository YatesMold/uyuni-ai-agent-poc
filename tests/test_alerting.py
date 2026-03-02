"""Tests for agent.alerting — AlertManager integration."""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from agent.alerting import build_alert, send_to_alertmanager
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
        severity="critical",
    )


@pytest.fixture
def sample_rca():
    return "Root cause: salt-minion process consuming 95% CPU due to authentication loop."


# ---------------------------------------------------------------------------
# TestBuildAlert
# ---------------------------------------------------------------------------


class TestBuildAlert:

    def test_build_alert_labels(self, sample_anomaly, sample_rca):
        alert = build_alert(sample_anomaly, sample_rca)
        labels = alert["labels"]

        assert labels["alertname"] == "cpu_threshold_breach"
        assert labels["severity"] == "critical"
        assert labels["source"] == "uyuni-ai-agent"
        assert labels["minion"] == "test-minion"
        assert labels["metric"] == "cpu"

    def test_build_alert_annotations(self, sample_anomaly, sample_rca):
        alert = build_alert(sample_anomaly, sample_rca)
        annotations = alert["annotations"]

        assert annotations["summary"] == "High cpu on test-minion"
        assert annotations["description"] == sample_rca

    def test_build_alert_has_starts_at(self, sample_anomaly, sample_rca):
        alert = build_alert(sample_anomaly, sample_rca)

        assert "startsAt" in alert
        assert isinstance(alert["startsAt"], str)
        assert len(alert["startsAt"]) > 0

    def test_build_alert_alertname_format(self, sample_rca):
        """alertname must be <metric_name>_threshold_breach for any metric."""
        anomaly = Anomaly(
            minion_id="srv1",
            metric_name="apache_workers",
            current_value=180.0,
            threshold=150.0,
            scenario="high_apache_load",
            severity="warning",
        )
        alert = build_alert(anomaly, sample_rca)
        assert alert["labels"]["alertname"] == "apache_workers_threshold_breach"


# ---------------------------------------------------------------------------
# TestSendToAlertmanager
# ---------------------------------------------------------------------------


class TestSendToAlertmanager:

    def _ok_response(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        return resp

    def _error_response(self, status_code=500):
        resp = MagicMock()
        resp.status_code = status_code
        resp.raise_for_status.side_effect = requests_lib.exceptions.HTTPError(
            f"{status_code} Server Error"
        )
        return resp

    @patch("agent.alerting.requests.post")
    def test_send_success(self, mock_post, sample_anomaly, sample_rca):
        """On HTTP 200, POST is called with correct URL, payload, and timeout; returns True."""
        mock_post.return_value = self._ok_response()
        alert = build_alert(sample_anomaly, sample_rca)

        result = send_to_alertmanager("http://localhost:9093", [alert])

        assert result is True
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "http://localhost:9093/api/v1/alerts"
        assert mock_post.call_args[1]["json"] == [alert]
        assert mock_post.call_args[1]["timeout"] == 10

    @patch("agent.alerting.requests.post")
    def test_send_success_logs_info(self, mock_post, sample_anomaly, sample_rca, caplog):
        """On success an INFO-level message is emitted."""
        mock_post.return_value = self._ok_response()
        alert = build_alert(sample_anomaly, sample_rca)

        with caplog.at_level(logging.INFO):
            send_to_alertmanager("http://localhost:9093", [alert])

        assert any("Successfully sent" in r.getMessage() for r in caplog.records)

    @patch("agent.alerting.requests.post")
    def test_send_unreachable(self, mock_post, sample_anomaly, sample_rca, caplog):
        """On ConnectionError: logs a warning, returns False, does not raise."""
        mock_post.side_effect = requests_lib.exceptions.ConnectionError("Connection refused")
        alert = build_alert(sample_anomaly, sample_rca)

        with caplog.at_level(logging.WARNING):
            result = send_to_alertmanager("http://localhost:9093", [alert])

        assert result is False
        assert any("Failed to send" in r.getMessage() for r in caplog.records)

    @patch("agent.alerting.requests.post")
    def test_send_http_error(self, mock_post, sample_anomaly, sample_rca, caplog):
        """On HTTP 500: raise_for_status raises, logs a warning, returns False."""
        mock_post.return_value = self._error_response(500)
        alert = build_alert(sample_anomaly, sample_rca)

        with caplog.at_level(logging.WARNING):
            result = send_to_alertmanager("http://localhost:9093", [alert])

        assert result is False
        assert any("Failed to send" in r.getMessage() for r in caplog.records)

    @patch("agent.alerting.requests.post")
    def test_send_url_no_double_slash(self, mock_post, sample_anomaly, sample_rca):
        """Trailing slash on base URL must not produce a double slash in the final URL."""
        mock_post.return_value = self._ok_response()
        alert = build_alert(sample_anomaly, sample_rca)

        send_to_alertmanager("http://localhost:9093/", [alert])

        called_url = mock_post.call_args[0][0]
        # Strip the scheme before checking for double slashes
        assert "//" not in called_url.replace("http://", "").replace("https://", "")
