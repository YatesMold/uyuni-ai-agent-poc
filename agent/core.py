import logging
import requests
import subprocess
from typing import Optional, Dict, Any
logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.5-flash:generateContent"
)

_SYSTEM_PROMPT = (
    "You are an expert SUSE Linux System Administrator with deep knowledge of the "
    "Uyuni management platform and Salt configuration management. "
    "Analyze the following raw terminal output from a system experiencing high CPU load. "
    "Provide: (1) a concise Root Cause Analysis identifying the most likely cause, "
    "(2) the specific process(es) responsible including PID and name, and "
    "(3) concrete remediation steps an operator should take immediately. "
    "Be precise, technical, and actionable. Keep your response under 200 words."
)


class UyuniAIAgent:
    """
    A standalone AI Agent PoC that monitors Prometheus metrics and
    executes localized system checks via mgrctl/SSH when anomalies are detected.
    When an LLM API key is provided, raw diagnostic output is analysed by Gemini
    and returned as a human-readable Root Cause Analysis (RCA).
    """

    def __init__(
        self,
        prometheus_url: str,
        minion_id: str,
        threshold: float,
        llm_api_key: Optional[str] = None,
    ):
        self.prometheus_url = prometheus_url.rstrip("/")
        self.minion_id = minion_id
        self.threshold = threshold
        self._llm_api_key: Optional[str] = llm_api_key

    def fetch_node_load(self) -> Optional[float]:
        """Queries Prometheus for the node_load1 metric."""
        query_url = f"{self.prometheus_url}/api/v1/query"
        params = {"query": "node_load1"}

        try:
            response = requests.get(query_url, params=params, timeout=5)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

            results = data.get("data", {}).get("result", [])
            if results:
                return float(results[0]["value"][1])

            logger.warning("No metric data found for node_load1.")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Prometheus connection error: {e}")
            return None

    def execute_mgrctl_inspection(self) -> str:
        """Executes a diagnostic Salt command on the minion via mgrctl."""
        logger.info(f"Gathering live system state from {self.minion_id} via mgrctl...")

        cmd = [
            "mgrctl",
            "exec",
            f"salt '{self.minion_id}' cmd.run 'ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 10'",
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

    def analyze_with_llm(self, raw_output: str) -> str:
        """Sends raw diagnostic output to Gemini and returns a human-readable RCA.

        Falls back to returning raw_output unchanged if no API key was configured
        or if the API call fails.
        """
        if not self._llm_api_key:
            logger.warning("LLM_API_KEY not configured. Skipping AI analysis.")
            return raw_output

        try:
            payload = {
                "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": f"--- RAW SYSTEM OUTPUT ---\n{raw_output}\n--- END OUTPUT ---"}]}],
            }
            response = requests.post(
                _GEMINI_URL,
                json=payload,
                params={"key": self._llm_api_key},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            safe_msg = str(e).replace(self._llm_api_key, "***") if self._llm_api_key else str(e)
            logger.error(f"LLM analysis failed: {safe_msg}. Falling back to raw output.")
            return raw_output

    def run_check_cycle(self) -> bool:
        """Runs a single monitoring and inspection cycle. Returns True if alert triggered."""
        load = self.fetch_node_load()
        if load is not None:
            logger.info(f"Current node_load1: {load}")
            if load > self.threshold:
                logger.warning(f"ALERT: Load ({load}) exceeds threshold ({self.threshold})!")
                state = self.execute_mgrctl_inspection()
                logger.info(f"System State Gathered:\n{state}")
                analysis = self.analyze_with_llm(state)
                logger.info(f"AI Root Cause Analysis:\n{analysis}")
                return True
        return False
