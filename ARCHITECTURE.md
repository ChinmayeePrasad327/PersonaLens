# PersonaLens 2.0 — Architecture and Milestone Plan

**Status:** proposal for review, revision 3, 2026-11-12. Nothing in this document is implemented yet. See `AUDIT.md` for the current state of the code.

**What v2.0 is:** a small free-tier demo, not a public launch. One person (or a handful of invited users) can upload a PDF, have it processed, and ask grounded questions about it with validated page citations. Everything runs on free tiers with no payment method, card, billing account or paid plan required at any step. Cold starts, paused services, quota limits and temporary unavailability are expected and are shown honestly in the UI. The README also documents a local demo path (uvicorn plus the Vite dev server, pointed at a free Supabase project) for interviews when the hosted demo is asleep or out of quota.

## 1. Principles

- **One journey, done well:** upload PDF → process → retrieve relevant passages → ask → grounded answer with page citations. Anything else is a [future improvement](#12-future-improvements-not-in-v20).
- **Measure before claiming.** No capacity, latency or memory figure is stated as fact until it has been measured on the real free configuration. Figures in this document marked *estimate* are planning inputs only.
- **Simplify instead of paying.** If a benchmark fails on the free tier, the architecture gets simpler. No paid upgrade is ever the fix.
- **Modular monolith.** One FastAPI service and one React app, with no queues, Redis or microservices. Existing modules move into `backend/app/` with `git mv` to keep their history.
- **Supabase is the source of truth.** Anything in process memory, such as loaded models or cached vectors, is disposable and is rebuilt on demand.
- **No resource is "free".** LLM tokens are the scarcest resource, but OCR, embeddings, reranking, search, database rows, storage and bandwidth all cost CPU, RAM, disk or quota. Each one is bounded and measured.

## 2. v2.0 scope

| In v2.0 | Notes |
|---|---|
| Auth and user isolation | Supabase Auth: register, login, logout, protected routes, profile. Every file, chunk, conversation, message and citation is scoped to the authenticated user. |
| PDF management | Upload one PDF at a time with validation and progress, list, view, delete, processing status, and **Retry** on failure. |
| Extraction | pdfplumber text per page. OCR fallback is bounded by page count, DPI and time (§5). |
| Chunking | Page-aware, sentence-aware, overlapping chunks carrying `document_id`, `filename`, `page_start`, `page_end`, `chunk_id` and `text`. |
| Retrieval | Low-resource embeddings plus Postgres full-text keyword search, fused with Reciprocal Rank Fusion (RRF). Cross-Encoder reranking is **off by default** and turned on only if the benchmark shows it fits (§6). |
| Grounded Q&A | One document at a time. Answers cite only passages actually supplied, and the backend validates every citation. "Not found in this document" when unsupported. |
| Conversation history | Saved per document. New and delete conversation. Follow-ups are resolved deterministically, with no extra LLM call (§7). |
| Personas | Four fixed compact prompt presets: **Beginner, Exam Preparation, Researcher, Professional**. Their prompt tokens are counted in the budget. |
| Quota visibility | Usage meter, clear quota and "AI unavailable" states, admin kill switch. Viewing, metadata and local search keep working when AI is off. |
| Frontend | React + TypeScript + Vite + Tailwind. Landing page, auth, library, workspace (PDF viewer + Q&A + citations), settings and usage. |
| Answer export | Client-side "Copy" and "Download as Markdown" for a single answer with its citations. No server work. |

Everything else (multi-document chat, collections, custom personas, briefs, summaries, quizzes, flashcards, comparison, research assistant, DOCX/CSV/PDF export, and a fallback provider) is listed in §12 with its added cost.

## 3. System overview

```
 React (Vercel Hobby)               FastAPI (Render Free)                       Supabase Free
 ────────────────────               ─────────────────────                       ─────────────
 supabase-js: auth only ─login──▶                                               Auth
       │ user JWT
       ▼
 Axios ─ Bearer JWT ───────────▶  api/ ─ core/auth: verify JWT → user_id
                                    │      core/quota: global + per-user token ledger, kill switch
                                    ▼
                                  services/ (documents, ingest, qa)
                                    │                    │
                document_processing/                 rag/
                extract → bounded OCR → chunks       embed (lazy) · vector + keyword search · RRF
                                                     [rerank: optional] · context · prompt
                                                     llm/ provider adapter ─────────────────────▶ LLM API (chosen in M3)
                                    │
                                    └── database/ (queries run as the user, RLS applies) ────────▶ Postgres + Storage
```

The browser uses Supabase **only for authentication**. All data access goes through FastAPI. LLM keys and the Supabase service-role key exist only in the backend's environment.

## 4. Data model, isolation and storage

### Tables (Supabase Postgres, RLS enabled on every table)

| Table | Key columns |
|---|---|
| `profiles` | `id` (= `auth.users.id`), `display_name`, `default_persona` |
| `documents` | `id`, `user_id`, `filename`, `storage_path`, `size_bytes`, `page_count`, `sha256`, `status` (`queued`/`processing`/`ready`/`failed`), `error`, `attempts`, `lease_until`, `ocr_pages`, `created_at` |
| `chunks` | `id`, `document_id`, `user_id`, `chunk_index`, `page_start`, `page_end`, `text`, `embedding` (pgvector `vector(384)`), `tsv` (generated `tsvector`, GIN index) |
| `conversations` | `id`, `user_id`, `document_id`, `persona`, `title`, timestamps |
| `messages` | `id`, `conversation_id`, `user_id`, `role`, `content`, `citations jsonb` (`[{chunk_id, page_start, page_end, quote}]`), `provider`, `model`, `tokens_in`, `tokens_out` |
| `llm_usage` | `id`, `user_id`, `day`, `reserved_tokens`, `actual_in`, `actual_out`, `status` (`ok`/`rate_limited`/`error`), `created_at` |
| `app_settings` | single row: `ai_enabled`, `global_daily_token_cap`, `per_user_daily_questions`, `storage_cap_bytes`, `db_rows_cap` |

Full page text is **not** stored. Chunks are enough for retrieval and citations, and the original PDF in Storage is the source for viewing and reprocessing.

### Isolation

- **Normal user requests run as the user.** The backend forwards the caller's JWT to Supabase, so RLS (`user_id = auth.uid()`) applies to every read and write. The service-role key is **not** used for user-scoped queries.
- **Service role is limited to:** the ingest worker writing chunks for a document whose ownership was verified at upload (it also filters by `user_id`), and the storage and row guard totals. Each use is a named function in `database/admin.py`, so it is easy to audit.
- **Citations are re-checked.** Before a citation is returned, its `chunk_id` must belong to the conversation's document, which in turn belongs to the user.
- **Storage paths** are `{user_id}/{document_id}.pdf` in a private bucket, with Storage RLS on the path prefix. Signed URLs are short-lived and issued only after an ownership check.
- **Gate:** no public deployment (Milestone 7) until the cross-user isolation suite passes. That suite covers files, chunks, conversations, messages, citations and signed URLs, with two real test users.

### Storage and database limits

Supabase Free gives **1 GB of Storage and 500 MB of database per project, shared by all users**. These are not per-user allowances. *Estimates, to be replaced by Milestone 2 measurements:*

- **Per chunk:** about 1.2 KB of text, about 1.6 KB of vector, and about 1 KB for the tsvector and indexes, so roughly 4 KB per chunk.
- **Per document:** a 100-page PDF yields about 300 chunks, which is about 1.2 MB of database.

| Limit (configurable) | Default | Why |
|---|---|---|
| Max file size | 10 MB | Bounds upload time, memory and Storage use |
| Max pages per PDF | 150 | Bounds processing time and chunk rows |
| Max documents per user | 5 | 5 × 10 MB = 50 MB worst case per user |
| Project Storage guard | 800 MB (80% of 1 GB) | Uploads are refused with a visible "Storage is full for this demo" error |
| Project database guard | 400 MB (80% of 500 MB) | Same, measured with `pg_database_size` |

Deleting a document removes the Storage object, its chunks, conversations and messages in one transaction, and a cleanup task removes orphaned objects. Duplicate uploads (same `sha256` for the same user) are rejected.

## 5. Document processing (bounded and recoverable)

**Upload:** the backend checks size, the `%PDF-` signature, page count and the guards. It stores the file, inserts the document as `queued`, and returns at once.

**Processing on a host that can sleep or restart at any time:** background work is not durable on Render Free, so it is designed as a re-runnable state machine rather than a promise.

1. A worker claims a `queued` document by setting `status=processing` and `lease_until = now + 10 min` in a single conditional update, so only one worker gets it.
2. **Extract** text per page with pdfplumber. **OCR** a page only if its text is under 50 characters. OCR runs at 150 DPI, on at most 20 pages per document, with a 20-second per-page timeout. Pages beyond the cap are recorded in `ocr_pages` as skipped and shown to the user.
3. **Chunk** and **embed** in small batches.
4. **Write idempotently.** Inside one transaction, delete the document's existing chunks, insert the new ones, and set `status=ready`. Re-running a document always gives the same result.
5. **Recover.** On startup, and whenever the library is listed, documents with an expired lease go back to `queued` (if `attempts < 3`) or to `failed` with the error. The UI shows the live status and a **Retry** button. The app never claims processing will finish while the service is asleep. A document left `queued` simply resumes when the service wakes.

CPU-heavy steps run in a thread pool so request handling is not blocked.

## 6. Retrieval (low-resource first, chosen by measurement)

```
question + persona hint terms (+ previous question when needed, §7)
  ├─▶ semantic: top 20 by cosine similarity within the document
  ├─▶ keyword:  top 20 by Postgres websearch_to_tsquery + ts_rank_cd within the document
  ├─▶ RRF (k=60) → top 10
  ├─▶ [optional Cross-Encoder rerank → top 5; off by default]
  └─▶ context: best 4–5 passages, capped at about 1,500 tokens, tagged [C1]…[Cn] with pages
```

- **Embedding model.** The current `all-MiniLM-L6-v2` (22M parameters, 384 dimensions) is already small. Milestone 2 measures it under PyTorch CPU against an ONNX Runtime build of the same model, and keeps the lighter one if quality is equal. It loads lazily on the first upload or question and stays loaded.
- **Semantic search strategy.** Because Q&A is one document at a time, the search space is one document's chunks (about 450 at the 150-page cap). Milestone 2 benchmarks three options for peak RSS and p50/p95 latency, and the best is selected:
  - **(a)** pgvector exact search in Postgres, filtered by `document_id`. Nothing is held in Render RAM.
  - **(b)** load that document's vectors from Postgres into NumPy per request, or into a small LRU of 2–3 documents.
  - **(c)** the existing FAISS `IndexFlatIP` per document, in the same small LRU.

  Full per-document indexes for all users are **never** held in RAM. No rebuild time is claimed until it is measured.
- **Cross-Encoder** (`ms-marco-MiniLM-L-6-v2`) is behind `RERANK_ENABLED=false`. It is turned on only if the Milestone 2 benchmark shows the whole pipeline fits the free instance with headroom, and if the Milestone 3 evaluation shows it improves citation accuracy enough to justify its CPU cost.
- **Persona effect on retrieval** is limited to adding 3–5 hint terms to the keyword query. This costs no tokens.

## 7. Generation, token accounting and quota

### The only LLM call in v2.0: the answer

Follow-ups do **not** use an LLM rewrite. If a question is short (under 6 words) or starts with a reference word ("it", "this", "that", "they", "what about", "and"), the retrieval query becomes the previous user question plus this one. The model also sees the last 2 turns, truncated. There are no structured-output calls in v2.0, so there are no JSON repair retries.

### Per-request token budget (worst case, reserved before the call)

| Part | Cap (tokens) |
|---|---|
| System prompt (grounding and citation rules) | 220 |
| Persona preset (compact, all 4 measured in Milestone 3) | ≤ 60 |
| Retrieved passages (4–5 tagged passages) | ≤ 1,500 |
| History (last 2 turns, truncated) | ≤ 400 |
| Question | ≤ 120 |
| **Input total** | **≤ 2,300** |
| Answer (`max_tokens`) | 500 |
| **Reserved per request** | **2,800** |
| Retries | A 429 or provider error is retried at most once, after `retry-after`. A rejected request uses no tokens, but the ledger still reserves for it. A request that started and failed is charged at its actual usage. |

The ledger reserves 2,800 tokens before each call, settles to the provider's reported usage afterwards, and releases unused reservation. Real per-call numbers come from the Milestone 3 workload test, and the caps are tuned from them.

### Global and per-user limits

- **Global cap.** `global_daily_tokens = floor(0.6 × D)`, where D is the lowest *verified* daily token limit for the chosen model, read from the account console and not from docs. The 40% headroom covers retries, settlement drift and limit changes. A per-minute cap works the same way, at 60% of the verified per-minute limit.
- **Per-user limit** (default 15 questions per day) only stops one user from using up the shared pool. It is **not** a capacity guarantee, and the UI does not present it as one.
- **No advertised capacity until it is measured.** After Milestone 3 the README states "expected daily answers = global cap ÷ measured p95 tokens per answer", with the measurement date and the verified limits it is based on.
- **Kill switch.** `AI_ENABLED` (environment) and `app_settings.ai_enabled` (database) disable generation immediately.
- **States the UI shows explicitly:**
  - AI unavailable, for the kill switch or a provider outage.
  - Daily limit reached, with the reset time.
  - AI busy, try again in N seconds, for the per-minute limit or a 429.

  PDF viewing, metadata, history and the search results list keep working in all of these states.
- **Never an error as an answer.** Provider failures become typed HTTP errors. A message is stored only on success, and a failed question can be retried.

### Personas (prompt presets)

| Preset | Instruction (target ≤ 60 tokens) | Retrieval hints |
|---|---|---|
| Beginner | Plain language, define terms, one analogy if helpful | example, definition, introduction |
| Exam Preparation | Precise definitions, key points as a list, note likely exam angles | define, important, formula, difference |
| Researcher | Methodology, evidence, assumptions and limitations | method, results, limitation, evaluation |
| Professional | Concise executive-style answer: conclusion first, then support | summary, recommendation, impact |

## 8. LLM provider: evidence-based gate

The provider is **not** fixed in advance. v2.0 ships a small adapter: one OpenAI-compatible client (`rag/llm/openai_compat.py`), configured by `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`, with typed errors (`RateLimited`, `QuotaExceeded`, `ProviderUnavailable`, `ModelUnavailable`, `AuthError`). Groq, Mistral and Gemini all offer OpenAI-compatible endpoints, so switching providers is a configuration change. Exactly one provider is active. There is **no automatic fallback**, so a failure never silently sends a document to a second provider.

**Desk research (official pages, 2026-11-12). These are starting points only, not decisions.**

| Candidate | Payment method needed for free use? | Free-tier data use, as published | Notes |
|---|---|---|---|
| Groq (`openai/gpt-oss-120b`, `gpt-oss-20b`) | Card only needed to upgrade | "does not retain customer data for inference requests" by default; abuse logs kept up to 30 days, can be opted out of | Docs table of limits is ambiguous between Free and Developer, so it must be read from the console |
| Gemini Developer API (Flash, Flash-Lite) | No billing account needed; India is an available region | Free-tier content "used to improve our products"; human reviewers may read it; terms say not to submit sensitive or personal info | A usable model with a weak privacy position for user PDFs |
| Mistral (Small) | Free API tier exists | Not stated for the free tier | Limits shown only in the console |
| Cerebras | **Yes** (credit requires a payment method) | Not applicable | **Excluded** |
| Cohere trial, OpenRouter `:free` | No | Varies | **Excluded:** 1,000 calls per month, or 50 requests per day |

**The gate (Milestone 2 checks, Milestone 3 decides):**
1. For each remaining candidate, **you** confirm on the actual account console: exact model ID, RPM, TPM, RPD and TPD limits, India availability, and that no payment method was requested. I verify current official pricing, structured output, data retention and deprecation notices.
2. Run the grounded-Q&A evaluation (§10) on **public fixture PDFs only**, never on user documents, for every candidate that passes step 1. Measure citation accuracy, faithfulness, "not found" correctness, p50/p95 latency and tokens per answer.
3. Pick the candidate with the best balance of quality, latency, privacy and verified free quota. A provider whose free tier may use or human-review inputs is chosen only if it is clearly better **and** you accept the trade-off. In that case the upload screen states plainly which provider receives passages from the document and what its policy says.
4. Record the decision, the evidence and the date in `docs/provider-decision.md`.

Until the gate is passed, development uses a fake provider in tests. Real calls use only the fixture PDFs.

## 9. Resource limits on free hosting

Render Free has an ephemeral filesystem and spins down after 15 minutes idle, with a cold start of about 1 minute. Its RAM and CPU are not stated on its free-tier page, so Milestone 2 reads them from the actual service. The backend must fit them with headroom. Bounds:

- **Models:** lazy-loaded, one embedding model, reranker off by default, CPU-only builds, and no model downloads at request time (they are baked into the image at build).
- **OCR:** 20 pages, 150 DPI, 20 seconds per page, and one document processed at a time.
- **Concurrency:** one processing worker and a small request pool, so a large upload cannot starve Q&A.
- **Cold start:** the UI shows a "Waking up the demo server…" state when `/health` is slow, instead of failing.
- **If it does not fit,** step down in this order: switch to the ONNX embedder, keep the reranker off, use pgvector search so no vectors are held in RAM, then lower the OCR and page caps. Never upgrade the plan.

## 10. Testing and acceptance

- **Backend (pytest):**
  - unit tests for extraction (text and scanned fixtures), chunk page mapping, RRF, citation validation, follow-up resolution and the token ledger;
  - API tests with the fake provider;
  - quota exhaustion, 429, timeout, kill switch and invalid-model tests;
  - the cross-user isolation suite against a real Supabase test project.
- **Frontend:** Vitest and React Testing Library for components and states, including "AI unavailable", "limit reached" and "waking up". One Playwright smoke test: sign up → upload → wait for ready → ask → open citation.
- **Repeatable workload test** (`backend/scripts/workload.py`). It runs 3 fixture PDFs (text, mixed and scanned) and about 20 realistic questions, and records:
  - tokens in and out per call;
  - p50/p95 answer latency;
  - peak RSS;
  - OCR and total processing time per document;
  - Storage and database growth per document;
  - retrieval recall@5 and citation accuracy against gold pages;
  - behaviour under forced 429s and quota exhaustion.

  It runs locally in Milestones 2–3, and again against the deployed free services in Milestone 7.
- **Deployment acceptance (Milestone 7):** the deployed app passes the smoke test and the isolation suite. The workload results are attached to the PR, and the README states expected daily capacity from measured tokens and console-confirmed limits, with the safety margin applied.

## 11. Milestones (7)

Each milestone uses its own branch from the latest `main`, has its own PR to `main` on `ChinmayeePrasad327/PersonaLens`, and waits for your review and merge before the next one starts.

| # | Branch | Delivers | Exit criteria |
|---|---|---|---|
| 1 | `docs/m1-audit-architecture` | This audit and plan. After your approval, in the same PR: `.env.example`, a fuller `.gitignore`, a README that describes only what exists plus the local demo path, and a pytest scaffold with CI (lint and test). | CI green |
| 2 | `feat/m2-backend-hardening` | `git mv` into `backend/app/`. Fixes the audit's C1–C3, H1, M1–M4, S3, S4 and S6. Page-aware chunk metadata, bounded OCR, upload validation, `/health`, settings, the provider adapter with typed errors (fake provider in tests), CPU-only pinned requirements and a Dockerfile with Tesseract. **Resource benchmark** of the embedder (Torch vs ONNX) and the three search options, on a free Render instance. Provider gate step 1. `ui.py` keeps working. | Tests pass; benchmark report in the PR with the chosen options |
| 3 | `feat/m3-retrieval-citations` | Keyword + semantic retrieval with RRF, optional reranker, token-capped context, citation tagging and validation, deterministic follow-ups, the 4 persona presets, and the token ledger logic. Evaluation set and **provider gate steps 2–4**. | Recall@5, citation accuracy and tokens per answer reported; provider decision recorded |
| 4 | `feat/m4-auth-persistence-quotas` | Supabase migrations with RLS, Storage bucket and policies, JWT auth, document CRUD with the recoverable processing state machine, conversation history, Storage and database guards, global and per-user quotas, kill switch, `/usage`. | Isolation suite passes; restart-mid-processing test; quota-exhaustion test |
| 5 | `feat/m5-frontend-foundation` | Vite + React + TypeScript, Tailwind design system, landing page, auth screens, protected routes, and the "waking up" and error states. `ui.py` is retired once Milestone 6 reaches parity. | Vitest; accessibility check; screenshots |
| 6 | `feat/m6-library-workspace` | Library (upload with progress, status, retry, delete), workspace (PDF viewer, single-document Q&A, citations that jump to the page, passage previews, history, persona selector), usage meter and quota states, answer copy and Markdown download. **Retire `ui.py`.** | Component tests; manual run against the Milestone 4 backend |
| 7 | `feat/m7-test-deploy` | Deploy to Render Free, Vercel Hobby and Supabase Free. Deployment guide, workload test on the deployed services, final cost and quota audit, README capacity statement and demo caveats. | Smoke test and isolation suite pass on production; workload report attached. **No deployment claim without this evidence.** |

## 12. Future improvements (not in v2.0)

Each item below is excluded because of its token cost or infrastructure cost on free tiers. The architecture leaves room for each one (the adapter, the `documents` and `chunks` model, and the quota ledger) without building it now.

| Improvement | Added LLM token cost | Added infrastructure or resource cost |
|---|---|---|
| Multi-document chat | Larger context: about 1.5–2× input per answer to keep per-document diversity | Searching across several documents: more vectors in memory or larger pgvector scans |
| Collections | None | More tables and UI; low risk, mostly product scope |
| Custom personas | Longer and unbounded system prompts (must be capped and counted) | A table plus a builder UI, and validation |
| LLM follow-up rewriting | +1 small call per follow-up (about 300–500 tokens) | None |
| Document brief (quick summary, takeaways, definitions) | About 4–6K per document, once (cached) | Cache table |
| Detailed, executive and chapter-wise summaries | About 20–60K per document (map-reduce) | Long jobs on a sleeping host need durable job tracking |
| Quizzes and flashcards | About 3–5K per set, plus JSON repair retries | Storage of sets and attempts; scoring UI |
| Short- and long-answer grading, exam mode | +1 call per submitted answer | Attempt history |
| Multi-PDF comparison, contradictions | Paired generation per topic, often 10K+ per comparison | Topic clustering across documents (CPU) |
| Research assistant (paper analysis, gaps, methodology) | Several long structured calls per paper | Section detection |
| Document classification, concept extraction | About 1K per document at ingest | Small |
| DOCX, PDF and CSV export | None | Server-side rendering libraries, CPU and bandwidth |
| Second or fallback LLM provider | None extra, but sends user passages to another party | Explicit per-user opt-in with a privacy disclosure; never automatic |
| Cross-Encoder on by default | None | About 100 MB or more of RAM and extra CPU per query; depends on the benchmark |
| Batch multi-file upload | None | Concurrent processing load on a single small instance |
