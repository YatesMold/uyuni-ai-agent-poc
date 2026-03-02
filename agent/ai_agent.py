"""Agentic tool-use loop for Uyuni AI investigation.

Uses Gemini function calling to let the LLM autonomously select which
diagnostic tools to run on the managed minion, iterating until a final
Root Cause Analysis (RCA) text is produced.
"""

import logging
from typing import Dict, List

import requests

from agent import tools
from agent.evaluator import Anomaly
from agent.prompts import build_prompt, load_prompt

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.5-flash:generateContent"
)

_SYSTEM_PROMPT = load_prompt("system_prompt.md")

_MAX_TOOL_ROUNDS = 5

# ---------------------------------------------------------------------------
# Tool Registry — maps tool name → Gemini function declaration.
# The callable is resolved at runtime via getattr(tools, name) so that
# unittest.mock.patch works correctly.
# ---------------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, dict] = {
    "execute_mgrctl_inspection": {
        "name": "execute_mgrctl_inspection",
        "description": (
            "Runs a general diagnostic command on the minion showing the "
            "top processes by CPU usage (ps output with PID, PPID, CMD, "
            "%MEM, %CPU). Good for a quick initial overview."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_top_cpu_processes": {
        "name": "get_top_cpu_processes",
        "description": (
            "Returns the top 15 processes sorted by CPU usage. Use this "
            "when investigating high CPU or load anomalies."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_top_memory_processes": {
        "name": "get_top_memory_processes",
        "description": (
            "Returns the top 15 processes sorted by memory usage. Use "
            "this when investigating high memory consumption."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_disk_usage_breakdown": {
        "name": "get_disk_usage_breakdown",
        "description": (
            "Returns filesystem usage (df -h) and sizes of key "
            "directories (/var, /tmp, /home, /opt). Use this when "
            "investigating disk space issues."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_running_services": {
        "name": "get_running_services",
        "description": (
            "Returns the list of currently running systemd services. "
            "Use this to check which services are active on the minion."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_service_logs": {
        "name": "get_service_logs",
        "description": (
            "Returns the last 50 journal lines for a specific systemd "
            "service. Use this to investigate logs of a service that "
            "appears problematic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": (
                        "The systemd service unit name, e.g. "
                        "'salt-minion.service', 'apache2.service', "
                        "'postgresql.service'."
                    ),
                },
            },
            "required": ["service_name"],
        },
    },
    "get_apache_error_log": {
        "name": "get_apache_error_log",
        "description": (
            "Returns the last 50 lines of the Apache error log. Use "
            "this when investigating Apache/httpd worker or proxy issues."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "get_postgres_slow_queries": {
        "name": "get_postgres_slow_queries",
        "description": (
            "Returns currently running slow PostgreSQL queries (those "
            "exceeding 5 seconds). Use this when investigating database "
            "performance or high connection counts."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def _build_function_declarations() -> List[dict]:
    """Extract the list of Gemini function declarations from the registry."""
    return list(TOOL_REGISTRY.values())


def _execute_tool(tool_name: str, args: dict, minion_id: str) -> str:
    """Look up a tool in the registry and execute it with auto-injected minion_id.

    The callable is resolved at runtime via ``getattr(tools, tool_name)``
    so that ``unittest.mock.patch`` on ``agent.ai_agent.tools.<name>``
    works correctly.

    Returns the raw string output from the tool, or an error message if the
    tool raised an exception or was not found.
    """
    if tool_name not in TOOL_REGISTRY:
        return (
            f"ERROR: Unknown tool '{tool_name}'. "
            f"Available tools: {', '.join(TOOL_REGISTRY.keys())}"
        )

    fn = getattr(tools, tool_name)
    try:
        return fn(minion_id, **args)
    except Exception as e:
        logger.warning("Tool '%s' raised %s: %s", tool_name, type(e).__name__, e)
        return f"ERROR: {type(e).__name__}: {e}"


def run_investigation(anomaly: Anomaly, api_key: str) -> str:
    """Run an agentic tool-use investigation loop for a detected anomaly.

    Sends the anomaly context to Gemini with function declarations for all
    registered tools. Gemini can call tools to gather diagnostic data, and
    the loop continues until Gemini produces a final text RCA or the maximum
    number of tool-call rounds is reached.
    """
    # --- Fallback: no API key ---
    if not api_key:
        logger.warning("No LLM API key provided. Falling back to raw inspection.")
        return tools.execute_mgrctl_inspection(anomaly.minion_id)

    # --- Build initial prompt ---
    context = {
        "minion_id": anomaly.minion_id,
        "metric_value": str(anomaly.current_value),
        "threshold": str(anomaly.threshold),
        "raw_output": "",
    }
    try:
        user_prompt = build_prompt(anomaly.scenario, context)
    except FileNotFoundError:
        user_prompt = (
            f"ALERT: {anomaly.metric_name} anomaly detected on "
            f"{anomaly.minion_id}. Current value: {anomaly.current_value}, "
            f"threshold: {anomaly.threshold}, severity: {anomaly.severity}. "
            "Use the available tools to investigate and provide a "
            "Root Cause Analysis."
        )

    # --- Build Gemini payload pieces ---
    contents: List[dict] = [
        {"role": "user", "parts": [{"text": user_prompt}]},
    ]
    function_declarations = _build_function_declarations()

    # --- Agentic loop ---
    for round_num in range(_MAX_TOOL_ROUNDS):
        payload = {
            "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "tools": [{"functionDeclarations": function_declarations}],
            "contents": contents,
        }

        try:
            response = requests.post(
                _GEMINI_URL,
                json=payload,
                params={"key": api_key},
                timeout=30,
            )
            response.raise_for_status()
            response_json = response.json()
        except Exception as e:
            safe_msg = str(e).replace(api_key, "***") if api_key else str(e)
            logger.error("Gemini API error on round %d: %s", round_num, safe_msg)
            return tools.execute_mgrctl_inspection(anomaly.minion_id)

        # --- Parse response ---
        try:
            response_parts = response_json["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            logger.error("Unexpected Gemini response structure: %s", e)
            return tools.execute_mgrctl_inspection(anomaly.minion_id)

        function_calls = [
            p["functionCall"] for p in response_parts if "functionCall" in p
        ]
        text_parts = [p["text"] for p in response_parts if "text" in p]

        # --- Text-only response → done ---
        if text_parts and not function_calls:
            return "\n".join(text_parts)

        # --- Function calls → execute and continue ---
        if function_calls:
            contents.append({"role": "model", "parts": response_parts})

            fn_response_parts = []
            for fc in function_calls:
                tool_name = fc["name"]
                tool_args = fc.get("args", {})
                logger.info(
                    "Round %d: Gemini called tool '%s' with args %s",
                    round_num,
                    tool_name,
                    tool_args,
                )
                output = _execute_tool(tool_name, tool_args, anomaly.minion_id)
                fn_response_parts.append(
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": {"output": output},
                        }
                    }
                )

            contents.append({"role": "user", "parts": fn_response_parts})
            continue

        # --- Neither text nor function calls (unexpected) ---
        logger.warning(
            "Round %d: Gemini returned neither text nor functionCall.",
            round_num,
        )
        return tools.execute_mgrctl_inspection(anomaly.minion_id)

    # --- Max rounds exceeded: force a final text response ---
    logger.warning(
        "Agentic loop reached max rounds (%d) without final RCA.",
        _MAX_TOOL_ROUNDS,
    )
    payload_final = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": contents
        + [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "You have reached the maximum number of tool "
                            "calls. Based on all the evidence gathered "
                            "above, provide your Root Cause Analysis now."
                        )
                    }
                ],
            },
        ],
    }
    try:
        response = requests.post(
            _GEMINI_URL,
            json=payload_final,
            params={"key": api_key},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        safe_msg = str(e).replace(api_key, "***") if api_key else str(e)
        logger.error("Final RCA request failed: %s", safe_msg)
        return tools.execute_mgrctl_inspection(anomaly.minion_id)
