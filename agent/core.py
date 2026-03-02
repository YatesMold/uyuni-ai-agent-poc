import logging
import requests
from typing import Optional, Tuple

from agent.evaluator import Anomaly, evaluate_metrics
from agent.ai_agent import run_investigation
from agent.prompts import build_prompt, load_prompt

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.5-flash:generateContent"
)

_SYSTEM_PROMPT = load_prompt("system_prompt.md")


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

    def analyze_with_llm(self, raw_output: str, scenario: str = None) -> str:
        """Sends raw diagnostic output to Gemini and returns a human-readable RCA.

        When *scenario* is provided (e.g. ``"high_cpu"``), the corresponding
        scenario template is loaded and interpolated with agent context before
        being sent as the user message.  Otherwise a plain wrapper is used.

        Falls back to returning raw_output unchanged if no API key was configured
        or if the API call fails.
        """
        if not self._llm_api_key:
            logger.warning("LLM_API_KEY not configured. Skipping AI analysis.")
            return raw_output

        if scenario:
            user_message = build_prompt(scenario, {
                "minion_id": self.minion_id,
                "metric_value": "N/A",
                "threshold": self.threshold,
                "raw_output": raw_output,
            })
        else:
            user_message = f"--- RAW SYSTEM OUTPUT ---\n{raw_output}\n--- END OUTPUT ---"

        try:
            payload = {
                "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": user_message}]}],
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

    def run_check_cycle(self) -> Tuple[Optional[Anomaly], Optional[str]]:
        """Runs a single monitoring and inspection cycle.

        Delegates to evaluate_metrics() + run_investigation() for multi-metric
        evaluation via the agentic tool-use loop. Returns the first detected
        anomaly and its RCA, or (None, None) when no threshold is breached.
        """
        anomalies = evaluate_metrics(self.prometheus_url, self.minion_id)
        if not anomalies:
            return None, None
        anomaly = anomalies[0]
        rca = run_investigation(anomaly, self._llm_api_key)
        logger.info("RCA for %s/%s:\n%s", anomaly.minion_id, anomaly.metric_name, rca)
        return anomaly, rca
