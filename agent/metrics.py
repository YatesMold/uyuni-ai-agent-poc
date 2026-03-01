import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _query_prometheus(base_url: str, promql: str) -> Optional[float]:
    """Executes a PromQL instant query and returns the first result as a float.

    Handles timeouts, non-200 responses, empty result sets, and parse
    failures in one place so that every metric function stays trivial.

    Returns None (never raises) for any failure.
    """
    url = f"{base_url}/api/v1/query"
    try:
        response = requests.get(url, params={"query": promql}, timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Prometheus connection error: {e}")
        return None

    try:
        data: Dict[str, Any] = response.json()
        results = data.get("data", {}).get("result", [])
    except ValueError as e:
        logger.error(f"Failed to decode Prometheus JSON for '{promql}': {e}")
        return None

    if not results:
        logger.warning(f"No metric data found for '{promql}'.")
        return None

    try:
        return float(results[0]["value"][1])
    except (KeyError, IndexError, ValueError) as e:
        logger.error(f"Failed to parse Prometheus result for '{promql}': {e}")
        return None


def fetch_node_load(base_url: str, minion_id: str) -> Optional[float]:
    """Queries Prometheus for the node_load1 metric."""
    promql = f'node_load1{{instance="{minion_id}"}}'
    return _query_prometheus(base_url, promql)


def fetch_memory_usage_percent(base_url: str, instance: str) -> Optional[float]:
    """Queries Prometheus for memory usage as a percentage."""
    promql = (
        f'100 * (1 - node_memory_MemAvailable_bytes{{instance="{instance}"}}'
        f' / node_memory_MemTotal_bytes{{instance="{instance}"}})'
    )
    return _query_prometheus(base_url, promql)


def fetch_cpu_usage_percent(base_url: str, instance: str) -> Optional[float]:
    """Queries Prometheus for CPU usage as a percentage."""
    promql = (
        '100 * (1 - avg by (instance)'
        f'(rate(node_cpu_seconds_total{{mode="idle",instance="{instance}"}}[5m])))'
    )
    return _query_prometheus(base_url, promql)


def fetch_disk_usage_percent(base_url: str, instance: str) -> Optional[float]:
    """Queries Prometheus for root disk usage as a percentage."""
    promql = (
        '100 * (1 - node_filesystem_avail_bytes'
        f'{{instance="{instance}",mountpoint="/",fstype!="tmpfs"}}'
        ' / node_filesystem_size_bytes'
        f'{{instance="{instance}",mountpoint="/",fstype!="tmpfs"}})'
    )
    return _query_prometheus(base_url, promql)
