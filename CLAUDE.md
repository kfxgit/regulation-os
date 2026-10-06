# REGULATION OS — Project Briefing

## 1. What we are building

Regulation OS is an AI-powered Regulatory Intelligence & Compliance Platform.

It converts regulatory documents — circulars, notifications, laws, rules,
guidelines, amendments — into structured, verified, queryable requirements,
and then into real-world compliance tracking: obligations, tasks, deadlines,
impact analysis.

One sentence: we turn changing regulations into executable business compliance.

## 2. The problem

Compliance teams at banks, FinTechs, and companies receive regulatory PDFs
continuously. Today a human must: read every circular, understand it, decide
who/what it applies to, compare with old versions, find what changed, convert
it into tasks, update policies, collect evidence, track deadlines, and prepare
audit reports. This is slow, expensive, error-prone, and easy to get wrong —
and mistakes mean regulatory penalties.

## 3. The core idea (the product backbone)

```
REGULATION
   ↓
REQUIREMENT        (what the regulation says, structured + verified)
   ↓
APPLICABILITY      (who/what it applies to: entity, product, activity, dates)
   ↓
OBLIGATION         (what an organization must actually DO)
   ↓
CONTROL            (later phase: the internal control that satisfies it)
   ↓
EVIDENCE           (later phase: the proof it was done)
   ↓
COMPLIANCE         (compliant / partially / non-compliant status)
   ↓
IMPACT ANALYSIS    (a change arrives → what is affected, downstream)
```

The key differentiator is this CHAIN. We are not building a PDF search engine
or a document reader. Competitors stop at "search regulations". We connect
regulatory language to actual business operations.

## 4. Non-negotiable principles (memorize these)

- DOCUMENT ≠ RULE. A document contains definitions, rules, exceptions, tables, procedures, amendments. Never treat a paragraph as "one rule".
- REQUIREMENT ≠ OBLIGATION. Requirement = what the regulation says. Obligation = actor + action + object + frequency + deadline. Both stored separately, linked.
- AI IS NOT THE SOURCE OF TRUTH. Hierarchy: official regulation → verified source text → structured data → AI interpretation. Every requirement must trace to exact source text (page + character span). No citation = unpublishable.
- NO SILENT PUBLISHING. AI output is always a DRAFT candidate. A human reviews and approves/corrects before anything becomes ACTIVE.
- NO SILENT DEFAULTS. Missing critical values stay empty and flagged. Never fill with 0 or false — a wrong limit is worse than a missing one.
- NOTHING IS DELETED. When a circular amends a rule: new revision added, old revision marked SUPERSEDED, full history preserved, change recorded.
- REQUIREMENTS ARE IMMUTABLE. Amendments append revisions; never edit rows.
- HIGH-RISK FIELDS GET EXTRA VERIFICATION. Money, percentages, dates, deadlines, thresholds, prohibition language. "must not exceed 10%" must NEVER become "must exceed 10%".
- FIVE SEPARATE CONFIDENCE SCORES, never one generic score: extraction, source_match, classification, applicability, interpretation. The full five apply to RegulatoryRequirement. RegulatoryRelationship and ApplicabilityRule carry only the three that have a real meaning for them (extraction, classification, source_match) -- applicability is circular on a table that IS the applicability judgment, and interpretation doesn't add anything beyond extraction for a single reference/scope value. source_match is always computed by code (fuzzy match), never self-reported, on every table that has it.
  - Updated 2026-10-06: added confidence_classification + confidence_source_match to RegulatoryRelationship and ApplicabilityRule (previously only confidence_extraction). Existing rows from before this change are NULL on both new columns -- not backfilled, since confidence_classification would mean re-judging an already-reviewed decision and confidence_source_match could only be backfilled for the resolved rows, not the ones where the original extracted text was already discarded by resolution. NULL means "not computed for this batch", not zero.
  - Also noted: RegulatoryRequirement.confidence_applicability has existed since Phase 0 but is never populated by any extraction code -- ApplicabilityRule.confidence_extraction (its own table) does that job now. Left as NULL, not wired up; a decision for later, not a bug fixed here.

## 5. Scope strategy

