ALERT: High PostgreSQL Active Connection Count Detected
Minion: {minion_id}
Observed Active Connections: {metric_value}
Threshold: {threshold}

## Scenario Context
The number of active PostgreSQL connections on this Uyuni-managed minion has exceeded the
configured threshold. Uyuni's PostgreSQL database handles all channel metadata, system
registration, action scheduling, and audit data. A spike in active connections typically
indicates long-running queries holding connections open, Taskomatic batch jobs competing
for database access, or a connection leak in the Java application layer.

## What to Look For
- Long-running queries (duration > 30 seconds): these block connection slots and can
  indicate missing indexes on rhnChannel, rhnServerAction, or rhnPackage tables.
- VACUUM or ANALYZE operations running during peak hours, competing with application queries.
- Multiple connections in "active" state executing similar queries, which suggests a
  Taskomatic task fanout (e.g. errata cache regeneration) saturating the pool.
- Whether the query pattern involves rhnServerAction or rhnAction joins, which are
  common bottlenecks during large-scale patch deployment.

## Tool Output Included Below
Source: psql query of pg_stat_activity (queries running > 5 seconds)
(slow query listing, captured via mgrctl on {minion_id})

--- RAW SYSTEM OUTPUT ---