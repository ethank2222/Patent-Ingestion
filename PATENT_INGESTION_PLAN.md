# U.S. Patent Intelligence Platform Plan (Full Scope, React + Flask, On-Demand AI Summaries)

## 1. Executive Feasibility Verdict
This is feasible and a strong product direction.

Main reason it is feasible:
- Public U.S. patent data is accessible through USPTO Open Data Portal (ODP) APIs and bulk datasets.
- Patent application full text is available in machine-readable XML formats.
- The UI behavior you want (browse all patents, filter, then summarize only selected patents) is straightforward and materially reduces LLM cost.

Main constraint to design around:
- You can only reliably cover **issued patents and published patent applications** in public feeds. You cannot cover all newly filed-but-not-yet-published applications because they are not publicly available yet.

## 2. What "Recently Filed" Means In Practice
For public data, "recently filed" should be represented as:
- Recently **published applications** (pre-grant publications).
- Recently **granted patents**.

Important legal/publication behavior:
- Publication generally occurs around 18 months from earliest claimed filing date, and publications occur weekly on Thursdays.
- Some application categories are exceptions to publication.

Product wording recommendation in UI:
- Use "Recent U.S. patent publications" and "Recent U.S. patent grants."
- Optionally show earliest filing date in each row so users still see filing recency.

## 3. Deep-Research Findings That Affect Architecture
### USPTO platform transition and access requirements
- ODP launched on **February 12, 2025** and replaced older distribution systems over time.
- PEDS was retired on **March 14, 2025**.
- BDSS was retired on **April 11, 2025**.
- ODP requires account-based access beginning **June 18, 2026**.
- ODP APIs require an API key.

Implication:
- Build an ingestion adapter layer that can tolerate endpoint, auth, and product migration changes.
- Track auth tokens/API keys in secure secret storage and monitor for failed auth patterns.

### Data availability and formats
- Patent application XML full text data is distributed in weekly files and includes rich sections.
- USPTO publishes XML DTD/version resources; parser must support multiple historical and current XML versions.

Implication:
- Implement a version-aware XML parser (by DTD/version), not a single rigid parser.
- Keep raw XML blobs in object storage for re-parsing when parser logic evolves.

### Publication cadence and filtering
- Published applications: weekly Thursday cadence.
- Official Gazette for grants: weekly Tuesday cadence.

Implication:
- Run daily incremental sync plus weekly reconciliation jobs (Thursday and Tuesday windows).

### PatentsView migration state
- PatentsView migrated to ODP on **March 20, 2026**, with temporary pauses to some legacy functions during transition.

Implication:
- Treat PatentsView-derived endpoints as optional enrichment, not single-source-of-truth.

## 4. Product Requirements (Exact UX You Requested)
## Core user flow
1. User opens web app.
2. User sees a table/feed of recent U.S. patents/publications with filters.
3. User filters by type and technical field.
4. User opens a specific patent detail page.
5. User clicks "Generate AI summary" (or summary auto-generates on first detail open if you prefer).
6. Backend runs summarization for that one patent, stores cached result, and returns it.
7. Subsequent views use cached summary unless source content changed.

## Token conservation requirement (hard requirement)
- Do **not** summarize all ingested patents.
- Ingestion stores metadata + source text only.
- Summarization runs **only on demand** for selected patent.

## 5. System Architecture (React + Flask)
## Frontend (React)
- `PatentListPage`
  - Virtualized table for performance.
  - Filters: date range, document type, CPC section/class, assignee, keyword.
- `PatentDetailPage`
  - Bibliographic metadata.
  - Claims/spec sections.
  - "Generate summary" button.
  - Streaming status and summary render.
- `SavedSummariesPage` (optional)
  - Recently generated summaries and reuse.

## Backend (Flask API)
- API service (Flask + Flask-RESTX/FastAPI-style organization if preferred).
- Worker service (Celery/RQ) for ingestion and summarization jobs.
- PostgreSQL for relational data.
- Redis for queue + cache metadata.
- Object storage for raw XML and intermediate parse artifacts.
- Optional pgvector for semantic search.

## Suggested service boundaries
- `collector` module: gets new publication identifiers and metadata.
- `document_fetcher` module: downloads XML/raw docs.
- `normalizer` module: canonical JSON sections.
- `summarizer` module: on-demand LLM pipeline.
- `api` module: web endpoints for React app.

## 6. Data Acquisition Strategy
## Source priority
1. USPTO ODP APIs and bulk datasets (authoritative primary source).
2. ODP bulk files for robust full-text backfill and reconciliation.
3. Secondary mirror (Google Patents public datasets) only as fallback/enrichment, not canonical record authority.

