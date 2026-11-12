# PersonaLens — Technical Audit

**Audited:** 2026-11-12
**Repository:** `ChinmayeePrasad327/PersonaLens`, branch `main` at commit `b5bb462`
**Reference only (not modified):** `Gayathri-yadla/Persona_pdf_analyser`

## 1. Scope and method

Every file in the repository was read in full. There are 13 files (about 22.8 KB):

| File | Lines | Role |
|---|---|---|
| `app.py` | 91 | FastAPI backend: `POST /upload`, `POST /query` |
| `ui.py` | 199 | Streamlit frontend that calls the backend over HTTP |
| `pdf_processor.py` | 32 | pdfplumber text extraction with a pytesseract OCR fallback |
| `chunker.py` | 15 | Word-based sliding-window chunker |
| `embeddings.py` | 12 | `all-MiniLM-L6-v2` Sentence Transformer, loaded at import |
| `vector_store.py` | 38 | Global in-memory FAISS `IndexFlatL2` plus a parallel list of chunk strings |
| `personas.py` | 53 | Persona hierarchy (3 roles, 7 sub-personas) |
| `relevance.py` | 36 | Heuristic re-scoring (semantic score + persona keywords + query words) |
| `generator.py` | 80 | Groq chat completion with a persona system prompt |
| `requirements.txt` | 13 | Unpinned dependencies |
| `README.md` | 110 | Project description |
| `.gitignore` | 5 | Ignores `.env`, venv and bytecode |

Beyond reading the code, the following were run with Python 3.13. Sentence Transformers, pytesseract and Groq were stubbed because they need large or external dependencies.

- `extract_text_from_pdf` on a generated 2-page PDF
- `split_text` on a 600-word input
- `VectorStore.add_documents` and `search` with `k` larger than the corpus
- `calculate_hybrid_score` with a known and an unknown persona
- Importing `generator` without the `groq` package

Git history has 6 commits, made between 2026-01-06 and 2026-01-21 by Gayathri-yadla (4) and Chinmayee_Prasad (2). There are no other branches, no tests, no CI and no licence file.

## 2. What works today

Assuming dependencies are installed and the Groq model is valid (see C1 below), the core loop works end to end:

1. Streamlit uploads each PDF to `POST /upload`. The UI supports selecting several files at once and sends them one at a time.
2. The backend extracts text with pdfplumber. It falls back to Tesseract OCR when a page has fewer than 50 characters of text. Verified on a generated PDF.
3. Text is split into 300-word chunks with a 50-word overlap. Verified: 600 words give 3 chunks starting at words 0, 250 and 500.
4. Chunks are embedded with MiniLM and added to a FAISS index. Search correctly skips `-1` results when `k` exceeds the corpus.
5. The query is embedded, the top 15 chunks are retrieved, re-scored with persona keywords, and the top 5 are sent to Groq with a persona-specific system prompt.
6. An empty query triggers "summary mode", which retrieves with the fixed text "summary main points overview".
7. The persona hierarchy drives both the UI dropdowns and the prompt.

**Worth preserving:** the module split itself (extraction → chunking → embedding → store → relevance → generation) is clean and maps directly onto a proper RAG package. The OCR-fallback idea, the persona data model (`intent`, `keywords`, `prompt_style`), and the "answer only from context, else say not found" prompt are good foundations.

## 3. Findings

Severity: **Critical** = broken or unsafe now. **High** = blocks a 2.0 requirement. **Medium** = quality or robustness. **Low** = cleanup.

### 3.1 Bugs and broken functionality

| ID | Sev | Finding | Evidence |
|---|---|---|---|
| C1 | Critical | **The hard-coded Groq model has been retired.** `generator.py:73` uses `llama-3.3-70b-versatile`. Groq's deprecations page lists its shutdown on 2026-08-16 for free and developer tiers, with `openai/gpt-oss-120b` as the replacement. Every answer now returns the string `"Error connecting to Groq: …"` with HTTP 200, so the UI shows the error as if it were an answer. | [Groq deprecations](https://console.groq.com/docs/deprecations) |
| C2 | Critical | **`groq` is missing from `requirements.txt`.** `openai` is listed instead and is never imported. A fresh install crashes at `import generator`. | Smoke test: `ModuleNotFoundError: No module named 'groq'` |
| C3 | Critical | **The backend cannot start without `GROQ_API_KEY`.** `generator.py:11-12` raises `ValueError` at import time. Upload and retrieval, which do not need the LLM, also become unavailable, and tests cannot import the app. | `generator.py:10-12` |
| H1 | High | **LLM errors are hidden as successful answers.** `generate_response` catches every exception and returns the error text, so `/query` responds 200 with the error as the answer. | `generator.py:79-80` |
| M1 | Medium | **Substring matching in query overlap.** `word in chunk_text` matches inside words, so "a", "is" or "in" count as overlaps against almost any chunk. This inflates scores for chunks that are not relevant. | `relevance.py:24`; reproduced in the smoke test |
| M2 | Medium | **Unknown personas silently fall back** to Student / First Year, but the prompt still says "acting as {unknown persona}". Bad input should get a 422 instead. | `personas.py:51-53` |
| M3 | Medium | **Summary mode is not a summary.** It summarises whichever 5 chunks happen to be nearest to "summary main points overview", not the document. | `app.py:58-63` |
| M4 | Medium | **The extension check is case-sensitive.** `REPORT.PDF` is rejected, while any file named `*.pdf` is accepted without checking its content. | `app.py:32` |
| L1 | Low | The UI title is "Insight AI", not PersonaLens. | `ui.py:10,144` |

