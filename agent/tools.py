import logging
import re
import subprocess
from typing import Dict

logger = logging.getLogger(__name__)

_SAFE_SERVICE_NAME = re.compile(r'^[a-zA-Z0-9._@-]+$')

# Realistic simulated terminal output used as fallback when mgrctl is unavailable.
# Each key corresponds to a public inspection function name.
SIMULATED_OUTPUTS: Dict[str, str] = {
    "top_processes": (
        "  PID  PPID CMD                                         %MEM %CPU\n"
        " 1842     1 /usr/lib/venv-salt-minion/bin/python3 -u /u  12.3 95.4\n"
        "  431     1 /usr/sbin/mgr-osad --pid-file /var/run/osad   4.1  3.2\n"
        "  988     1 /usr/bin/python3 /usr/bin/salt-master -d       2.8  1.5\n"
        " 1200   988 /usr/bin/python3 /usr/bin/zypper --non-inter   1.9  0.8\n"
        "  112     1 /usr/lib/systemd/systemd-journald              1.2  0.3\n"
        "   52     1 /usr/sbin/rsyslogd -n                          0.4  0.1\n"
        "  200     1 /usr/sbin/sshd -D -o AuthorizedKeysCommand     0.3  0.1\n"
        "  310     1 /usr/sbin/crond -n                              0.1  0.0\n"
        "  320     1 /usr/lib/systemd/systemd-logind                 0.1  0.0\n"
        "    1     0 /usr/lib/systemd/systemd --switched-root --s    0.1  0.0"
    ),
    "top_memory_processes": (
        "  PID  PPID CMD                                         %MEM %CPU\n"
        " 2501     1 /usr/lib/jvm/java-17-openjdk/bin/java -Xmx1  38.7  4.2\n"
        " 1842     1 /usr/lib/venv-salt-minion/bin/python3 -u /u   12.3 95.4\n"
        " 3102  2501 /usr/bin/python3 /usr/share/rhn/up2date --no   8.1  0.9\n"
        "  431     1 /usr/sbin/mgr-osad --pid-file /var/run/osad    4.1  3.2\n"
        "  988     1 /usr/bin/python3 /usr/bin/salt-master -d        2.8  1.5\n"
        " 1200   988 /usr/bin/python3 /usr/bin/zypper --non-inter    1.9  0.8\n"
        "  112     1 /usr/lib/systemd/systemd-journald               1.2  0.3\n"
        "   52     1 /usr/sbin/rsyslogd -n                           0.4  0.1\n"
        "  200     1 /usr/sbin/sshd -D -o AuthorizedKeysCommand      0.3  0.1\n"
        "    1     0 /usr/lib/systemd/systemd --switched-root --s     0.1  0.0"
    ),
"journal_errors": (
        "-- Logs begin at Mon 2025-06-01 00:00:00 UTC, end at Mon 2025-06-02 12:00:00 UTC. --\n"
        "Jun 02 11:45:12 test-minion systemd[1]: salt-minion.service: Main process exited, code=exited, status=1/FAILURE\n"
        "Jun 02 11:45:12 test-minion systemd[1]: salt-minion.service: Failed with result 'exit-code'.\n"
        "Jun 02 11:45:42 test-minion systemd[1]: salt-minion.service: Scheduled restart job, restart counter is at 3.\n"
        "Jun 02 11:45:42 test-minion systemd[1]: Started The Salt Minion.\n"
        "Jun 02 11:45:44 test-minion salt-minion[1842]: [WARNING ] Unable to connect to the salt master at salt.mgr.suse.de:4505\n"
        "Jun 02 11:45:44 test-minion salt-minion[1842]: [ERROR   ] The Salt Master has cached the "
        "public key for this node, but this node is not authenticated yet.\n"
        "Jun 02 11:58:32 test-minion salt-minion[1842]: [ERROR   ] Authentication error occurred.\n"
        "Jun 02 11:59:01 test-minion salt-minion[1842]: [ERROR   ] The minion was unable to check in with the master. "
        "Restarting salt-minion process to pick up any network changes.\n"
        "Jun 02 12:00:00 test-minion mgr-osad[431]: ERROR: Connection to Uyuni server lost. Retrying in 30s...\n"
        "Jun 02 12:00:30 test-minion mgr-osad[431]: ERROR: Failed to reconnect to Uyuni server (attempt 4/10)."
    ),
    "disk_usage": (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "/dev/sda1        50G   47G  3.0G  94% /\n"
        "/dev/sda2       200G  184G   16G  92% /var\n"
        "tmpfs            16G  1.2M   16G   1% /tmp\n"
        "156G\t/var\n"
        "12M\t/tmp\n"
        "284K\t/home\n"
        "4.8G\t/opt"
    ),
    "apache_error_log": (
        "[Mon Jun 02 11:45:03.123456 2025] [mpm_prefork:error] [pid 4521] AH00161: server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers setting\n"
        "[Mon Jun 02 11:45:10.654321 2025] [proxy:error] [pid 4522] (111)Connection refused: AH00957: HTTP: attempt to connect to 127.0.0.1:8080 (localhost) failed\n"
        "[Mon Jun 02 11:45:10.654400 2025] [proxy_http:error] [pid 4522] [client 192.168.1.50:43210] AH01114: HTTP: failed to make connection to backend: localhost\n"
        "[Mon Jun 02 11:46:01.111111 2025] [ssl:warn] [pid 4500] AH01909: RSA certificate configured for server does not include an ID which matches the server name\n"
        "[Mon Jun 02 11:47:22.222222 2025] [mpm_prefork:notice] [pid 4500] AH00171: Graceful restart requested, doing restart\n"
        "[Mon Jun 02 11:47:23.333333 2025] [mpm_prefork:error] [pid 4521] AH00161: server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers setting\n"
        "[Mon Jun 02 11:48:00.444444 2025] [core:error] [pid 4530] [client 10.0.0.15:52300] AH00126: Invalid URI in request GET /rhn/manager/api/contentmanagement/projects HTTP/1.1\n"
        "[Mon Jun 02 11:49:15.555555 2025] [mpm_prefork:error] [pid 4521] AH00161: server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers setting"
    ),
    "postgres_slow_queries": (
        "  pid  |    duration     |                                    query                                     |        state\n"
        "-------+-----------------+------------------------------------------------------------------------------+---------------------\n"
        " 12045 | 00:02:34.567891 | SELECT ro.id, ro.label, ro.name FROM rhnChannel ro WHERE ro.parent_channel   | active\n"
        " 12102 | 00:01:12.345678 | UPDATE rhnServerAction SET status = 2 WHERE server_id IN (SELECT id FROM r  | active\n"
        " 12200 | 00:00:45.678901 | SELECT sa.server_id, sa.action_id FROM rhnServerAction sa JOIN rhnAction a  | active\n"
        " 12305 | 00:00:08.901234 | VACUUM ANALYZE rhnPackage                                                   | active\n"
        "(4 rows)"
    ),
    "running_services": (
        "  UNIT                               LOAD   ACTIVE SUB     DESCRIPTION\n"
        "  dbus.service                       loaded active running D-Bus System Message Bus\n"
        "  getty@tty1.service                 loaded active running Getty on tty1\n"
        "  salt-minion.service                loaded active running The Salt Minion\n"
        "  sshd.service                       loaded active running OpenSSH Daemon\n"
        "  systemd-journald.service           loaded active running Journal Service\n"
        "  systemd-logind.service             loaded active running User Login Management\n"
        "  systemd-udevd.service              loaded active running Rule-based Manager for Device Events\n"
        "  cron.service                       loaded active running Command Scheduler\n"
        "\n"
        "LOAD   = Reflects whether the unit definition was properly loaded.\n"
        "ACTIVE = The high-level unit activation state, i.e. generalization of SUB.\n"
        "SUB    = The low-level unit activation state, values depend on unit type.\n"
        "\n"
        "8 loaded units listed."
    ),
}


