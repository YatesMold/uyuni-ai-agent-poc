ALERT: High Memory Usage Detected
Minion: {minion_id}
Observed Memory Usage: {metric_value}%
Threshold: {threshold}%

## Scenario Context
Memory usage on this Uyuni-managed minion has exceeded the configured alert threshold.
In a Uyuni environment, high memory is frequently caused by the Java heap of
mgr-taskomatic or tomcat growing unbounded, by salt-minion worker processes
accumulating large pillar data, or by a zypper operation loading a large package index.

## What to Look For
- The top process by %MEM: is it a JVM process (java, mgr-taskomatic), a Python
  process (salt-minion, up2date), or an unexpected workload?
- Absolute %MEM values: if the top consumer exceeds 30%, the system may be
  approaching swap exhaustion, which degrades all Uyuni operations.
- Whether %CPU for the top memory consumer is also elevated, indicating active
  processing rather than a dormant resident-set leak.
- If /usr/lib/jvm appears in the CMD column, the JVM heap limit (-Xmx) in
  Taskomatic or Tomcat configuration may need to be raised or the service restarted.

## Tool Output Included Below
Source: ps -eo pid,ppid,comm,%mem,%cpu --sort=-%mem | head -15
(top 15 processes sorted by memory descending, captured via mgrctl on {minion_id})

--- RAW SYSTEM OUTPUT ---