## Ingestion pattern
- Daily incremental:
  - Pull recent records by publication/grant date windows.
- Weekly reconciliation:
  - Re-check Thursday application publication and Tuesday grant windows.
- Backfill mode:
  - Configurable historical range to bootstrap database.

## De-duplication keys
- Primary: `publication_number`.
- Secondary: `application_number`.
- Preserve kind code/versioned document references.

## 7. Data Model (Full Scope)
## Core tables
- `patents`
  - `id`, `publication_number`, `application_number`, `kind_code`, `doc_type` (`application_publication` or `grant`)
  - `publication_date`, `filing_date`, `priority_date`
  - `title`, `abstract`, `assignee`, `inventors_json`, `cpc_codes_json`
  - `source_system`, `source_url`, `source_hash`, `ingested_at`, `updated_at`
- `patent_text_sections`
  - `patent_id`, `section_type` (`claims`, `description`, `background`, `summary`, etc.), `section_text`, `token_count_estimate`
- `summaries`
  - `id`, `patent_id`, `status` (`queued`, `running`, `completed`, `failed`)
  - `model_name`, `prompt_version`, `source_hash_at_generation`
  - `summary_markdown`, `summary_json`, `quality_score`, `generated_at`
- `summary_requests`
  - `id`, `patent_id`, `requested_by`, `requested_at`, `latency_ms`, `cache_hit`
- `embeddings` (optional initial phase)
  - `patent_id`, `embedding_type`, `vector`, `model_name`, `created_at`

## Indexes
- `publication_date`, `doc_type`, `assignee`, `kind_code`
- GIN index on CPC codes array
- Full text indexes for title/abstract/claims
- Unique constraints on publication identifiers

## 8. Flask API Contract
## Listing/filter endpoints
- `GET /api/patents`
  - Query params: `q`, `doc_type`, `cpc_prefix`, `assignee`, `from_date`, `to_date`, `page`, `page_size`, `sort`
- `GET /api/patents/{publication_number}`
  - Returns metadata + stored section excerpts (no LLM call).

## Summarization endpoints (on-demand)
- `POST /api/patents/{publication_number}/summaries`
  - Behavior:
    - If valid cached summary exists and source hash unchanged, return cached.
    - Else queue summarization job and return `job_id`.
- `GET /api/summaries/{job_id}`
  - Returns job status and output when complete.

## Admin/ops endpoints
- `POST /api/admin/ingest/incremental`
- `POST /api/admin/ingest/backfill`
- `GET /api/admin/health`

## 9. React UI Specification
## List page requirements
- Show: publication number, title, publication date, filing date (if present), type, top CPC, assignee.
- Filters:
  - Type: application publication vs grant.
  - Field: CPC section/class/subclass.
  - Date range.
  - Assignee.
  - Keyword.
- Sorting:
  - Publication date desc default.

## Detail page requirements
- Header with bibliographic metadata.
- Tabs: abstract, claims, description sections, AI summary.
- AI summary tab states:
  - Not generated.
  - In progress.
  - Completed with timestamp/model.
  - Failed with retry.

## 10. AI Summarization Pipeline (On Demand Only)
## Triggering
- Trigger only when user explicitly requests summary for a specific patent.
- Optional auto-trigger only on first detail view can be feature-flagged.

## Pipeline stages
1. Section extraction and token budgeting.
2. Claims-focused extraction (independent claims first).
3. Structured synthesis (JSON schema output).
4. Markdown rendering from structured JSON.
5. Citation anchors to source sections.

## Quality controls
- Enforce structured outputs (JSON schema).
- Require evidence fields for each major assertion.
- Reject incomplete or non-grounded outputs.
- Retry with fallback prompt/model if validation fails.

## 11. Token And Cost Optimization Plan
## Hard controls
- No background summarization of entire corpus.
- Max one active summary per patent per prompt/model version.
- Server-side cache keyed by:
  - `publication_number + model + prompt_version + source_hash`.

## Prompt design controls
- Put static instructions first and dynamic patent text last to maximize prompt caching benefits.
- Use compact extracted sections first (abstract + independent claims + summary section) before full description expansion.
- Cap output tokens by summary mode:
  - `brief`, `standard`, `deep`.

## Compute controls
- Use lower-cost model for extraction steps, stronger model for final synthesis when needed.
- Batch non-urgent enrichment tasks (embeddings/offline evaluations), not user-triggered summaries.

