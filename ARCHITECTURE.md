# PersonaLens 2.0 — Architecture and Milestone Plan

**Status:** proposal for review, 2026-11-12. Nothing in this document is implemented yet. See `AUDIT.md` for the current state.

## 1. Principles

- **Modular monolith.** There is one FastAPI service and one React app, with no queues, Redis, Kubernetes or microservices.
- **Evolve, don't rewrite.** The existing modules move into `backend/app/` with `git mv` so their history is kept, then they are improved in place.
- **Supabase is the source of truth.** Anything in memory, such as FAISS indexes or loaded models, is a cache that can be rebuilt after a restart.
- **The RAG core does not depend on the web layer.** `backend/app/rag/` and `document_processing/` import nothing from FastAPI or Supabase and are unit-testable with plain data.
- **Every citation is traceable** to a stored `chunk_id`, which maps to a `document_id` and page range. The LLM may only cite chunk IDs that it was given, and the backend checks this.

## 2. v2.0 scope under the free quota

PersonaLens v2.0 runs at ₹0, so its features are chosen by their AI token cost. Everything that runs locally costs no tokens and stays in scope: upload, OCR, chunking, embeddings, hybrid search, reranking, the PDF viewer, scoring and exports. LLM calls are kept to the core job, which is **upload PDFs and ask grounded questions with page citations**. Token-heavy extras move to [Future improvements](#15-future-improvements-out-of-scope-for-v20).

### Token budget (Groq free tier, per model, to be confirmed on your console)

| Model | Daily budget | Used for | Approximate cost per use | Capacity per day |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 200K tokens | Chat answers only | About 3.5K (6 chunks of context, short history, about 600 tokens out) | **About 50 answers** |
| `openai/gpt-oss-20b` | 200K tokens (separate quota) | Follow-up condensing (about 0.5K), document brief (about 6K, once per document), quiz or flashcard set (about 4K, once per request) | Varies | About 15 documents briefed **plus** about 20 quiz or flashcard sets |

The binding per-minute limit is about 8K tokens, which is roughly 2 chat answers per minute across all users. The app queues briefly and then shows "AI is busy, try again in N s" instead of failing. This capacity suits a portfolio demo and a small group of users. It is not a public service, and the README will say so.

**Guards that keep every core feature working within quota:**
- Per-user daily limits (default 25 questions and 5 study generations) and a visible usage meter.
- Generated briefs, quizzes and flashcards are cached in the database and reused. Opening them again costs nothing.
- Context is capped by tokens, and chat history is trimmed to the last 4 turns.
- When a quota runs out, the app gives a clear message with the reset time. The rest of the app (library, viewer, search, saved study items, exports) keeps working.
- Upload caps to stay inside Supabase Free's 1 GB storage: 20 MB and 300 pages per PDF, and 10 documents per user.

### In scope for v2.0

| Area | Included | AI tokens? |
|---|---|---|
| Auth | Register, login, logout, protected pages, profile, per-user data isolation | No |
| Documents | Drag-and-drop multi-upload with validation and progress, library, metadata, status, PDF viewer, delete, reprocess, collections | No |
| RAG | Extraction, OCR fallback, page-aware overlapping chunks, embeddings, FAISS and keyword hybrid search, Cross-Encoder rerank, context selection, validated page citations | Only for the answer |
| Chat | Multi-document grounded chat, follow-ups, saved history, new and delete conversation, citation-to-page jump, passage previews | Yes (120b) |
| Personas | All 14 built-in sub-personas and custom personas (knowledge level, objective, style, output format, difficulty). They shape retrieval hints and the prompt at no extra token cost. | No extra |
| Document brief | One cached call per document returns a quick summary, key takeaways and important definitions | Yes, once (20b) |
| Learning | MCQ quiz (5–10 questions with explanations, difficulty choice), interactive scoring done locally, flashcards with flip | Yes, once per set (20b) |
| Export | Chat answers with citations and briefs to PDF and DOCX, flashcards and quizzes to CSV | No |

## 3. System overview

```
 React (Vercel)                       FastAPI (Render)                        Supabase
 ──────────────                       ────────────────                        ────────
 Supabase Auth (anon key) ──login──▶                                          Auth
        │ access token (JWT)
        ▼
 Axios ── Authorization: Bearer ──▶  api/  (routers, Pydantic schemas)
                                       │  core/auth  verify JWT → user_id
                                       ▼
                                     services/  (documents, chat, study)
                                       │                     │
                     document_processing/          rag/                     ──▶ Postgres (+ full-text, RLS)
                     extract → OCR → pages         embed · FAISS cache        ──▶ Storage (private "documents" bucket)
                                   → chunks        keyword (PG FTS) · fuse
                                                   rerank · context · generate ──▶ Groq API
```

The browser talks to Supabase **only for authentication**. All data access goes through FastAPI. The Groq key and the Supabase service-role key exist only in the backend's environment.

## 4. Repository layout (target)

```
PersonaLens/
  backend/
    app/
      main.py                  # app factory, CORS, /health, routers
      api/                     # auth, documents, chat, personas, study, export
      core/                    # config (pydantic-settings), auth, errors, logging
      database/                # supabase client, queries per table, migrations/*.sql
      document_processing/     # ← pdf_processor.py, chunker.py
      rag/                     # ← embeddings.py, vector_store.py, relevance.py, generator.py
                               #    + keyword.py, fusion.py, reranker.py, context.py, prompts.py
      personas/                # ← personas.py (+ custom persona model)
      services/                # orchestration: ingest, chat, brief, quiz, flashcards, export
    tests/                     # pytest: unit (rag, processing) + API (TestClient, fakes)
    requirements.txt           # pinned; CPU-only torch
    Dockerfile                 # includes tesseract-ocr for Render
  frontend/
    src/{components,pages,layouts,hooks,services,contexts,types,assets}
    package.json
  docs/                        # deployment guide, API reference, screenshots
  AUDIT.md  ARCHITECTURE.md  README.md  .env.example  .gitignore
```

`ui.py` stays at the root and keeps working against the new API until the React chat reaches parity in Milestone 7. It is deleted at that point.

## 5. Data model (Supabase Postgres)

Every table has `user_id uuid references auth.users` and row-level security (RLS) with `user_id = auth.uid()`. **User-scoped queries run as the caller:** the backend forwards the user's own JWT to Supabase, so RLS actually applies. The service-role key bypasses RLS, so it is used only where no user token exists: background ingestion of a document whose ownership was already checked, Storage housekeeping, and migrations. Those code paths always filter by `user_id` explicitly. A two-user isolation test covers both paths.

| Table | Key columns |
|---|---|
| `profiles` | `id` (= auth user), `display_name`, `default_persona_id`, `created_at` |
| `documents` | `id`, `user_id`, `filename`, `storage_path`, `size_bytes`, `page_count`, `sha256`, `status` (`uploaded`/`processing`/`ready`/`failed`), `error`, `created_at` |
| `document_pages` | `document_id`, `page_no`, `text`, `extraction` (`text`/`ocr`) |
| `chunks` | `id`, `document_id`, `user_id`, `chunk_index`, `page_start`, `page_end`, `text`, `embedding` (`vector(384)` via pgvector, used only as storage), `tsv` (generated `tsvector`, GIN index) |
| `collections`, `collection_documents` | user-defined groups of documents |
| `personas` | built-in rows (`user_id` null, read-only) and custom rows: `role`, `name`, `knowledge_level`, `objective`, `style`, `output_format`, `difficulty`, `retrieval_hints` |
| `conversations` | `id`, `user_id`, `title`, `persona_id`, `document_ids uuid[]`, timestamps |
| `messages` | `conversation_id`, `role`, `content`, `citations jsonb` (`[{chunk_id, document_id, filename, page_start, page_end, quote}]`) |
| `study_items` | document briefs, quizzes and flashcard decks: `kind`, `document_ids`, `persona_id`, `params jsonb`, `content jsonb` |
| `quiz_attempts` | `study_item_id`, `answers jsonb`, `score` |

**Storage:** a private bucket `documents`, with objects stored at `{user_id}/{document_id}.pdf`. The PDF viewer loads short-lived signed URLs issued by the backend after an ownership check. The upload limit is 20 MB and 300 pages per file, and 10 documents per user (§2), under Supabase Free's 50 MB file cap and 1 GB total.

## 6. Document pipeline

1. **Upload.** `POST /documents` takes multipart input with multiple files. The backend checks the `%PDF-` signature, size and page limits, and deduplicates by `sha256` per user. It stores the file in Storage, inserts a `documents` row with status `processing`, and returns immediately.
2. **Process.** Processing runs in a FastAPI `BackgroundTasks` job, with CPU work in a thread pool so the event loop stays free:
   - **Extract.** pdfplumber reads each page. OCR is used when the extracted text is sparse **or** images cover most of the page, at 200 DPI with a page cap. Short lines are no longer dropped, and only repeated headers and footers are stripped.
   - **Chunk.** Sentence-aware chunks of about 250 words with about 50 words of overlap. Chunks never cross a document and record `page_start` and `page_end`.
   - **Embed and persist.** MiniLM in batches with normalised vectors. Pages and chunks with embeddings are written to Postgres, and status becomes `ready`.
3. **Recover.** On startup, documents stuck in `processing` are re-queued. **Reprocess** re-runs step 2 from the stored PDF, and **delete** removes the Storage object and cascades to all rows.

## 7. Retrieval and generation

```
query + persona + scope(document_ids) + chat history
  │ 1. Query shaping: condense follow-up into standalone query (LLM, only when history exists);
  │    append persona retrieval_hints (e.g. Methodology Analysis → "method, dataset, evaluation")
  ├─▶ 2a. Semantic: FAISS IndexFlatIP per document, top 30
  ├─▶ 2b. Keyword: Postgres websearch_to_tsquery + ts_rank_cd over chunks.tsv, top 30
  │ 3. Reciprocal Rank Fusion (k=60) → top 30 unique chunks
  │ 4. Cross-Encoder rerank (cross-encoder/ms-marco-MiniLM-L-6-v2) → top 8
  │ 5. Context selection: token budget, per-document diversity for multi-doc questions,
  │    merge adjacent chunks; each block tagged [C1] … [Cn] with filename + pages
  │ 6. Generate (Groq): persona system prompt + tagged context + recent history;
  │    model must cite [Cn]; "not found in your documents" when unsupported
  └─▶ 7. Citation validation: drop any tag not in the provided set; map tags → chunk metadata
```

- **FAISS cache.** A per-document `IndexFlatIP` is built lazily from `chunks.embedding` on first use and kept in an LRU cache in memory. A restart or spin-down only costs a rebuild, about milliseconds per document at these sizes. Moving search to pgvector later is a contained change in `rag/vector_store.py`, but it is not planned.
- **Persona influence.**
  - **Retrieval:** hint terms, top-k and diversity. For example, the Executive Summary persona favours breadth across sections, and GATE favours formulas and definitions.
  - **Generation:** objective, knowledge level, style, output format and difficulty are rendered into the system prompt.

  Tests assert that both sides change measurably between personas.
- **LLM.** Generation goes through a provider adapter (§8). Structured outputs (briefs, quizzes, flashcards) use the provider's JSON-schema mode where it exists and are always validated with Pydantic, with one repair retry. A second failure becomes a typed error and is never shown as content.
- **Document brief** uses extractive pre-selection rather than the whole document: the top-ranked chunk per section or heading, capped at about 4K tokens of input, then one structured call.

## 8. LLM provider choice (₹0 budget)

**Constraint:** no paid API usage, no payment method on file, and no fallback that could start billing. All facts below come from each provider's official pages, read on 2026-11-12. They will be re-checked before Milestone 2 and Milestone 9.

| Provider and model | Free without a payment method? | Free-tier limits | Context | Structured output | Data handling on free tier | Verdict |
|---|---|---|---|---|---|---|
| **Groq**, `openai/gpt-oss-120b` (plus `gpt-oss-20b` for light tasks) | Yes. A card is only needed to upgrade to Developer. | 30 RPM, 1K RPD, **8K TPM, 200K TPD** per model. The docs table is labelled ambiguously, so the real numbers must be confirmed on the console Limits page. | 131K | JSON schema `strict: true` (constrained decoding), but not with streaming | "By default, Groq does not retain customer data for inference requests." Abuse logs are kept up to 30 days and can be opted out of, and Zero Data Retention is self-serve. | **Primary** |
| **Google Gemini** Developer API, `gemini-3.5-flash` / `gemini-3.1-flash-lite` | Yes, no billing account. India is an available region. | Per-model numbers are shown only inside AI Studio and must be verified there. | Large (exact value not stated on the pages read) | JSON schema | **Free-tier content is "used to improve our products", "human reviewers may read… your API input and output"**, and the terms say "do not submit sensitive, confidential, or personal information". | **Not in v2.0.** A possible future opt-in fallback (§15) |
| **Mistral**, `mistral-small` 4 (256K) | A free API tier exists with "restrictive rate limits". | Not published; shown only in the console. | 256K | Yes | Training on free-tier data is not stated (the Free column is blank). | Candidate for evaluation only, pending console verification |
| **Cerebras**, `gpt-oss-120b` | **No.** Free credit requires adding a payment method and expires in 30 days. "Is there a permanently free tier? No." | 5 RPM | 65K on trial | Strict JSON schema | No retention of inputs or outputs | **Excluded** (needs a payment method) |
| **Cohere** trial, Command A | Yes | **1,000 calls per month**, 20 RPM. Trial keys are "evaluation keys". | 256K | Native citations | Not found | **Excluded** (quota far too small, evaluation-only) |
| **OpenRouter** `:free` models | Yes | **50 requests per day** without buying credits | Varies | Varies | Some upstream providers train on prompts; this is controlled by an account setting. | **Excluded** (quota) |

**Recommendation: Groq `openai/gpt-oss-120b` as the default provider.**
- It is the only candidate that is free with no payment method, retains no inference data by default, and offers schema-constrained JSON. Those three properties matter most for a product that ingests users' private PDFs and depends on valid quizzes and flashcards.
- `gpt-oss-20b` has its own quota, so it handles follow-up condensing, document briefs, quizzes and flashcards. That saves the 120B quota for answers.
- The binding limit is tokens: **8K tokens per minute and 200K per day**. A grounded answer uses about 3–5K tokens, which is roughly 40–60 answers a day.

**How the app lives within that quota:**
- Context packing is tight: 6–8 reranked chunks, not whole documents.
- Generated summaries, quizzes and flashcards are stored and reused, so they are never regenerated for the same inputs.
- Per-user daily limits, caching and quota messages, as set out in §2.

**Choosing on quality, not on paper.** Milestone 3 adds a small evaluation set: about 30 questions over 3 fixture PDFs, with gold pages. It measures faithfulness, citation accuracy, "not found" correctness and JSON validity on Groq, using about 120K tokens in one run, and the results go in the PR. A cross-provider comparison is a future improvement (§15).

### Provider adapter

```
rag/llm/
  base.py        # LLMProvider protocol: generate(), generate_stream(), generate_json(schema)
                 # typed errors: QuotaExceeded, RateLimited(retry_after), ProviderUnavailable,
                 #               ModelUnavailable, InvalidStructuredOutput, ProviderAuthError
  groq.py        # OpenAI-compatible chat API
  registry.py    # builds providers from settings; no provider imported unless configured
```

- **Configuration:** `LLM_PRIMARY=groq:openai/gpt-oss-120b` and `LLM_LIGHT=groq:openai/gpt-oss-20b`. Keys are read only by the backend. v2.0 ships only the Groq adapter. The interface lets another provider be added later without touching the RAG code.
- **Retries:** 429 responses honour `retry-after` with bounded backoff, at most 2 retries within the request's time budget. Then the user gets a typed error with the reset time.
- **Fallback rules (for a future second provider; there is no fallback in v2.0):**
  - A fallback exists only if the admin configures it **and** the signed-in user has opted in, per user and revocable in Settings.
  - The opt-in screen names the provider and quotes its data policy (for Gemini free tier: content may be used to improve Google products and read by human reviewers).
  - Without both, a primary failure is shown as an error, never silently rerouted. Every answer records and displays which provider and model produced it.
  - Only providers verified as free without a payment method may be registered. The registry refuses any key flagged as billing-enabled in config, and the deployment guide explains how to keep Gemini and Groq keys on unbilled projects.
- **Never an error as an answer:** a provider error maps to an HTTP 4xx/5xx with a typed body. Answers and study items are only stored on success.

## 9. Open decision: model memory versus free hosting

Under the ₹0 rule, the backend must fit Render's free web service. That service spins down after 15 minutes and has an ephemeral filesystem; its RAM is not stated on its free-tier page and must be confirmed. A paid instance is no longer an option. Milestone 2 measures the backend's peak memory with the embedding model and Cross-Encoder loaded, then applies whichever of these is needed to fit:

- Run both models through Sentence Transformers' ONNX backend on CPU-only builds.
- Load the Cross-Encoder lazily and skip it when the candidate set is small.
- As a last resort, make reranking a documented optional feature.

The `Embedder` and `Reranker` interfaces keep this a configuration change. Embeddings stay local, so document text is never sent to a third-party embedding API.

## 10. API surface (v1, all under `/api`, all require a Bearer token except health)

| Area | Endpoints |
|---|---|
| Health | `GET /health` (liveness, plus DB and Groq configuration checks) |
| Me | `GET/PATCH /me` |
| Documents | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/file-url`, `POST /documents/{id}/reprocess`, `DELETE /documents/{id}` |
| Collections | CRUD `/collections` |
| Personas | `GET /personas`, CRUD `/personas/custom` |
| Chat | `POST /conversations`, `GET /conversations`, `GET /conversations/{id}`, `DELETE /conversations/{id}`, `POST /conversations/{id}/messages` (streams the answer, then sends citations) |
| Study | `POST /documents/{id}/brief` (cached), `POST /quizzes`, `POST /quizzes/{id}/attempts` (scored locally, no tokens), `POST /flashcards`, `GET /study-items` |
| Usage | `GET /usage` (today's questions and generations against the limits) |
| Export | `GET /export/conversation/{id}?format=pdf\|docx`, `GET /export/{study_item_id}?format=pdf\|docx\|csv` |

## 11. Frontend

- **Stack:** React, TypeScript, Vite, Tailwind, React Router, Axios, `@supabase/supabase-js` (auth only), Lucide, Swiper, GSAP, Motion. PDF rendering adds **react-pdf** (pdf.js), the one dependency beyond your list. It is needed for the viewer and page-jump-to-citation.
- **Animation ownership:** GSAP handles the landing hero and scroll reveals only, and Motion handles everything in the app. No element is animated by both.
- **Design tokens:** a warm neutral base, navy and charcoal ink, and one indigo-violet accent. These are defined once as CSS variables and mapped into Tailwind, with light and dark themes and WCAG AA contrast checked.
- **Screens:** landing, login and registration, dashboard, document library and upload, workspace (viewer and chat), persona configuration, document brief, quiz, flashcards, conversation history, settings and usage. Comparison and research-assistant screens are future improvements.
- **Workspace:** a three-pane layout (library and history, PDF viewer, chat with persona and citations) that collapses into tabs below `lg`. Clicking a citation jumps the viewer to the cited page and highlights the passage preview.
- **Rule:** a screen ships only when its backend endpoint exists. No button is added before its endpoint.
- **Tests:** Vitest and React Testing Library for components and hooks, plus one Playwright smoke test (sign up → upload → ask → citation) in Milestone 9.

## 12. Configuration and security

- **`.env` variables.** Backend: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` (or JWKS), `LLM_PRIMARY`, `LLM_LIGHT`, `GROQ_API_KEY`, `ALLOWED_ORIGINS`, `MAX_UPLOAD_MB`, `MAX_DOCS_PER_USER`, `DAILY_QUESTIONS_PER_USER`, `DAILY_GENERATIONS_PER_USER`. Frontend: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (public by design).
- **CORS:** an explicit origin list, with no wildcard alongside credentials.
- **Errors:** errors are logged server-side and clients get typed messages.
- **Rendering:** answers are rendered as sanitised Markdown and never as raw HTML.
- **Rate limiting:** per-user daily counters stored in Postgres, plus a short in-process queue for the per-minute token limit. No Redis.

## 13. Milestone plan

Each milestone uses its own branch from the latest `main`, opens a PR to `main` on `ChinmayeePrasad327/PersonaLens`, and waits for your review and merge before the next one starts.

| # | Branch | Delivers | Verified by |
|---|---|---|---|
| 1 | `docs/m1-audit-architecture` | This audit and architecture (this PR). **After your approval, same PR:** `.env.example`, a fuller `.gitignore`, a corrected README "current state" section, and a pytest scaffold with CI (GitHub Actions: lint and test). | CI green |
| 2 | `feat/m2-backend-stabilization` | `git mv` into `backend/app/`. Fixes C1–C3, H1, M1–M4, S3, S4, S6, P1, P2. Per-page extraction with better OCR and cleaning. Page-aware chunks with metadata. Config through settings. `/health`. **Groq provider adapter with typed errors and 429 handling (§8).** Pinned requirements, CPU torch, Dockerfile with Tesseract. Memory measurement and fit for the free tier (§9). `ui.py` updated to keep working. | pytest for extraction (text and scanned fixtures), chunk page mapping, API with a faked LLM, quota-error tests |
| 3 | `feat/m3-rag-citations` | Hybrid retrieval (FAISS and keyword with RRF), Cross-Encoder rerank, token-capped context selection, citation-tagged generation with validation, persona retrieval hints, all 14 built-in personas. Retrieval eval (recall@k) and the Groq grounded-answer eval (§8). | Unit tests per stage, a citation-integrity test, eval numbers in the PR |
| 4 | `feat/m4-supabase-persistence` | SQL migrations with RLS, Storage bucket, JWT auth dependency, document CRUD, reprocess, delete, processing status, upload caps, FAISS rebuild from the database after restart, conversation persistence, per-user daily usage limits and `/usage`. | Two-user isolation tests, restart-then-query test, limit tests |
| 5 | `feat/m5-frontend-foundation` | Vite, React and TypeScript scaffold, design system, landing page, auth screens wired to Supabase, protected routes. | Vitest, Lighthouse accessibility check, screenshots in the PR |
| 6 | `feat/m6-dashboard-workspace` | Dashboard, library with drag-and-drop multi-upload and progress, three-pane workspace with the PDF viewer, collections, mobile tabs. | Component tests, manual run against the M4 backend |
| 7 | `feat/m7-chat-personas` | Streaming multi-document chat, follow-ups, history, delete and new conversation, citation-to-page jump, persona settings, custom persona builder, usage meter and quota messages. **Retire `ui.py`.** | API and UI tests, persona-difference test |
| 8 | `feat/m8-brief-quiz-flashcards-export` | Cached document brief (quick summary, takeaways, definitions), MCQ quiz with difficulty, explanations and local scoring, flashcards with flip, and PDF, DOCX and CSV export. | Schema-validated LLM output tests, cache-hit test (no second call), scoring and export tests |
| 9 | `feat/m9-test-deploy` | Performance pass, deployment guide, Render, Vercel and Supabase configuration. Live end-to-end test of every item in your deployment checklist, on the deployed URLs, before reporting success. | Playwright smoke test on production, plus manual checklist evidence in the PR |

Milestones 2–4 are backend-only and keep the Streamlit UI usable, so `main` stays demoable at every merge.

## 14. Things you will need to do (no credentials in chat)

- **Before Milestone 4:** create a Supabase project, enable the `vector` extension, and add its keys to a local `.env` and later to Render. I will provide exact click-paths and the SQL.
- **Before Milestone 9:** connect the repository to Vercel and Render in their dashboards, and set environment variables there.
- **Before Milestone 2 is tested live:** create a free Groq API key with no payment method, put it in your local `.env`, and tell me the limits your console's Limits page shows for `openai/gpt-oss-120b`.
- **No step will ever ask you to add a payment method.** If a step seems to need one, stop and tell me.

## 15. Future improvements (out of scope for v2.0)

These are deliberately left out because they need many large LLM calls per use, more than the free quota can support reliably. Each one can be added later on the same architecture, through the provider adapter and the `study_items` table, if a larger free quota or a budget becomes available. **No buttons or screens will exist for them in v2.0.**

| Improvement | Why deferred | What it would take |
|---|---|---|
| Detailed, executive and chapter-wise summaries; separate formula and conclusion extraction | Whole-document coverage needs about 20–60K tokens per document | Map-reduce over page groups; a higher daily quota |
| Short- and long-answer questions with AI grading, practice tests, exam-preparation mode | Every answer submitted needs its own grading call | One grading call per answer with a rubric |
| Multi-PDF comparison, similarity and contradiction detection | Needs paired passages from every document per topic | Topic clustering on embeddings (local) plus a paired-generation call per topic |
| Research assistant: paper analysis, research gaps, methodology critique | Long structured outputs over full papers | Section-aware extraction plus several generation calls |
| Document classification and concept extraction as separate features | Low value compared with their token cost | A cheap 20b call at ingest, or a local zero-shot classifier |
| Gemini or other fallback provider | Gemini's free tier uses content for product improvement and human review | `gemini.py` adapter plus per-user opt-in (design kept in §8) |
| Cross-provider quality evaluation | Needs keys and tokens for several providers | Run the Milestone 3 evaluation set against each provider |
| pgvector search instead of FAISS | Not needed at demo scale | Swap `rag/vector_store.py` |
