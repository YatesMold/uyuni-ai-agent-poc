# Uyuni AI Agent - Proof of Concept (PoC)

This repository contains the standalone Python Proof of Concept for the **GSoC 2026: AI-Powered Intelligent Monitoring and Root Cause Analysis for Uyuni** proposal.

## Architecture & Security Alignment
As discussed with the Uyuni maintainers, to maintain strict security boundaries and isolation, this AI Agent runs as an **independent, standalone container** rather than inside the Uyuni server container. 

Instead of relying on internal server tools (like Salt-API/CherryPy), it securely orchestrates targeted system inspections from the outside by wrapping the official **mgrctl exec** CLI utility and standard SSH commands.

## Features
- **Prometheus Ingestion:** Queries the Prometheus HTTP API (e.g., node_load1).
- **Threshold Evaluation:** Evaluates anomalies based on configurable thresholds.
- **mgrctl Orchestration:** Upon anomaly detection, dynamically executes Salt commands on the affected minions (e.g., fetching top CPU-consuming processes) using mgrctl exec.
- **Enterprise-ready Code:** Fully typed (typing), modularized, structured with standard logging, and covered by pytest unit tests.
- **Secure by Default:** Utilizes the official **openSUSE BCI** (Base Container Image) for Python 3.11 to ensure a minimal, secure, and vulnerability-free footprint.

## Running the PoC

### Local Execution (Simulation Mode)
If mgrctl is not present on your system, the agent will gracefully fall back to returning simulated data for demonstration purposes.

Run the following:
`pip install -r requirements.txt`
`python main.py`

### Running the Test Suite
`pytest tests/ -v`

## Docker Deployment
Build the image:
`docker build -t uyuni-ai-agent-poc .`

Run the container:
`docker run -e PROMETHEUS_URL="http://your-prom:9090" -e MINION_ID="myminion.mgr.suse.de" uyuni-ai-agent-poc`
