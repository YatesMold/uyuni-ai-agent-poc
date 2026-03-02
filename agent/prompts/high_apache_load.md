ALERT: High Apache Worker Count Detected
Minion: {minion_id}
Observed Busy Workers: {metric_value}
Threshold: {threshold}

## Scenario Context
The number of busy Apache workers on this Uyuni-managed minion has exceeded the configured
threshold. In Uyuni deployments, Apache httpd acts as the front-end reverse proxy for the
Uyuni web UI, XMLRPC API, and Salt API endpoints. When busy workers approach the
MaxRequestWorkers limit, new client connections queue or are refused.

## What to Look For
- Whether the error log contains "AH00161: server reached MaxRequestWorkers setting",
  confirming the prefork pool is fully saturated.
- Proxy errors (AH00957, AH01114) indicating a backend (Tomcat, Salt API) is
  unresponsive, causing workers to block on proxy_http connections.
- Repeated slow URI patterns (e.g. /rhn/manager/api/) that suggest an expensive
  API endpoint is holding workers for extended periods.
- SSL renegotiation warnings or certificate errors that may cause client retries,
  amplifying connection pressure.

## Tool Output Included Below
Source: tail -n 50 /var/log/apache2/error_log
(last 50 lines of the Apache error log, captured via mgrctl on {minion_id})

--- RAW SYSTEM OUTPUT ---