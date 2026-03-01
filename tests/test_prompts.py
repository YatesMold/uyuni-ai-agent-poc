from pathlib import Path
from unittest.mock import patch

import pytest

from agent.prompts import build_prompt, load_prompt, _resolve_prompt_path


# --- _resolve_prompt_path tests ---


def test_resolve_prompt_path_returns_path_in_prompts_dir():
    result = _resolve_prompt_path("system_prompt.md")
    assert result.parent.name == "prompts"
    assert result.name == "system_prompt.md"


def test_resolve_prompt_path_is_absolute():
    result = _resolve_prompt_path("system_prompt.md")
    assert result.is_absolute()


# --- load_prompt tests ---


def test_load_prompt_reads_file_content(tmp_path: Path):
    prompt_file = tmp_path / "test_prompt.txt"
    prompt_file.write_text("You are a helpful assistant.", encoding="utf-8")

    with patch("agent.prompts._PROMPTS_DIR", tmp_path):
        result = load_prompt("test_prompt.txt")

    assert result == "You are a helpful assistant."


def test_load_prompt_strips_whitespace(tmp_path: Path):
    prompt_file = tmp_path / "padded.txt"
    prompt_file.write_text("  hello world  \n\n", encoding="utf-8")

    with patch("agent.prompts._PROMPTS_DIR", tmp_path):
        result = load_prompt("padded.txt")

    assert result == "hello world"


def test_load_prompt_raises_on_missing_file(tmp_path: Path):
    with patch("agent.prompts._PROMPTS_DIR", tmp_path):
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            load_prompt("nonexistent.txt")


def test_load_prompt_error_includes_filename(tmp_path: Path):
    with patch("agent.prompts._PROMPTS_DIR", tmp_path):
        with pytest.raises(FileNotFoundError, match="nonexistent.txt"):
            load_prompt("nonexistent.txt")


# --- Integration: real system_prompt.md file exists ---


def test_system_prompt_file_exists():
    """Ensures the shipped system_prompt.md prompt file is loadable."""
    result = load_prompt("system_prompt.md")
    assert len(result) > 0
    assert "ROOT CAUSE ANALYSIS" in result


# --- build_prompt tests ---


def test_build_prompt_interpolates_placeholders():
    """Placeholders in the scenario template are replaced with context values."""
    result = build_prompt("high_cpu", {
        "minion_id": "web01.mgr.suse.de",
        "metric_value": "95.3",
        "threshold": "80",
        "raw_output": "PID CMD %CPU\n123 python 99.9",
    })
    assert "web01.mgr.suse.de" in result
    assert "95.3%" in result
    assert "80%" in result
    assert "{minion_id}" not in result
    assert "{metric_value}" not in result
    assert "{threshold}" not in result


def test_build_prompt_appends_raw_output():
    """Raw output appears after the scenario template marker."""
    raw = "PID CMD %CPU\n123 python 99.9"
    result = build_prompt("high_cpu", {
        "minion_id": "test-minion",
        "metric_value": "90",
        "threshold": "80",
        "raw_output": raw,
    })
    assert raw in result
    assert "--- END OUTPUT ---" in result
    # Raw output should come after the scenario context
    assert result.index("Scenario Context") < result.index(raw)


def test_build_prompt_raises_on_unknown_scenario():
    """FileNotFoundError is raised for a non-existent scenario template."""
    with pytest.raises(FileNotFoundError):
        build_prompt("nonexistent_scenario", {
            "minion_id": "m",
            "metric_value": "1",
            "threshold": "2",
            "raw_output": "x",
        })


def test_build_prompt_raises_on_missing_context_key():
    """KeyError is raised when a required placeholder is missing from context."""
    with pytest.raises(KeyError):
        build_prompt("high_cpu", {
            "raw_output": "PID CMD %CPU\n123 python 99.9",
            # missing minion_id, metric_value, threshold
        })
