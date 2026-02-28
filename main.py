import os
import time
import logging
from agent.core import UyuniAIAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

def main():
    prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    minion_id = os.getenv("MINION_ID", "myminion.mgr.suse.de")
    threshold = float(os.getenv("THRESHOLD", "2.0"))
    llm_api_key = os.getenv("LLM_API_KEY")

    if not llm_api_key:
        logging.warning("LLM_API_KEY is not set. AI analysis will be skipped.")

    agent = UyuniAIAgent(prometheus_url, minion_id, threshold, llm_api_key=llm_api_key)
    logging.info(f"Starting Uyuni AI Agent PoC for {minion_id}...")

    while True:
        try:
            alert_triggered = agent.run_check_cycle()
            sleep_time = 60 if alert_triggered else 10
            time.sleep(sleep_time)
        except KeyboardInterrupt:
            logging.info("Agent stopped by user.")
            break

if __name__ == "__main__":
    main()