## 12. Ingestion And Parsing Details
## Parser requirements
- DTD/version aware parsing for Patent Application XML and Grant XML.
- Normalize to canonical section names despite source version differences.
- Preserve references to figures/tables/equations when present.

## Failure handling
- Retry transient HTTP failures with exponential backoff.
- Quarantine malformed XML for manual/parser updates.
- Maintain dead-letter queue for repeated failures.

## 13. Observability, Security, And Compliance
## Observability
- Metrics:
  - ingestion success rate
  - records/day
  - summary request volume
  - summary cache hit rate
  - median/P95 summary latency
  - average tokens per summary request
- Logging:
  - request IDs from UI to worker for traceability.

## Security
- Store API keys/secrets in secret manager.
- Rate-limit public endpoints.
- AuthN/AuthZ for admin ingest endpoints.

## Compliance
- Honor USPTO terms, authentication, and usage/rate requirements.
- Show disclaimer: "AI summary is informational, not legal advice."

## 14. Delivery Plan (Milestones)
## Phase 0: Setup (Week 1)
- Flask app skeleton, React app skeleton, Postgres, Redis, worker.
- Env/secrets and deployment baseline.

## Phase 1: Data Ingestion (Week 2)
- ODP connector + incremental sync.
- Bulk backfill pipeline.
- Canonical schema and parser.

## Phase 2: Browsing UX (Week 3)
- Patent list API + filters.
- React list/detail pages.

## Phase 3: On-Demand Summaries (Week 4)
- Summary job queue and status API.
- Structured output validation and caching.

## Phase 4: Hardening (Week 5)
- Error handling, retries, metrics dashboards.
- Cost guardrails and prompt cache optimizations.

## Phase 5: Evaluation And Launch (Week 6)
- Human evaluation rubric.
- Performance/cost tuning.
- Launch checklist and runbooks.

## 15. Acceptance Criteria
- User can browse and filter recent U.S. publications/grants without triggering LLM calls.
- Summary is generated only when user requests it on a specific patent.
- Re-opening same unchanged patent summary returns cached result.
- Ingestion and parsing sustain weekly publication flow with recovery from transient failures.
- Output includes clear technical explanation plus claim-grounded evidence.

## 16. Risks And Mitigations
- ODP/API changes and migrations:
  - Mitigation: adapter pattern, schema versioning, reconciliation jobs.
- Data quality drift:
  - Mitigation: source hashing, weekly re-ingest checks, anomaly alerts.
- LLM hallucinations:
  - Mitigation: evidence-required schema + validation + retries.
- Token/cost spikes:
  - Mitigation: on-demand-only summaries, caching, output caps, model tiering.

## 17. Immediate Build Tasks
1. Scaffold Flask backend (`api`, `worker`, `collector`, `normalizer`, `summarizer` modules).
2. Scaffold React frontend with list/detail routes and filter state.
3. Implement `GET /api/patents` with pagination + filter query grammar.
4. Implement on-demand summary job API and summary cache key strategy.
5. Add parser test fixtures for current USPTO XML versions.
6. Add observability dashboard for ingestion and summary token metrics.

## 18. Sources (Research Basis)
- USPTO ODP launch announcement (February 12, 2025): https://www.uspto.gov/about-us/news-updates/uspto-launches-new-open-data-portal-easy-quick-access-data
- PEDS retirement (March 14, 2025): https://www.uspto.gov/system-status/20250212-patent-examination-data-system-peds-retirement
- BDSS retirement (April 11, 2025): https://www.uspto.gov/subscription-center/2025/bulk-data-storage-system-retiring-soon
- ODP registration requirement announcement (effective June 18, 2026): https://www.uspto.gov/about-us/news-updates/uspto-open-data-portal-require-registration-access-beginning-june-18-2026
- ODP API metadata and key requirement (data.gov catalog): https://catalog.data.gov/dataset/open-data-portal-odp-api-version-2-3
- MPEP publication timing and exceptions (Thursday publication cadence): https://www.uspto.gov/web/offices/pac/mpep/s1120.html
- Official Gazette weekly cadence (Tuesday): https://www.uspto.gov/learning-and-resources/official-gazette
- USPTO XML Resources (DTD/version references): https://www.uspto.gov/learning-and-resources/xml-resources
- PatentsView migration bulletin (March 20, 2026): https://content.govdelivery.com/accounts/USPTO/bulletins/40e8c67
- Google Patents public dataset reference repo (secondary/fallback context): https://github.com/google/patents-public-data
- OpenAI prompt caching guide: https://developers.openai.com/api/docs/guides/prompt-caching
- OpenAI structured outputs guide: https://developers.openai.com/api/docs/guides/structured-outputs