### 3.2 Missing metadata and retrieval limitations (the largest gap for 2.0)

| ID | Sev | Finding |
|---|---|---|
| R1 | High | **No metadata at all.** The store keeps bare chunk strings. There is no document ID, filename, page number or chunk ID, so citations are impossible. |
| R2 | High | **Page boundaries are destroyed.** `extract_text_from_pdf` concatenates all pages into one string before chunking, so a chunk cannot be traced back to a page. |
| R3 | High | **No document scoping.** All uploads go into one global index. You cannot query one document, delete one, or compare documents. |
| R4 | High | **No real keyword search.** The "hybrid" step only re-scores the 15 semantic hits. A chunk that matches the keywords exactly but ranks 16th semantically can never be found. There is no BM25 or full-text index. |
| R5 | Medium | **Unbalanced score fusion.** The semantic part `1/(1+L2)` sits between about 0.33 and 1, while the keyword part grows without limit (+0.1 per persona keyword, +0.05 per query word). Long chunks with many keyword hits can outrank better semantic matches. |
| R6 | Medium | **Persona keywords favour vocabulary, not intent.** For example, "Quiz Generation" boosts chunks containing the word "quiz". Persona should shape query expansion, filtering and generation rather than literal word matching. |
| R7 | Medium | **No reranker.** The README describes a trained Cross-Encoder (`reranker.py`, `train_reranker.py`, `models/slm`), but none of these files exist. |
| R8 | Medium | **Cleaning destroys content.** Every line of 5 characters or fewer is dropped, including short formulas (`x=1`), equation lines, list markers and short headings. Verified in the smoke test. |
| R9 | Medium | **Coarse OCR trigger.** A page with a 49-character caption and an embedded scanned image goes to OCR, while a mixed page with 60 characters of text never does. |
| R10 | Low | The chunker splits on whitespace with no regard for sentences or sections, so chunks start and end mid-sentence. |
| R11 | Low | No conversation memory, so follow-up questions are not possible. |

### 3.3 Security issues

| ID | Sev | Finding |
|---|---|---|
| S1 | Critical | **Every user shares one index.** The vector store is a process-wide global, so any uploader's documents are retrieved for every other user's queries. Any public deployment of this code, including the Streamlit demo linked in the README, would leak documents between users. |
| S2 | High | **No authentication or authorisation** on any endpoint. |
| S3 | High | **No upload limits.** The whole file is read into memory (`await file.read()`) with no size limit, no page limit and no PDF signature check. A large or malformed PDF can exhaust memory or tie up CPU on OCR. |
| S4 | Medium | **Permissive CORS.** `allow_origins=["*"]` together with `allow_credentials=True` makes Starlette echo any origin back, which allows credentialed cross-origin requests from any site. |
| S5 | Medium | **Raw LLM output is rendered as HTML.** `ui.py:186-193` injects the answer into `st.markdown(..., unsafe_allow_html=True)`. A crafted PDF could prompt-inject HTML into the answer. This goes away when Streamlit is retired, but the React app must render answers as sanitised Markdown. |
| S6 | Medium | **Internal errors are leaked to clients.** `HTTPException(500, detail=str(e))` and the Groq error string expose internals. |
| S7 | Low | No rate limiting. LLM cost and OCR CPU can be abused. |
| S8 | OK | Secrets are handled correctly: the key is read from the environment and `.env` is gitignored. No credentials were found in the code or the git history. |

### 3.4 Performance problems

| ID | Sev | Finding |
|---|---|---|
| P1 | High | **CPU-heavy work blocks the event loop.** OCR, embedding and the Groq call run synchronously inside `async def` handlers, so a single upload stalls every other request. |
| P2 | Medium | **Models load at import.** MiniLM loads when the module is imported, which makes startup slow and memory-heavy. The faster path is lazy loading or one load at startup, shared across requests. |
| P3 | Medium | **Expensive OCR settings.** OCR at 300 DPI on every sparse page, with no page cap or timeout. |
| P4 | Low | Embeddings are not normalised explicitly. MiniLM happens to normalise its output, but switching models would silently break L2-as-cosine. Use `IndexFlatIP` with explicit normalisation. |

### 3.5 Missing dependencies and configuration

- `groq` is missing (C2). `openai` and `requests` (backend side) are listed but unused by the backend.
- No version is pinned, which makes builds unreproducible. sentence-transformers pulls in a full CUDA build of torch by default, several GB, unless the CPU wheel is pinned.
- The Tesseract binary is a system dependency and is not documented for deployment.
- There is no `.env.example`, no test dependencies, no `pyproject` or lint config, and no CI.

