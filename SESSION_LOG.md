# Regulation OS — Session Log

A record of the working session that took Regulation OS from an empty folder
through Phase 0, all of Phase 1, and the start of Phase 2 (relationships and
applicability). Not a raw transcript — this captures the decisions, what got
built, what broke and got fixed, and where things stand.

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

## 7. Closing out Phase 1: 8 more documents, hard cases, and a real batch review

The user supplied 8 more real SBP documents, specifically including a master
circular and table-heavy ones, to close the gap flagged above.

**A real bug found mid-batch**: one page (`BC_CPD_Circular_No_08.pdf`) was an
unusually tall scanned page (~46 inches), rendering past the Anthropic API's
8000px image-dimension limit and crashing the batch. Fixed by clamping any
oversized render to the limit, preserving aspect ratio, rather than failing
the whole batch on one page.

**A second real bug**: `max_tokens=8192` on the extraction call turned out
too low for genuinely dense pages once real master circulars and table-heavy
documents were in the corpus — the JSON response was getting cut off
mid-string. Raising it to 32000 hit the Anthropic SDK's own non-streaming
timeout guard (it refuses anything estimated to exceed 10 minutes); settled
on 20000, the highest safe non-streaming value.

**Twice, the batch also hit real Anthropic API credit exhaustion mid-run** —
not a code bug, but handled by verifying no partial/corrupt data was left
behind each time (the uncommitted transaction rolled back cleanly) before
resuming once credits were restored.

Result: **24 documents total**, including 2 genuine master circulars and 46
new `TABLE_DATA` clauses (versus a handful before) — the corpus-size and
hard-case gates from Phase 1's quality gate are both satisfied now.

### The batch review, in detail

The user reviewed the resulting 155 new requirements document-by-document
and sent back a long, itemized pass. Two things stood out in applying it:

- **A real workflow bug caught by verifying, not trusting, the result**:
  after rejecting 6 duplicate/fragment rows, a subsequent bulk "approve
  everything still DRAFT" step silently reactivated those same 6 rows --
  `reject_requirement()` intentionally leaves status as `DRAFT` (rejected
  items stay `DRAFT` forever by design), and nothing was checking for a
  prior rejection before approving. Caught immediately by re-querying the
  actual data after the script ran, reverted the 6 rows back to `DRAFT`
  with a Review row explaining the correction, and fixed
  `approve_requirement()` to refuse reactivating anything last `REJECTED`
  unless explicitly overridden. Two new tests lock this in.
- Two items the user flagged as "possibly not in the source, verify" turned
  out to be genuinely present — confirmed directly against our own stored
  OCR citations (both exact matches, score 1.0), not by re-reading the PDF.
  Approved rather than rejected, with the reasoning shown back to the user.

**Final state after this round**: 326 `ACTIVE` requirements, 153 `ACTIVE`
obligations, 41 `DRAFT` (rejected, preserved for audit), 20 `SUPERSEDED`.

One item stayed genuinely unresolved: whether "SBP may also issue specific
instructions" should stay `EXCEPTION` (current state) or revert to `RULE` --
a follow-up message read as ambiguous rather than a clear reversal, left as
`EXCEPTION` pending confirmation.

---

## 8. Phase 2: relationships and applicability

With Phase 1 closed out, work moved to Phase 2 per the roadmap, starting
with **Relationships** (the amendment/supersession chain) rather than
**Applicability**, reversing the original priority order — reasoning: we
already had real, reviewed evidence sitting unused (`AMENDMENT_TEXT` clauses
naming exactly what they supersede), making it more bounded and immediately
provable than applicability's more open-ended taxonomy work.

### Relationships (the amendment resolver)

**A design assumption that would have made the feature produce nothing**:
the original `RegulatoryRelationship` schema required both documents in a
relationship to exist in our own corpus. Checking first: zero of 32 real
`AMENDMENT_TEXT` clauses reference anything we'd actually ingested — every
reference points to an older circular outside our 24-document corpus.
Extended the schema before writing any extraction code: `to_document_id`
became nullable, paired with `external_reference_text` for out-of-corpus
references (a new check constraint enforces exactly one is set), plus
`confidence_extraction`, `status` (`DRAFT` by default), and traceability
fields — the same AI-derived/needs-review pattern as everything else.

**Fuzzy string matching was tried and found unsafe** for resolving document
references: `rapidfuzz`'s `token_set_ratio` scored "BPRD Circular No. 08" vs
"No. 10" at 95% similarity — *higher* than a genuine cross-document match
scored in testing — because circular reference strings share nearly every
word except the one that actually matters. Replaced with exact matching on
a parsed `(department code, circular number, year)` tuple, which correctly
refuses to guess when genuinely ambiguous (proven against real production
data: two of our own documents are legitimately ambiguous under this
scheme, and the resolver correctly declines rather than picking one).

