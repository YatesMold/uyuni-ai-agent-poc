import logging
import requests
import subprocess
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class UyuniAIAgent:
    """
    A standalone AI Agent PoC that monitors Prometheus metrics and 
    executes localized system checks via mgrctl/SSH when anomalies are detected.
    """

    def __init__(self, prometheus_url: str, minion_id: str, threshold: float):
        self.prometheus_url = prometheus_url.rstrip('/')
        self.minion_id = minion_id
        self.threshold = threshold

    def fetch_node_load(self) -> Optional[float]:
        """Queries Prometheus for the node_load1 metric."""
        query_url = f"{self.prometheus_url}/api/v1/query"
        params = {"query": "node_load1"}
        
        try:
            response = requests.get(query_url, params=params, timeout=5)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            
            results = data.get('data', {}).get('result', [])
            if results:
                return float(results[0]['value'][1])
            
            logger.warning("No metric data found for node_load1.")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Prometheus connection error: {e}")
            return None

    def execute_mgrctl_inspection(self) -> str:
        """Executes a diagnostic Salt command on the minion via mgrctl."""
        logger.info(f"Gathering live system state from {self.minion_id} via mgrctl...")
        
        cmd = [
            "mgrctl", "exec",
            f"salt '{self.minion_id}' cmd.run 'ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 10'"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except FileNotFoundError:
            logger.warning("'mgrctl' binary not found. Returning simulated fallback data for PoC.")
            return "SIMULATED_OUTPUT: High CPU usage detected on /usr/lib/venv-salt-minion"
        except subprocess.CalledProcessError as e:
            logger.error(f"Command execution failed: {e.stderr}")
            return f"ERROR: {e.stderr}"

    def run_check_cycle(self) -> bool:
        """Runs a single monitoring and inspection cycle. Returns True if alert triggered."""
        load = self.fetch_node_load()
        if load is not None:
            logger.info(f"Current node_load1: {load}")
            if load > self.threshold:
                logger.warning(f"ALERT: Load ({load}) exceeds threshold ({self.threshold})!")
                state = self.execute_mgrctl_inspection()
                logger.info(f"System State Gathered:\n{state}")
                return True
        return False
