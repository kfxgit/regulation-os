# Regulation OS — Session Log

A record of the working session that took Regulation OS from an empty folder
through Phase 0 and the core of Phase 1, including the first real batch of
SBP circulars reviewed end to end. Not a raw transcript — this captures the
decisions, what got built, what broke and got fixed, and where things stand.

---

## 0. Briefing

The session began with a full project briefing saved as `CLAUDE.md` in the
repo root. Core points:

- **What we're building**: an AI-powered Regulatory Intelligence & Compliance
  Platform that turns regulatory documents into structured, verified,
  queryable requirements, then into real compliance tracking.
- **The chain**: REGULATION → REQUIREMENT → APPLICABILITY → OBLIGATION →
  CONTROL → EVIDENCE → COMPLIANCE → IMPACT ANALYSIS.
- **Non-negotiable principles**: document ≠ rule; requirement ≠ obligation;
  AI is not the source of truth (every requirement traces to exact source
  text); no silent publishing (AI output is always DRAFT until a human
  approves); no silent defaults (missing values stay empty and flagged,
  never 0/false); nothing is deleted (amendments append revisions); five
  separate confidence scores, never one generic score.
- **Scope**: start with State Bank of Pakistan (SBP) documents as the first
  regulatory pack.
- **Tech stack (as briefed)**: Next.js/React/TS frontend (later), Node/Express
  API (later), Python/FastAPI engine (now), one PostgreSQL 16 + pgvector
  database, monorepo (`apps/engine`, `apps/api`, `apps/web`), uv + SQLAlchemy
  2.0 + Alembic + Pydantic v2 + pytest.
- **Working style**: simple English, small stages with a confirmation after
  each, stop and explain on any failure (never silently work around it),
  no scope creep, Windows/PowerShell environment.

---

## 1. Setup (Stages 1–5)

| Stage | What happened |
|---|---|
| 1 | Repo skeleton: `apps/engine`, `apps/api`, `apps/web`, `.gitignore`, `README.md`, `git init` |
| 2 | Python engine scaffold: `uv init`, FastAPI `/health`, Alembic initialized |
| 3 | Node API scaffold: Express `/health` |
| 4 | Database: local Postgres, `regos` database created |
| 5 | Sanity check: engine + API + DB all reachable |

**Deviations found and recorded (not silent):**

- **PostgreSQL 18** installed, not 16 as briefed — used what was actually on
  the machine, updated `CLAUDE.md` rather than forcing a downgrade.
- **pgvector deferred** — no Windows prebuilt package exists, needs Visual
  Studio Build Tools to compile from source. Not needed until Phase 2
  (semantic search), so left uninstalled for now.

---

## 2. Phase 0 — the 16-table data model

Built the full regulation schema in SQLAlchemy 2.0 (Mapped style):

- **Taxonomy**: `Regulator`, `EntityType`, `ProductType`, `BusinessActivity`
- **Documents**: `Document`, `DocumentVersion`, `DocumentPage`, `Section`
- **Core chain**: `RegulatoryRequirement` (immutable, `stable_key` +
  `revision_number`), `SourceCitation`, `RegulatoryRelationship`,
  `RegulatoryChange`, `ApplicabilityRule`
- **Obligations**: `Obligation` (same revision pattern, tenant-free)
- **Workflow**: `ExtractionRun`, `Review`

**Two migrations**: the schema itself, then a second migration adding real
Postgres triggers — not just application discipline — for two of the
non-negotiable principles:

1. **Immutability**: a `BEFORE UPDATE` trigger on `regulatory_requirement`
   blocks any change to content columns; only `status` and
   `superseded_by_id` may move. Amendments and corrections both work by
   inserting a new revision and superseding the old row, never editing it.
2. **No citation = unpublishable**: a trigger blocks `status → ACTIVE`
   unless at least one `SourceCitation` row already exists for that
   requirement.

**Seed data**: SBP as the first `Regulator`, plus starter `EntityType` /
`ProductType` / `BusinessActivity` taxonomies.

**7 integrity tests**, each proving one non-negotiable principle by actually
trying to violate it and checking the database rejects it:
requirement immutability, `stable_key`+`revision` uniqueness,
citation-required-for-ACTIVE, no silent defaults on high-risk fields,
supersede-preserves-old-row, five independent confidence scores, and
review-links-to-exactly-one-target.

All 16 tables verified against the real `regos` database; all 7 tests green.

---

## 3. Phase 1 — the extraction engine

### 3.1 Model and tooling decisions (made explicitly, recorded in CLAUDE.md)

- **AI extraction switched from Gemini to Anthropic Claude** — explicit
  decision, user-requested.
- **OCR switched from Tesseract to Claude vision** — better accuracy on real
  SBP scans (tables, stamps, multi-column layouts) than classical OCR, at
  the cost of blurring "AI is not the source of truth" slightly. Mitigated
  by keeping OCR a strictly separate, narrow "transcribe only" call from
  interpretation.
