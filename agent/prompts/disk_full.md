ALERT: High Disk Usage Detected
Minion: {minion_id}
Observed Disk Usage (root filesystem): {metric_value}%
Threshold: {threshold}%

## Scenario Context
The root filesystem or a monitored mountpoint on this Uyuni-managed minion is critically
full. Disk exhaustion is most commonly caused by accumulated package cache under
/var/cache/zypp, growing Salt job cache at /var/cache/salt, uncleaned Taskomatic logs
at /var/log/rhn, or a large software channel repository mirror under /var/spacewalk.

## What to Look For
- Which filesystem is at or above the threshold in df -h: is it / (root), /var,
  or another mountpoint?
- The du -sh breakdown for /var — the primary growth area in Uyuni deployments.
  Values above 150-180 GB on a server without a dedicated /var partition indicate
  imminent exhaustion.
- Whether /tmp is unexpectedly large (>1 GB), which can indicate a failed package
  transaction that left behind extracted RPM contents.
- Whether /opt contains unexpected data from a third-party installation.

## Tool Output Included Below
Source: df -h && du -sh /var /tmp /home /opt
(filesystem usage and key directory sizes, captured via mgrctl on {minion_id})

--- RAW SYSTEM OUTPUT ---
