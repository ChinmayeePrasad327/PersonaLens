# PersonaLens

PersonaLens answers questions about your PDFs from the point of view of a chosen persona, such as a student preparing for exams or a teacher planning a lesson. It extracts text from the PDF, retrieves the most relevant passages, and asks an LLM to answer using only those passages.

> **Status:** this repository is the original prototype, which is being rebuilt as PersonaLens 2.0, a small free-tier demo of grounded, page-cited Q&A.
> - [`AUDIT.md`](AUDIT.md) describes exactly what works today and what is broken.
> - [`ARCHITECTURE.md`](ARCHITECTURE.md) is the approved v2.0 plan and its 7 milestones.

The prototype was originally built with [Gayathri-yadla/Persona_pdf_analyser](https://github.com/Gayathri-yadla/Persona_pdf_analyser).

## What the prototype contains

| File | Purpose |
|---|---|
| `app.py` | FastAPI backend: `POST /upload` (one PDF) and `POST /query` |
| `ui.py` | Streamlit frontend that calls the backend at `http://localhost:8000` |
| `pdf_processor.py` | Text extraction with pdfplumber, with a Tesseract OCR fallback for sparse pages |
| `chunker.py` | 300-word sliding-window chunks with 50 words of overlap |
| `embeddings.py` | `all-MiniLM-L6-v2` Sentence Transformer |
| `vector_store.py` | In-memory FAISS index shared by every upload in the process |
| `personas.py` | Persona hierarchy: Student, Teacher and Researcher roles with sub-personas |
| `relevance.py` | Re-scores retrieved chunks with persona keywords and query words |
| `generator.py` | Builds the persona prompt and calls the Groq API |

`POST /query` takes `{"query": str, "main_persona": str, "sub_persona": str}`. An empty query produces a persona-styled summary of the top retrieved chunks.

## Known limitations (see `AUDIT.md` for the full list)

- **Answers currently fail.** The Groq model hard-coded in `generator.py` (`llama-3.3-70b-versatile`) was retired on 2026-08-16, so every answer comes back as an error message. Milestone 2 fixes this.
- **Not installable as listed.** `groq` is missing from `requirements.txt`. Install it manually for now (see below).
- **No citations.** Chunks carry no document or page metadata, so answers cannot cite pages.
- **Single-user only.** All uploads share one in-memory index, are lost on restart, and are visible to every user of the same backend. **Do not deploy this prototype publicly.**

## Run locally

Prerequisites:
- Python 3.11 or later.
- The [Tesseract](https://github.com/tesseract-ocr/tesseract) binary on your `PATH`, which is needed only for scanned pages.
- A free [Groq](https://console.groq.com) API key. No payment method is needed.

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt groq
cp .env.example .env                                 # then set GROQ_API_KEY
uvicorn app:app --reload --port 8000                 # terminal 1
streamlit run ui.py                                  # terminal 2
```

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

These checks run on every pull request through GitHub Actions. They need no API keys or model downloads.

## Roadmap

PersonaLens 2.0 is developed one milestone at a time, each on its own branch and pull request. See [`ARCHITECTURE.md` §11](ARCHITECTURE.md#11-milestones-7):
1. audit and setup;
2. backend hardening and a resource gate on free hosting;
3. retrieval with citations, and the LLM provider evaluation;
4. auth, persistence and quotas;
5. the React foundation;
6. the PDF library and Q&A workspace;
7. tests and free-tier deployment.

v2.0 runs entirely on free tiers, with no payment method required at any step.