- Start: State Bank of Pakistan (SBP) documents — first regulatory PACK, not the product boundary.
- The pipeline: PDF → OCR (pdf2image + Claude vision) → AI extraction (Anthropic Claude, structured output via tool calling / forced JSON) → Pydantic validation → source verification (fuzzy match) → human review → PostgreSQL knowledge base.
  - Updated 2026-09-11: "temperature 0" dropped from this line -- the Anthropic API no longer exposes a temperature parameter (confirmed by inspecting SDK 1.5.0's actual call signature, not assumed). Determinism is enforced through strict prompt instructions instead.
  - Updated 2026-09-11: AI extraction originally planned as Gemini; switched to Anthropic Claude per explicit decision.
  - Updated 2026-09-11: OCR originally planned as Tesseract; switched to Claude vision per explicit decision (better accuracy on real SBP scans: tables, stamps, multi-column layouts). This makes the OCR step AI-based too, which blurs "AI is not the source of truth" (section 4) more than classical OCR did. Mitigation: OCR stays a strictly separate call from interpretation — narrow, temperature 0, "transcribe exactly what is on this page, do not summarize or interpret" — its output (DocumentPage.raw_text) is still treated as the mechanical source-text layer that requirements must cite against, not as an AI opinion. Revisit if OCR transcription errors show up in the gold-standard dataset review.
  - Model: Claude Opus 5 (`claude-opus-5`) for both OCR and extraction, explicit decision 2026-09-11 (~2.5x the cost of Sonnet 5, chosen for accuracy on the interpretation/classification step, where a misread threshold has real consequences).
- Next regulators (SECP etc.) become new packs on the same core engine.
- Target users (later phases): banks, FinTechs (EMIs, PSPs, wallets, BNPL, digital lenders), insurance, corporates, professional services, regulators.

## 6. Tech stack (decided, do not change)

- Web frontend: Next.js + React + TypeScript + Tailwind (later phase)
- Main API: Node.js + Express — users, login, tasks, alerts, dashboards
- Engine: Python 3.11+ / FastAPI — OCR, AI extraction, verification, knowledge base, search, review queue
- Database: ONE PostgreSQL 18 + pgvector (originally planned as 16; updated 2026-09-11 to match the version already installed on the dev machine — no functional impact). Clear ownership: Python owns the regulation tables, Node owns the app tables (users, tasks, alerts). Nobody writes into the other's tables.
  - pgvector is deferred: no Windows prebuilt package exists, it needs Visual Studio Build Tools to compile. Not needed until Phase 2 (semantic search), so it will be installed and enabled then, not during initial setup.
- Repository: monorepo — apps/engine (Python), apps/api (Node), apps/web (Next)
- Python tooling: uv, SQLAlchemy 2.0 (Mapped style), Alembic migrations, Pydantic v2, pytest
- The engine is ONE service, not microservices. No Redis/Kafka/Celery until real scale requires it.

## 7. Data model direction (Phase 0)

Core regulation tables: Regulator, Document, DocumentVersion, DocumentPage,
Section, RegulatoryRequirement (immutable, stable_key + revision),
SourceCitation (page + char span proof), Obligation (canonical, tenant-free),
RegulatoryRelationship (AMENDS / REPLACES / PARTIALLY_REPLACES / etc.),
EntityType / ProductType / BusinessActivity (hierarchical lists),
ApplicabilityRule (INCLUDES/EXCLUDES scoping), RegulatoryChange (added/
modified/repealed/moved — backbone of impact analysis), ExtractionRun
(every AI job logged: model, version, prompt version — run-to-run
comparability), Review (human decisions with before/after snapshots).

App tables (Node-owned, later phase): Organization, User, Task, Alert.
Compliance tables (Phase 3+): Control, Evidence, ComplianceAssessment,
ObligationAssignment.

## 8. Roadmap

- Phase 0 (COMPLETE): v2 data model — 16 regulation tables, migration, seed data, 9 database tests that prove the integrity rules
  - Updated 2026-10-06: grew from 7 to 9 tests as Phase 2 added relationship/applicability constraints.
- Phase 1 (COMPLETE): extraction engine — Pydantic extraction contract, Claude prompt, OCR pipeline (pdf2image + Claude vision), source verification, 24-document real SBP corpus ingested and human-reviewed end to end (326 ACTIVE requirements)
- Phase 2 (IN PROGRESS, CURRENT): regulatory intelligence — relationships and the applicability engine are built, run against the full corpus, and human-reviewed (24 relationships, 333 applicability rules). Still open: versioning, search (full-text + semantic), change detection, document browser
- Phase 3: compliance engine — obligations workflow, controls, evidence, tasks, assessments, dashboards (Node side wakes up here)
- Phase 4: FinTech compliance packs (EMI/PSP/wallet/BNPL workflows)
- Phase 5: multi-regulator (SECP + others)
- Phase 6: public APIs, SupTech for regulators, multi-country

## 9. Quality gates

- The data model is not "done" until 100 hand-reviewed real clauses fit in it.
- Every schema change = Alembic migration, never manual edits.
- The 9 model tests must stay green at all times.
- Before scaling to hundreds of documents: the 20–30 doc benchmark corpus must pass end-to-end, including the hard cases (master circulars, partial amendments, tables, definitions, applicability-heavy documents).

## 10. How I want you to work

- Simple English in all communication, comments, and docs.
- Work in SMALL STAGES. After each stage, print a one-line confirmation and continue only if the check passed.
- If a command fails: stop, show the full error, explain the cause, propose a fix, wait for my approval. Never silently skip or work around a failure.
- Do not add features, files, or dependencies beyond what I ask for.
- Windows / PowerShell environment.
