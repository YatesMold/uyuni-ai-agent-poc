import os
import time
import logging
from agent.evaluator import evaluate_metrics
from agent.ai_agent import run_investigation
from agent.alerting import build_alert, send_to_alertmanager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    minion_id = os.getenv("MINION_ID", "myminion.mgr.suse.de")
    llm_api_key = os.getenv("LLM_API_KEY")
    alertmanager_url = os.getenv("ALERTMANAGER_URL", "http://localhost:9093")
    alertmanager_enabled = os.getenv("ALERTMANAGER_ENABLED", "false").lower() == "true"

    if not llm_api_key:
        logger.warning("LLM_API_KEY is not set. AI analysis will be skipped.")
    if alertmanager_enabled:
        logger.info("AlertManager integration enabled at %s", alertmanager_url)

    logger.info("Starting Uyuni AI Agent PoC for %s...", minion_id)

    while True:
        try:
            anomalies = evaluate_metrics(prometheus_url, minion_id)
            for anomaly in anomalies:
                rca = run_investigation(anomaly, llm_api_key)
                logger.info("RCA for %s/%s:\n%s", anomaly.minion_id, anomaly.metric_name, rca)
                if alertmanager_enabled:
                    send_to_alertmanager(alertmanager_url, [build_alert(anomaly, rca)])
            time.sleep(60 if anomalies else 10)
        except KeyboardInterrupt:
            logger.info("Agent stopped by user.")
            break

if __name__ == "__main__":
    main()
