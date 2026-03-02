"""Threshold-based metric evaluation with per-metric env var overrides."""

import logging
import os
from dataclasses import dataclass
from typing import Callable, List, Optional

from agent.metrics import (
    fetch_apache_workers_busy,
    fetch_cpu_usage_percent,
    fetch_disk_usage_percent,
    fetch_memory_usage_percent,
    fetch_node_load,
    fetch_postgres_active_connections,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricThreshold:
    """Defines a single metric to evaluate against a threshold."""

    metric_name: str
    fetch_fn: Callable[[str, str], Optional[float]]
    default_threshold: float
    scenario: str


@dataclass
class Anomaly:
    """Represents a detected threshold breach for a single metric."""

    minion_id: str
    metric_name: str
    current_value: float
    threshold: float
    scenario: str
    severity: str


def _compute_severity(current_value: float, threshold: float) -> str:
    """Determine severity based on how far the value exceeds the threshold."""
    ratio = current_value / threshold if threshold > 0 else 1.0
    if ratio >= 1.5:
        return "critical"
    if ratio >= 1.2:
        return "warning"
    return "alert"


DEFAULT_THRESHOLDS: List[MetricThreshold] = [
    MetricThreshold(
        metric_name="cpu",
        fetch_fn=fetch_cpu_usage_percent,
        default_threshold=90.0,
        scenario="high_cpu",
    ),
    MetricThreshold(
        metric_name="memory",
        fetch_fn=fetch_memory_usage_percent,
        default_threshold=85.0,
        scenario="high_memory",
    ),
    MetricThreshold(
        metric_name="disk",
        fetch_fn=fetch_disk_usage_percent,
        default_threshold=90.0,
        scenario="disk_full",
    ),
    MetricThreshold(
        metric_name="load",
        fetch_fn=fetch_node_load,
        default_threshold=2.0,
        scenario="high_cpu",  # No dedicated high_load.md yet
    ),
    MetricThreshold(
        metric_name="apache_workers",
        fetch_fn=fetch_apache_workers_busy,
        default_threshold=150.0,
        scenario="high_apache_load",
    ),
    MetricThreshold(
        metric_name="postgres_connections",
        fetch_fn=fetch_postgres_active_connections,
        default_threshold=100.0,
        scenario="postgres_connections",
    ),
]


def evaluate_metrics(
    prometheus_url: str,
    minion_id: str,
    thresholds: List[MetricThreshold] = None,
) -> List[Anomaly]:
    """Fetch all metrics and return a list of threshold breaches.

    Per-metric thresholds can be overridden via environment variables
    named ``THRESHOLD_{METRIC_NAME}`` (e.g. ``THRESHOLD_CPU=95``).
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    anomalies: List[Anomaly] = []

    for mt in thresholds:
        env_key = f"THRESHOLD_{mt.metric_name.upper()}"
        effective_threshold = float(os.environ.get(env_key, mt.default_threshold))

        value = mt.fetch_fn(prometheus_url, minion_id)
        if value is None:
            logger.warning(
                "Metric '%s' returned no data for %s; skipping.",
                mt.metric_name,
                minion_id,
            )
            continue

        if value > effective_threshold:
            severity = _compute_severity(value, effective_threshold)
            anomaly = Anomaly(
                minion_id=minion_id,
                metric_name=mt.metric_name,
                current_value=value,
                threshold=effective_threshold,
                scenario=mt.scenario,
                severity=severity,
            )
            anomalies.append(anomaly)
            logger.warning(
                "Anomaly [%s]: %s=%.2f exceeds threshold %.2f on %s",
                severity,
                mt.metric_name,
                value,
                effective_threshold,
                minion_id,
            )
        else:
            logger.info(
                "Metric '%s' OK: %.2f <= %.2f on %s",
                mt.metric_name,
                value,
                effective_threshold,
                minion_id,
            )

    return anomalies
