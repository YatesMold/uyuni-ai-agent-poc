ALERT: High CPU Usage Detected
Minion: {minion_id}
Observed CPU Usage: {metric_value}%
Threshold: {threshold}%

## Scenario Context
CPU usage on this Uyuni-managed minion has exceeded the configured alert threshold.
In a Uyuni environment, sustained high CPU is commonly caused by runaway Salt jobs,
zypper package operations, or the Taskomatic scheduler consuming excessive cycles.

## What to Look For
- The top process by %CPU: is it a salt-minion worker, a zypper subprocess,
  a Java process (Taskomatic/mgr-taskomatic), or an unexpected third-party binary?
- Whether the offending process has a PPID pointing to salt-master or mgr-osad,
  indicating a Salt job that has stalled or looped.
- Whether multiple Python processes share a common PPID, suggesting a fanout of
  Salt worker threads under abnormal load.
- %MEM alongside %CPU: a process consuming both simultaneously points to a memory
  leak compounding CPU stall via swap pressure.

## Tool Output Included Below
Source: ps -eo pid,ppid,comm,%cpu,%mem --sort=-%cpu | head -15
(top 15 processes sorted by CPU descending, captured via mgrctl on {minion_id})

--- RAW SYSTEM OUTPUT ---