**A real extraction-quality bug found by inspecting the first real run's
output, not just trusting the row count**: feeding the extraction the
narrow `SourceCitation` quote instead of the already-resolved
`requirement_text` produced vague, unresolved references like "the above
referred circular" instead of the actual circular name Phase 1's own
extraction had already figured out from page context. Fixed the input
source, deleted the 19 flawed unreviewed rows, and re-ran clean: 24
relationships extracted. Real proof it works: the eCIB master circular's
full 7-document supersession chain, correctly split from one sentence
naming six items (one compound reference parsed into two separate
relationships).

Also extended `Review` to support `relationship_id` as a third target
(alongside `requirement_id`/`obligation_id`), with `approve_relationship()`/
`reject_relationship()` mirroring the requirement versions exactly — the
user was explicit that reviewing 24 AI-extracted relationships is their
call, not something "do what you think is best" extends to.

### Applicability (in progress)

**A real taxonomy gap found before writing any extraction code**: scanning
actual entity mentions across the 367 real requirements found "DFI"/"DFIs"
71 times — the second most common entity mention after "Bank"/"Banks" — and
it didn't exist anywhere in the seeded `EntityType` taxonomy. Added it
first. `ApplicabilityRule` was extended with the same resolution-fallback
pattern as relationships (per-dimension `_text` fallback columns for
entity/product/business-activity, each constrained to never be set
alongside its resolved `_id`), plus the same confidence/status/traceability
fields, and `Review` was extended again for a fourth target type.

**Validated on a small real sample before committing to the full run** (the
same discipline as relationships) and found two real quality issues:
compound entities ("banks'/DFIs'") were inconsistently extracted as one
unresolvable blob instead of being split; and "banks must submit their CAR
returns" produced `business_activity: 'submit their CAR returns'` — an
action, conflating Applicability with Obligation. Fixed the prompt for
both; re-running the same sample went from 4/17 resolved dimensions to
16/25, and the noise disappeared. The same real-evidence check also
surfaced two smaller taxonomy gaps (NBFC, Modaraba) and one abbreviation
needing a resolver alias rather than a new row (MFB → the existing
`MICROFINANCE_BANK`).