def _run_mgrctl(minion_id: str, command: str, fallback_key: str) -> str:
    """Run a Salt command on the minion via mgrctl and return stdout.

    Handles subprocess invocation, FileNotFoundError (mgrctl missing) and
    CalledProcessError centrally.  When mgrctl is unavailable the function
    returns the matching entry from ``SIMULATED_OUTPUTS`` so development
    and CI can proceed without a real Uyuni server.

    Args:
        minion_id: The Salt minion identifier.
        command: The shell command to execute on the minion via Salt cmd.run.
        fallback_key: Key into ``SIMULATED_OUTPUTS`` used when mgrctl is not found.
    """
    cmd = [
        "mgrctl",
        "exec",
        f"salt '{minion_id}' cmd.run '{command}'",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except FileNotFoundError:
        logger.warning(
            "'mgrctl' binary not found. Returning simulated fallback data for PoC."
        )
        return SIMULATED_OUTPUTS[fallback_key]
    except subprocess.CalledProcessError as e:
        logger.error(f"Command execution failed: {e.stderr}")
        return f"ERROR: {e.stderr}"


def execute_mgrctl_inspection(minion_id: str) -> str:
    """Executes a diagnostic Salt command on the minion via mgrctl."""
    logger.info(f"Gathering live system state from {minion_id} via mgrctl...")
    return _run_mgrctl(
        minion_id,
        "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -n 10",
        "top_processes",
    )


def get_top_cpu_processes(minion_id: str) -> str:
    """Returns the top 15 processes sorted by CPU usage (raw ps output)."""
    logger.info(f"Fetching top CPU processes from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        "ps -eo pid,ppid,comm,%cpu,%mem --sort=-%cpu | head -15",
        "top_processes",
    )


def get_top_memory_processes(minion_id: str) -> str:
    """Returns the top 15 processes sorted by memory usage (raw ps output)."""
    logger.info(f"Fetching top memory processes from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        "ps -eo pid,ppid,comm,%mem,%cpu --sort=-%mem | head -15",
        "top_memory_processes",
    )


def get_disk_usage_breakdown(minion_id: str) -> str:
    """Returns filesystem usage (df -h) and sizes of key directories."""
    logger.info(f"Fetching disk usage breakdown from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        "df -h && du -sh /var /tmp /home /opt",
        "disk_usage",
    )


def get_running_services(minion_id: str) -> str:
    """Returns currently running systemd services (raw systemctl output)."""
    logger.info(f"Fetching running services from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        "systemctl list-units --type=service --state=running --no-pager",
        "running_services",
    )


def get_service_logs(minion_id: str, service_name: str) -> str:
    """Returns the last 50 journal lines for *service_name*.

    Raises:
        ValueError: If *service_name* contains disallowed characters.
    """
    if not _SAFE_SERVICE_NAME.match(service_name):
        raise ValueError(
            f"Invalid service name '{service_name}': "
            "only alphanumeric characters, hyphens, underscores, dots, and @ are allowed."
        )
    logger.info(f"Fetching journal logs for {service_name} from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        f"journalctl -u {service_name} -n 50 --no-pager",
        "journal_errors",
    )


def get_apache_error_log(minion_id: str) -> str:
    """Returns the last 50 lines of the Apache error log (raw tail output)."""
    logger.info(f"Fetching Apache error log from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        "tail -n 50 /var/log/apache2/error_log",
        "apache_error_log",
    )


def get_postgres_slow_queries(minion_id: str) -> str:
    """Returns currently running slow PostgreSQL queries (raw psql output)."""
    logger.info(f"Fetching slow PostgreSQL queries from {minion_id}...")
    return _run_mgrctl(
        minion_id,
        "sudo -u postgres psql -c \"SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds' AND state != 'idle' ORDER BY duration DESC;\"",
        "postgres_slow_queries",
    )
