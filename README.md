# Uyuni AI Agent - Proof of Concept (PoC)

This repository contains the standalone Python Proof of Concept for the **GSoC 2026: AI-Powered Intelligent Monitoring and Root Cause Analysis for Uyuni** proposal.

## Architecture & Security Alignment

As discussed with the Uyuni maintainers, to maintain strict security boundaries and isolation, this AI Agent runs as an **independent, standalone container** rather than inside the Uyuni server container.

Instead of relying on internal server tools (like Salt-API/CherryPy), it securely orchestrates targeted system inspections from the outside by wrapping the official **mgrctl exec** CLI utility and standard SSH commands. Raw diagnostic output is then sent to an LLM for automated Root Cause Analysis.

## Workflow Diagram

```mermaid
sequenceDiagram
    participant P as Prometheus
    participant A as AI Agent Container
    participant M as Uyuni Server (mgrctl)
    participant L as LLM (Gemini 2.5 Flash)

    loop Every 10 seconds
        A->>P: Fetch metrics (CPU%, Memory%, Disk%, Load)
        P-->>A: Return Metric Values

        alt Any metric > Threshold
            A->>M: Execute inspection tools via mgrctl exec
            Note right of M: ps, df, du, systemctl,<br/>journalctl
            M-->>A: Return Raw Terminal Output
            A->>L: Send Output + Scenario-Specific Prompt
            Note right of L: high_cpu.md / high_memory.md /<br/>disk_full.md
            L-->>A: Return Root Cause Analysis
            A->>A: Log Human-Readable Alert
        end
    end
```

## Features

- **Multi-Metric Prometheus Monitoring:** Queries CPU usage, memory usage, disk usage, and node load via PromQL — not just a single metric.
- **Threshold Evaluation:** Evaluates anomalies based on configurable thresholds.
- **mgrctl Inspection Toolkit:** Upon anomaly detection, dynamically executes multiple Salt commands on affected minions via `mgrctl exec`:
  - Top CPU-consuming processes
  - Top memory-consuming processes
  - Disk usage breakdown (`df` + `du`)
  - Running systemd services
  - Service journal logs (with input sanitization to prevent command injection)
- **Scenario-Specific AI Analysis:** Sends raw diagnostic output to Gemini 2.5 Flash with a SUSE sysadmin system prompt and scenario-aware templates (high CPU, high memory, disk full). Returns a structured RCA identifying the responsible process, root cause, and concrete remediation steps. Falls back gracefully to raw output if no API key is configured.
- **Simulation Mode:** When `mgrctl` is not available (dev/CI), all inspection tools return realistic simulated terminal output so the full pipeline can be demonstrated without a live Uyuni server.
- **Secure by Default:** Uses the official **openSUSE BCI** (Base Container Image) for Python 3.11. The LLM API key is never hardcoded and is redacted from error logs. Service name inputs are validated against an allowlist pattern to prevent injection.
- **Comprehensive Test Suite:** 52 unit tests across 4 test files — all external calls (Prometheus, mgrctl, Gemini API) are mocked. No real services or API keys needed.

## Project Structure

```text
uyuni-ai-agent-poc/
├── agent/
│   ├── core.py              # UyuniAIAgent class — orchestrates monitoring + LLM analysis
│   ├── metrics.py            # Prometheus query functions (CPU, memory, disk, load)
│   ├── tools.py              # mgrctl inspection tools with simulated fallback
│   └── prompts/
│       ├── __init__.py       # load_prompt() and build_prompt() helpers
│       ├── system_prompt.md  # Base SUSE sysadmin persona for Gemini
│       ├── high_cpu.md       # Scenario template for CPU anomalies
│       ├── high_memory.md    # Scenario template for memory anomalies
│       └── disk_full.md      # Scenario template for disk anomalies
├── tests/
│   ├── test_core.py          # Agent delegation and LLM integration tests
│   ├── test_metrics.py       # Prometheus query tests (mocked HTTP)
│   ├── test_tools.py         # Inspection tools tests (mocked subprocess)
│   └── test_prompts.py       # Prompt loading and template interpolation tests
├── main.py                   # Entry point — reads env vars, runs monitoring loop
├── Dockerfile                # Production container (openSUSE BCI Python 3.11)
├── requirements.txt          # requests==2.31.0, pytest==8.0.0
├── .env.example              # Environment variable reference
└── .github/workflows/ci.yml  # GitHub Actions CI pipeline
```

## Running the PoC

### Local Execution (Simulation Mode)

If `mgrctl` is not present on your system, the agent will gracefully fall back to returning simulated data for demonstration purposes. `LLM_API_KEY` is optional — without it, AI analysis is skipped and raw output is logged instead.

```bash
pip install -r requirements.txt
export LLM_API_KEY="your_gemini_api_key"   # optional
python main.py
```

Get a free Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### Running the Test Suite

```bash
pytest tests/ -v
```

All external calls (Prometheus, mgrctl, Gemini API) are mocked — no real services or API keys are needed.

## Docker Deployment

Build the image:

```bash
docker build -t uyuni-ai-agent-poc .
```

Run the container:

```bash
docker run \
  -e PROMETHEUS_URL="http://your-prom:9090" \
  -e MINION_ID="myminion.mgr.suse.de" \
  -e THRESHOLD="2.0" \
  -e LLM_API_KEY="your_gemini_api_key" \
  uyuni-ai-agent-poc
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus HTTP API base URL |
| `MINION_ID` | `myminion.mgr.suse.de` | Salt minion identifier to monitor |
| `THRESHOLD` | `2.0` | Node load value that triggers inspection |
| `LLM_API_KEY` | *(none)* | Gemini API key — AI analysis is skipped if not set |