**Where this stood when the session paused**: the full run (253
requirements) was started and hit real Anthropic API credit exhaustion
partway through. This surfaced one more real robustness bug worth noting:
both extraction scripts only committed once at the very end, so the entire
run's already-completed work would have been silently discarded on retry.
Fixed to commit per-document instead — a mid-run failure now only loses the
current document's in-flight work, and re-running picks up exactly where it
left off via the existing idempotency check. Not yet re-run at full scale;
needs API credits restored (the user's action) to resume.

---

## 9. Phase 2 review: 24 relationships, 333 applicability rules

With API credits restored, the full applicability run (253 requirements)
completed, and both queues — 24 relationships, 333 applicability rules —
were ready for human review. Raw CLI review (one command per item) wasn't
going to scale, so the same pattern used for the 367-requirement review was
repeated: a second published review page
(`templates/review2_page.html`), grouped by document → requirement, nested
relationships and applicability rules shown with resolved/unresolved status
and confidence inline, filterable by search / unresolved-only /
relationships-only / applicability-only.

### 9.1 A review-tooling bug caught before acting on it

The three filter views (Unresolved Only / Relationships Only / Applicability
Only) are overlapping filters on the same underlying rows, not separate
copies — but the user's review pass, done view-by-view, read an item
appearing in two filtered views as a duplicated database row and flagged
~12 relationships and 7 applicability rules as "duplicates to reject,"
while *also* approving those same IDs elsewhere in the same review (by
content, correctly). Checked before acting: every flagged ID exists exactly
once in the underlying data. Resolved the contradiction by honoring
whichever call was backed by actual content reasoning — approve for the 12
relationships (the user's own note on them: "not errors... acceptable"),
reject for 7 applicability rules where a specific, separate low-confidence/
exception argument had been made (not just the view-overlap artifact).

### 9.2 Taxonomy extension, backed by real counts

The user's review flagged ~30 applicability rows stuck unresolved on
taxonomy gaps, not wrong extractions (e.g. "branches," "Participants,"
"Digital Banks," "auditors," "Raast"). Before adding anything, queried
actual mention counts across the extracted data to confirm each was real,
not a one-off: 11 mentions of branch-level terms, 10 of Raast-participant
terms, 4 of "Islamic banking subsidiary," 2 each of "Digital Banks" and
"auditors." Added 7 entity types (Branch, Raast Participant, Digital Bank,
External Auditor, Islamic Banking Subsidiary, Currency Chest, Sub-Chest)
and 6 product types (Raast, MTS, TTS, DDS, Claim Notes, Clearly Payable
Defective Notes) — the three-letter cash-management codes (MTS/TTS/DDS)
were deliberately named exactly as extracted rather than guessing their
expansion, since the source text never spells them out. Added a
`_PRODUCT_ALIASES` dict (products previously had no alias mechanism, only
entities did) and fixed a real normalizer bug along the way: the plural-
stripping logic turned "branches" into "branche", not "branch," silently
failing every branch-related match until caught.

Re-ran the backfill (no new AI calls, pure re-resolution against the
grown taxonomy): 51 previously-unresolved rows resolved. Two items stayed
deliberately unresolved rather than force a guess — an overly specific
product phrase and a business-activity dimension with no real taxonomy fit.

Also added `correct_relationship()` to `scripts/review.py`: unlike
`RegulatoryRequirement`, `RegulatoryRelationship` has no
`stable_key`/`revision_number` — it isn't immutable — so a correction edits
`relationship_type` in place and activates, recording one `CORRECTED`
review, rather than the append-a-revision pattern requirements use.

### 9.3 A second, more interesting mistake — this time on both sides

After applying ~314/333 applicability decisions, 19 rows remained
unaccounted for, all tied to a document called "BPRD 14 (Letter)" — the
user hadn't reviewed them and said so plainly when asked. The user then
described what they expected that content to be, from memory of the source
PDF: Core Principles compliance-assessment instructions (audit firm
engagement, compliance grading I–IV, a 15/30-day deadline pair). Querying
the actual stored requirement text before accepting that description
showed it didn't match at all — "BPRD 14 (Letter)" is a Basel III / Capital
Adequacy implementation letter (same family as the BSD/IBD superseding
relationships already reviewed), not the Core Principles letter. That
content lives in the *other* "BPRD 14" (no suffix), which had already been
reviewed. Presented the real 10 clauses + 19 applicability rows instead of
the remembered ones; the user reviewed the actual content and approved all
of it. Worth recording precisely because it went both ways in one exchange:
first a tooling-side misreading (the view-overlap "duplicates"), then a
memory-side misattribution (the wrong document's content) — both caught by
checking the database directly rather than trusting either side's
recollection.

**Final state**: 24/24 relationships `ACTIVE`. 326/333 applicability rules
`ACTIVE`, 7 `DRAFT` (the user's deliberate rejections — stay `DRAFT`
forever by design, never silently reactivated).

---

## 10. Where things stand

**Phase 0**: complete. **Phase 1**: complete against its own quality gates
(24-document corpus, master circulars and table-heavy content included,
326 `ACTIVE` requirements with real human review behind every one).
**Phase 2**: relationships and applicability both built, run against the
full corpus, and fully human-reviewed (24/24 relationships, 326/333
applicability rules active; 7 deliberately rejected).

**Still open:**

- The "SBP may also issue specific instructions" classification question
  from Phase 1, still unconfirmed.
- `RegulatoryChange` (change detection), search, and the document browser
  — the remaining pieces of Phase 2 per the roadmap — not started.
- The Node/API side remains an intentional `/health` stub, correctly so per
  the roadmap (it wakes up in Phase 3).

---

## 11. Repository made public

The repo (`github.com/kfxgit/regulation-os`) was switched from private to
public. Before anything further was pushed, a sweep checked for anything
that shouldn't be exposed: no `.env` file, API key, or database credential
was ever committed (checked the current tree and the full history, not
just `git status`); no source PDFs or other large binaries were ever
committed; `.gitignore` had correctly kept all of that out from the start.

One real finding: a personal email address was hardcoded in
`apps/engine/pyproject.toml`'s `authors` field (a leftover default from
`uv init`), and the same address is separately baked into every commit's
author metadata across the whole git history — the latter is permanent
short of a disruptive history rewrite, which wasn't done. Replaced the
`pyproject.toml` copy with a GitHub-provided noreply address
(`{id}+{username}@users.noreply.github.com`) so no *new* file repeats it.
Added a `LICENSE` (all-rights-reserved / proprietary notice — the repo is a
product, not an open-source library) and updated `README.md`, which had
drifted badly out of date (still describing Phase 1 as "next," with all of
Phase 1 and most of Phase 2 actually complete).

---

*Generated as a session record at the user's request, updated as the work
continued. Reflects the state of the project as of 2026-10-06.*