- **Model: Claude Opus 5** for both OCR and extraction (not Sonnet 5) —
  explicit decision, chosen for accuracy on the classification/interpretation
  step where a misread threshold has real consequences, despite ~2.5x the
  cost of Sonnet 5.

### 3.2 What got built

- **Pydantic extraction contract** (`app/extraction/schema.py`):
  `ExtractedRequirement` / `ExtractedObligation` / `PageExtractionResult`.
  `extra="forbid"`, no defaults on confidence or high-risk fields — Claude
  must supply them explicitly or validation fails loudly.
- **PDF → images** (`app/extraction/pdf_pages.py`): pdf2image + Poppler
  (installed manually, no official Windows package — prebuilt binaries from
  `oschwartz10612/poppler-windows`).
- **OCR** (`app/extraction/ocr.py`): a narrow, low-effort, transcribe-only
  Claude vision call, deliberately separate from interpretation.
- **Extraction** (`app/extraction/extract.py`): the structured,
  high-effort Claude call using `client.messages.parse(output_format=...)`.
- **Source verification** (`app/extraction/verification.py`): fuzzy-match
  (rapidfuzz) locates the cited quote in the page's raw text and scores the
  match — this produces `confidence_source_match`, computed by code, never
  self-reported by the AI.
- **Pipeline** (`app/extraction/pipeline.py`): ties OCR → extraction →
  verification → persistence together. Everything lands as `DRAFT`.
- **Document metadata auto-extraction** (`app/extraction/metadata.py`):
  reads a document's own first page for title/reference/date/type instead of
  requiring them typed in by hand — built once batch size made manual entry
  impractical.
- **CLIs**: `scripts/ingest.py` (one file), `scripts/batch_ingest.py` (a
  whole folder, idempotent by content hash), `scripts/review.py`
  (`approve-all`, `reject-document`, plus `approve_requirement` /
  `reject_requirement` / `correct_requirement` as library functions).

### 3.3 Real bugs found and fixed along the way

- **`temperature` parameter removed from the Anthropic API entirely** as of
  SDK 1.5.0 — discovered by inspecting the actual SDK call signature rather
  than trusting a stale assumption. Code and `CLAUDE.md` both updated.
- **Opus 5 runs extended thinking by default** — `response.content[0]` is
  often a `ThinkingBlock`, not text. Fixed `transcribe_page()` to find the
  text block by type instead of assuming its position; would have crashed
  in production.
- **`contains_high_risk_language` / `high_risk_notes` were computed by
  Claude but never persisted** — found while reviewing the very first real
  ingestion. The extraction contract had the fields; the pipeline silently
  dropped them. Added the missing columns + migration, wired them through,
  re-ingested cleanly rather than guessing a backfill value.
- **`correct_requirement()` sequencing bug**: inserting a corrected revision
  with `status=ACTIVE` directly fails the citation-required trigger, since
  its own `SourceCitation` doesn't exist yet at insert time. Fixed: insert
  as `DRAFT`, add the citation, then flip to `ACTIVE`.
- **Enum snapshot inconsistency**: `str(enum_instance)` gives
  `"RequirementStatus.DRAFT"` for a fresh object but plain `"DRAFT"` for one
  reloaded from the DB — the same value serializing two different ways in
  Review snapshots depending on ORM object staleness. Fixed by normalizing
  through the enum constructor instead of `str()`.

---

## 4. First real document: BPRD Circular No. 01 of 2019

The user's first real SBP PDF (Basel Capital Adequacy Framework — lowering
risk weight on Low Cost Housing Finance) went through the full pipeline:

- 4 requirements extracted, 3 obligations, all citations exact matches
  (score 1.0), numbers (35% / 25%) preserved correctly in both the citation
  and the paraphrased requirement text.
