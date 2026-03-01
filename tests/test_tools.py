import subprocess

import pytest
from unittest.mock import patch, MagicMock
from agent.tools import (
    SIMULATED_OUTPUTS,
    _run_mgrctl,
    execute_mgrctl_inspection,
    get_top_cpu_processes,
    get_top_memory_processes,
    get_disk_usage_breakdown,
    get_running_services,
    get_service_logs,
)


# --- _run_mgrctl tests ---


@patch("agent.tools.subprocess.run")
def test_run_mgrctl_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "PID CMD %CPU\n123 python 99.9"
    mock_run.return_value = mock_result

    output = _run_mgrctl("test-minion", "ps aux", "top_processes")

    assert "99.9" in output
    mock_run.assert_called_once_with(
        ["mgrctl", "exec", "salt 'test-minion' cmd.run 'ps aux'"],
        capture_output=True, text=True, check=True,
    )


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_run_mgrctl_fallback_when_binary_missing(mock_run):
    output = _run_mgrctl("test-minion", "ps aux", "top_processes")

    assert output == SIMULATED_OUTPUTS["top_processes"]


@patch("agent.tools.subprocess.run")
def test_run_mgrctl_returns_error_on_called_process_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="connection refused")

    output = _run_mgrctl("test-minion", "ps aux", "top_processes")

    assert output == "ERROR: connection refused"


# --- execute_mgrctl_inspection ---


@patch("agent.tools.subprocess.run")
def test_execute_mgrctl_inspection_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "PID CMD %CPU\n123 python 99.9"
    mock_run.return_value = mock_result

    output = execute_mgrctl_inspection("test-minion")
    assert "99.9" in output
    mock_run.assert_called_once()


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_execute_mgrctl_inspection_fallback(mock_run):
    output = execute_mgrctl_inspection("test-minion")
    assert output == SIMULATED_OUTPUTS["top_processes"]


@patch("agent.tools.subprocess.run")
def test_execute_mgrctl_inspection_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="connection refused")
    output = execute_mgrctl_inspection("test-minion")
    assert output == "ERROR: connection refused"


# --- get_top_cpu_processes ---


@patch("agent.tools.subprocess.run")
def test_get_top_cpu_processes_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "  PID  PPID COMMAND         %CPU %MEM\n 1842     1 salt-minion     98.7 12.3"
    mock_run.return_value = mock_result

    output = get_top_cpu_processes("test-minion")

    assert "98.7" in output
    mock_run.assert_called_once()


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_get_top_cpu_processes_fallback(mock_run):
    output = get_top_cpu_processes("test-minion")

    assert output == SIMULATED_OUTPUTS["top_processes"]


@patch("agent.tools.subprocess.run")
def test_get_top_cpu_processes_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="timeout")
    output = get_top_cpu_processes("test-minion")
    assert output == "ERROR: timeout"


# --- get_top_memory_processes ---


@patch("agent.tools.subprocess.run")
def test_get_top_memory_processes_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "  PID  PPID COMMAND         %MEM %CPU\n 1842     1 salt-minion     12.3 98.7"
    mock_run.return_value = mock_result

    output = get_top_memory_processes("test-minion")

    assert "12.3" in output
    mock_run.assert_called_once()


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_get_top_memory_processes_fallback(mock_run):
    output = get_top_memory_processes("test-minion")

    assert output == SIMULATED_OUTPUTS["top_memory_processes"]


@patch("agent.tools.subprocess.run")
def test_get_top_memory_processes_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="permission denied")
    output = get_top_memory_processes("test-minion")
    assert output == "ERROR: permission denied"


# --- get_disk_usage_breakdown ---


@patch("agent.tools.subprocess.run")
def test_get_disk_usage_breakdown_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "/dev/sda1        50G   47G  3.0G  94% /\n"
        "3.2G\t/var\n"
        "12M\t/tmp\n"
    )
    mock_run.return_value = mock_result

    output = get_disk_usage_breakdown("test-minion")

    assert "94%" in output
    mock_run.assert_called_once()


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_get_disk_usage_breakdown_fallback(mock_run):
    output = get_disk_usage_breakdown("test-minion")

    assert output == SIMULATED_OUTPUTS["disk_usage"]


@patch("agent.tools.subprocess.run")
def test_get_disk_usage_breakdown_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="disk error")
    output = get_disk_usage_breakdown("test-minion")
    assert output == "ERROR: disk error"


# --- get_running_services ---


@patch("agent.tools.subprocess.run")
def test_get_running_services_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = (
        "  UNIT                  LOAD   ACTIVE SUB     DESCRIPTION\n"
        "  sshd.service          loaded active running OpenSSH Daemon\n"
    )
    mock_run.return_value = mock_result

    output = get_running_services("test-minion")

    assert "sshd.service" in output
    mock_run.assert_called_once()


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_get_running_services_fallback(mock_run):
    output = get_running_services("test-minion")

    assert output == SIMULATED_OUTPUTS["running_services"]


@patch("agent.tools.subprocess.run")
def test_get_running_services_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="bus error")
    output = get_running_services("test-minion")
    assert output == "ERROR: bus error"


# --- get_service_logs ---


@patch("agent.tools.subprocess.run")
def test_get_service_logs_success(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Jun 02 12:00:00 test-minion sshd[200]: Server listening on 0.0.0.0 port 22."
    mock_run.return_value = mock_result

    output = get_service_logs("test-minion", "sshd.service")

    assert "listening" in output
    mock_run.assert_called_once()


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_get_service_logs_fallback(mock_run):
    output = get_service_logs("test-minion", "salt-minion.service")

    assert output == SIMULATED_OUTPUTS["journal_errors"]


@patch("agent.tools.subprocess.run")
def test_get_service_logs_error(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "mgrctl", stderr="unit not found")
    output = get_service_logs("test-minion", "sshd.service")
    assert output == "ERROR: unit not found"


def test_get_service_logs_rejects_injection():
    with pytest.raises(ValueError, match="Invalid service name"):
        get_service_logs("test-minion", "sshd; rm -rf /")


def test_get_service_logs_rejects_empty_name():
    with pytest.raises(ValueError, match="Invalid service name"):
        get_service_logs("test-minion", "")


@patch("agent.tools.subprocess.run", side_effect=FileNotFoundError)
def test_get_service_logs_accepts_template_unit(mock_run):
    """Template instances like getty@tty1.service must be accepted."""
    output = get_service_logs("test-minion", "getty@tty1.service")
    assert output == SIMULATED_OUTPUTS["journal_errors"]
