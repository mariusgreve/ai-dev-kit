---
name: postgres
description: Design or review PostgreSQL schemas, queries, indexes and safe database migrations.
---

# PostgreSQL

- Inspect the schema, data volume, query plans and migration framework before proposing changes.
- Make migrations forward-safe and compatible with the application's rollout order.
- Avoid long table locks and full rewrites on large tables; separate expansion, backfill and contraction when necessary.
- Add indexes for demonstrated access patterns and verify with `EXPLAIN (ANALYZE, BUFFERS)` when representative data is available.
- State rollback and data-loss implications explicitly.
