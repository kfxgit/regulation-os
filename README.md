# Regulation OS

AI-powered Regulatory Intelligence & Compliance Platform that converts
regulatory documents (circulars, notifications, laws, amendments) into
structured, verified, queryable requirements, and then into real-world
compliance tracking.

See [CLAUDE.md](./CLAUDE.md) for the full project briefing, principles, and
roadmap. See [SESSION_LOG.md](./SESSION_LOG.md) for a detailed build history.

This repository is public for portfolio/reference purposes. See
[LICENSE](./LICENSE) — all rights reserved, no reuse permitted without
written permission.

## Repo layout

```
apps/
  engine/   Python 3.11+ / FastAPI — OCR, AI extraction, verification, knowledge base
  api/      Node.js / Express — users, login, tasks, alerts, dashboards (Phase 3+)
  web/      Next.js / React / TypeScript — frontend (later phase)
```

## Status

**Phase 0 — complete**: 16-table regulation data model, Alembic migrations
(schema + integrity triggers), SBP-pack seed data, 9/9 integrity tests
passing.

**Phase 1 — complete**: full ingestion pipeline (PDF -> OCR -> Claude
extraction -> fuzzy-match source verification -> human review -> ACTIVE in
Postgres), run end-to-end against a 24-document real SBP corpus (master
circulars and table-heavy documents included). 326 `ACTIVE` requirements,
every one backed by a human review decision and an exact source citation.

**Phase 2 — in progress**: relationship extraction (AMENDS/SUPERSEDES/etc.
between documents) and the applicability engine (who/what each requirement
applies to: entity, product, business activity) are both built, run against
the full corpus, and reviewed — 24 relationships and 333 applicability
rules, all human-reviewed. Still open: change detection
(`RegulatoryChange`), full-text/semantic search, and the document browser.

**Phase 3+ (compliance engine, FinTech packs, multi-regulator)**: not
started — the Node/API side is an intentional `/health` stub until then.