### 3.6 Documentation drift (README versus code)

- It lists 6 files that do not exist: `heuristics.py`, `train_reranker.py`, `reranker.py`, `frontend/index.html`, `models/slm` and the training flow.
- It omits files that do exist: `ui.py`, `relevance.py`.
- It describes OpenAI polishing and an optional LLM, but the code requires Groq at startup.
- It documents a `/query` schema (`session_id`, `persona`, `subpersona`, `action`, `top_n`, `top_k`, `use_llm`) that does not match the real one (`query`, `main_persona`, `sub_persona`). `GET /personas` and session IDs do not exist.
- It says to open `http://localhost:8000/`, but there is no route at `/`.
- It ends with a stray code fence.

### 3.7 Deployment limitations

These were checked against the providers' own pages on 2026-11-12. They will be re-checked in Milestone 10.

- **Render free web services** have an ephemeral filesystem, lost on every restart, redeploy or spin-down. They spin down after 15 minutes idle, with a cold start of about 1 minute, and have no persistent disks ([render.com/docs/free](https://render.com/docs/free)). **Any index kept only in memory or on local disk will disappear**, so indexes must be rebuildable from Supabase.
- **Memory is the main deployment risk.** torch, MiniLM and a Cross-Encoder together take several hundred MB of RAM. Render's free instance size is not stated on the free-tier docs page and must be confirmed. If it is the commonly cited 512 MB, this stack will not fit without changes. See the decision in `ARCHITECTURE.md` §7.
- **Supabase Free** allows 500 MB of database, 1 GB of storage, uploads up to 50 MB and 2 active projects. **Projects pause after 1 week of inactivity**, and backups are not included ([supabase.com/pricing](https://supabase.com/pricing)). Storing 384-dimensional embeddings costs about 1.5 KB per chunk, which comfortably fits a demo.
- Tesseract must be installed in the Render image, which means a Docker deploy or a build script.

## 4. Persona coverage versus the 2.0 target

| Target | Today |
|---|---|
| Student: Beginner, Exam Preparation, GATE Aspirant, Research Student, Interview Preparation | First Year (Basics) ≈ Beginner; Exam Preparation exists; "Researcher (Deep Dive)" ≈ Research Student. GATE and Interview Preparation are **missing**. |
| Teacher: Lesson Planning, Quiz Generation, Assessment Design | First two exist; Assessment Design is **missing**. |
| Researcher: Literature Review, Research Gap Identification, Methodology Analysis | First two exist (as "Gap Identification"); Methodology Analysis is **missing**. |
| Professional: Business Analysis, Technical Documentation, Executive Summary | Entire role **missing**. |
| Custom personas with knowledge level, objective, style, format and difficulty | **Missing.** |

## 5. Preserve, fix, improve or replace

| Component | Decision | Notes |
|---|---|---|
| `pdf_processor.py` | **Improve** | Return per-page records `(page_no, text, method)`. Keep the OCR fallback but base the trigger on text and image coverage. Stop dropping short lines. Add size and page limits. |
| `chunker.py` | **Improve** | Make it page-aware and sentence-aware with overlap. Each chunk carries `doc_id`, `filename`, `page_start`, `page_end`, `chunk_id` and `text`. |
| `embeddings.py` | **Preserve and refactor** | Same model, lazy singleton, explicit normalisation, batch encoding. |
| `vector_store.py` | **Improve** | Keep FAISS (`IndexFlatIP`), but per document and rebuildable from embeddings persisted in Supabase. Add metadata and delete. |
| `relevance.py` | **Replace** | Replace with hybrid retrieval (FAISS + Postgres full-text), reciprocal-rank fusion, Cross-Encoder reranking and persona-aware query shaping. |
| `personas.py` | **Preserve and extend** | Keep the data model and add the missing personas, generation parameters and custom personas. |
| `generator.py` | **Improve** | Configurable model (default `openai/gpt-oss-120b`), lazy client, real error propagation, citation-tagged context, conversation history. |
| `app.py` | **Restructure** | Move into `backend/app/` with routers, Pydantic schemas, auth dependency, thread-pooled CPU work, and a `/health` route. |
| `ui.py` (Streamlit) | **Keep working, then retire** | Keep it runnable against the new API until the React app reaches parity (Milestone 7), then remove it. |
| `README.md` | **Rewrite** | Describe only what exists. |
| `requirements.txt` | **Fix** | Add `groq`, remove `openai`, pin versions, CPU-only torch. |

## 6. Summary

PersonaLens has a sound, readable pipeline skeleton, but it is a single-user prototype. Today it fails on a fresh install (C2), at startup without a key (C3), and at answer time because its model is retired (C1). It has no chunk metadata, so citations cannot exist (R1–R3), and it shares one global index across all users (S1). These are fixable without discarding the design. The modules map one-to-one onto the planned `backend/app/rag/` and `document_processing/` packages, and Milestones 2–3 address every Critical and High finding above before any UI work begins.
