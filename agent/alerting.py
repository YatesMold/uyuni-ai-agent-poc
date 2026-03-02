"""AlertManager integration for the Uyuni AI Agent.

Provides two public functions:
  - build_alert(anomaly, rca_summary) -> dict
  - send_to_alertmanager(alertmanager_url, alerts) -> bool

The ALERTMANAGER_ENABLED guard lives in main.py; this module always acts
when called and has no knowledge of that flag.
"""

import logging
from datetime import datetime, timezone

import requests

from agent.evaluator import Anomaly

logger = logging.getLogger(__name__)


def build_alert(anomaly: Anomaly, rca_summary: str) -> dict:
    """Build an AlertManager-compatible alert dict from an Anomaly and RCA text.

    The /api/v1/alerts endpoint expects a JSON array of these dicts.
    Wrap the return value in a list before passing to send_to_alertmanager().
    """
    return {
        "labels": {
            "alertname": f"{anomaly.metric_name}_threshold_breach",
            "severity": anomaly.severity,
            "source": "uyuni-ai-agent",
            "minion": anomaly.minion_id,
            "metric": anomaly.metric_name,
        },
        "annotations": {
            "summary": f"High {anomaly.metric_name} on {anomaly.minion_id}",
            "description": rca_summary,
        },
        "startsAt": datetime.now(timezone.utc).isoformat(),
    }


def send_to_alertmanager(alertmanager_url: str, alerts: list) -> bool:
    """POST a list of alert dicts to AlertManager /api/v1/alerts.

    Returns True on HTTP 2xx, False on any connection or HTTP error.
    Never raises — the monitoring loop must not be interrupted by alerting failures.

    Args:
        alertmanager_url: Base URL of AlertManager, e.g. "http://localhost:9093".
        alerts: A list of alert dicts, each built with build_alert().
    """
    url = f"{alertmanager_url.rstrip('/')}/api/v1/alerts"
    try:
        response = requests.post(url, json=alerts, timeout=10)
        response.raise_for_status()
        logger.info(
            "Successfully sent %d alert(s) to AlertManager at %s",
            len(alerts),
            url,
        )
        return True
    except Exception as e:
        logger.warning(
            "Failed to send alerts to AlertManager at %s: %s",
            url,
            e,
        )
        return False
