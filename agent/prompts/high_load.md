ALERT: High System Load Average Detected
Minion: {minion_id}
Observed Load Average (1m): {metric_value}
Threshold: {threshold}

## Scenario Context
System load average on this Uyuni-managed minion has exceeded the configured alert threshold.
In a Uyuni environment, sustained high load is commonly caused by a large number of concurrent
Salt job workers, zypper operations holding the RPM database lock, or a batch of Taskomatic
scheduler tasks running simultaneously — all of which queue CPU-bound work faster than the
system can drain it.

## What to Look For
- The number of processes in R (running) or D (uninterruptible sleep) state: D-state processes
  indicate I/O or lock contention, which inflates load independently of CPU usage.
- Whether the high-load processes share a common PPID, pointing to a Salt master dispatch
  wave or a Taskomatic thread pool exhaustion event.
- Whether load is CPU-bound (high %CPU across many processes) or I/O-bound (low %CPU but
  many D-state processes waiting on disk or the RPM database lock).
- Whether load correlates with a recent Salt highstate, package refresh, or cron-triggered job.

## Tool Output Included Below
Source: ps -eo pid,ppid,comm,%cpu,%mem,stat --sort=-%cpu | head -15
(top 15 processes sorted by CPU descending, captured via mgrctl on {minion_id})

--- RAW SYSTEM OUTPUT ---