- One judgment call (clause 1's classification, `RULE` vs `AMENDMENT_TEXT`)
  reviewed and confirmed by the user.
- Formally approved via `scripts/review.py` — the first real `Review` rows
  recorded, reviewer identified by the user's own email.

This proved the whole loop end to end: **PDF → OCR → extraction →
verification → human review → ACTIVE in the knowledge base.**

---

## 5. Batch of 15 more circulars

The user supplied 15 more real SBP documents. Before running the batch, a
naming-pattern check surfaced several files that looked like near-duplicates
(same reference number, different sizes) — the user chose to ingest all of
them as separate documents rather than have Claude guess which to drop.

**Batch result**: 208 DRAFT requirements, 188 obligations, 113 flagged
high-risk, **zero** low-confidence citations, **zero** numeric mismatches
between citation text and paraphrased requirement text (checked
programmatically across all 208).

### 5.1 The review page

Built as a published Artifact (`templates/review_page.html`, data injected
at publish time) — a design-considered review tool (IBM Plex type family,
a palette grounded in SBP's own circular branding, muted categorical badges
per clause type, amber reserved strictly for the high-risk flag), not a
generic dashboard. Filterable by search / clause type / high-risk-only,
with a per-browser "mark reviewed" checkbox for the user's own progress
tracking (never the system of record — that's always the `Review` table).

### 5.2 The duplicate-document investigation

The user's first review pass flagged several groups as duplicate
extractions. Investigating before acting turned up more than expected:

- **"BPRD Circular No. 08" was not a duplicate at all** — three genuinely
  different real circulars (Liquidity Standards / CAR Returns Submission /
  Retail Portfolio Limits) that happen to share a number. Not touched.
- **`BPRD_14_Letter__merged.pdf`** (88 requirements) turned out to be a
  13-page compilation bundling ~9 *other* circulars' content, mislabeled
  under one document identity — not a more-complete version of the 10-req
  standalone letter.
- **`DI_SD_merged.pdf`** (25 requirements) turned out to be the Raast
  circular (14 reqs) plus the PRISM+ circular (11 reqs) concatenated under
  the Raast title, burying an entire separate circular under the wrong
  identity.

The user's final instruction reversed the initial plan: **keep the merged
files as authoritative, reject the standalone files whose content is now
redundant with them** (the opposite of what "keep the more complete file"
would suggest, but correct for these specific documents). One clause (*"SBP
may also issue specific instructions..."*) existed only in the standalone
file being rejected, with no counterpart in the merged version — flagged and
individually corrected + reactivated rather than silently lost.

**Rejected** (stay `DRAFT` forever, never deleted, Review row records why):
`BPRD_14_Letter_.pdf` (10 reqs), `DI_SD_Circular_No_1 (1).pdf` (15 reqs),
`DI_SD_Circular_No_1.pdf` (11 reqs) — 36 requirements total.

### 5.3 Reclassification corrections

Built `correct_requirement()` — the `CORRECTED` review path: creates a new
revision (same `stable_key`, `revision_number + 1`) with the fix applied,
supersedes the old row, carries obligations forward, activates the new
revision. Same append-a-revision pattern used for regulatory amendments,
reused for human corrections.

**20 corrections applied**, each backed by the user's stated reasoning:

- LCR definition (×2 instances) and NSFR definition (×2 instances):
  `RULE` → `DEFINITION`
- "For measurement of liquidity risk..." preamble: `RULE` → `PROCEDURE`
- "SBP pays 1Y USD LIBOR minus 50bps": `RULE` → `DEFINITION` (SBP's own
  commitment, not a rule imposed on banks)
- "Comply with immediate effect": `RULE` → `PROCEDURE`
- "Non-compliance may lead to restrictions": `RULE` → `EXCEPTION`
- "SBP may also issue specific instructions": `RULE` → `EXCEPTION`
  (reactivated individually, see above)
- "All other instructions remain unchanged": standardized to
  `AMENDMENT_TEXT` across 11 instances spanning 9 documents

### 5.4 Final approval

After the user's exhaustive document-by-document sign-off covering every
remaining item across all 15 documents, the remaining 153 DRAFT
requirements were approved in bulk.

**Final state**: 177 `ACTIVE` requirements, 153 `ACTIVE` obligations, 35
`DRAFT` (rejected duplicates, preserved for audit only), 20 `SUPERSEDED`
(pre-correction revisions), 394 total `Review` rows.

---

## 6. GitHub

A private repo was created and the local history pushed:
[github.com/kfxgit/regulation-os](https://github.com/kfxgit/regulation-os).
GitHub CLI (`gh`) was installed and authenticated (device-code flow) since
no credentials existed on the machine beforehand; `gh auth setup-git` was
needed afterward to get plain `git push` working through the same
credentials.

---

## 7. Where things stand

**Phase 0**: complete. **Phase 1 core engine**: complete and proven against
16 real documents, not just synthetic text.

**Genuinely still open, per CLAUDE.md's own quality gates:**

- The 20–30 document benchmark corpus should include the *hard cases* —
  master circulars, real tables, applicability-heavy documents. Across the
  16 documents processed so far, none was a true master circular, and only
  a handful of `TABLE_DATA` clauses appeared. Worth deliberately sourcing a
  document of that shape before calling Phase 1 fully validated.
- One unresolved item from the user: whether "SBP may also issue specific
  instructions" should stay `EXCEPTION` (current state) or revert to
  `RULE` — a follow-up message read as ambiguous rather than a clear
  reversal, so it was left as `EXCEPTION` pending confirmation.
- Phase 2 (applicability engine, relationships, versioning, search, change
  detection, document browser) has not started.

---

*Generated as a session record at the user's request. Reflects the state of
the project as of 2026-09-15.*
