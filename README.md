```markdown
# PersonaLens – Persona-Based Intelligent PDF Understanding System

A hackathon-ready prototype of PersonaLens: a persona-aware, hybrid RAG system with a trained neural relevance model (SLM).  
It supports multiple PDF uploads per session, persona-aware retrieval, a Cross-Encoder reranker trained with weak supervision, deterministic persona templates, and an optional LLM polishing step.

Design principle (explainability):
"A persona-aware document intelligence system using hybrid RAG with a trained neural relevance model and optional generation."
Live Demo Link - https://persona-pdf-analyser.streamlit.app/
## Folder structure

- app.py
- pdf_processor.py
- chunker.py
- embeddings.py
- vector_store.py
- personas.py
- heuristics.py
- train_reranker.py
- reranker.py
- generator.py
- frontend/index.html

## Quick setup

1. Create a virtual environment and activate it:
   - python3 -m venv venv
   - source venv/bin/activate  (Linux/Mac) or venv\Scripts\activate (Windows)

2. Install dependencies:
   - pip install -r requirements.txt

Example requirements (suggested):
- fastapi
- uvicorn[standard]
- python-multipart
- pdfplumber
- pytesseract
- pillow
- sentence-transformers
- faiss-cpu
- torch
- scikit-learn
- transformers
- cross-encoder
- python-dotenv
- aiofiles

(You can create a `requirements.txt` with these packages. FAISS sometimes needs OS-specific install; `faiss-cpu` on pip is recommended for CPU-only.)

3. Tesseract binary:
   - Install the Tesseract OCR engine on your system (OS package manager).
   - Make sure `tesseract` is available in PATH.

4. Run the app:
   - uvicorn app:app --reload --host 0.0.0.0 --port 8000

5. Open the demo front-end:
   - http://localhost:8000/

## Usage

- POST /upload
  - Upload one or more PDFs (form field name: `files`)
  - Returns a `session_id` used for subsequent queries.

- POST /query
  - JSON body:
    {
      "session_id": "<session_id>",
      "persona": "STUDENT",
      "subpersona": "First Year Student",
      "action": "generate_exam" | "summarize" | "polish",
      "query": "optional question text",
      "top_n": 10,
      "top_k": 5,
      "use_llm": false
    }
  - Returns deterministic persona-aware response and retrieved chunk metadata.

- GET /personas
  - Returns persona/subpersona mapping and intent descriptions.

Notes:
- Sessions are stored in-memory (hackathon-safe).
- The SLM (Cross-Encoder) model is trained via `train_reranker.py` and saved to `models/slm`.
- If you set an environment variable `OPENAI_API_KEY`, optional LLM polishing is enabled (OpenAI polishing is optional).
- The system is designed to function fully without an LLM; deterministic templates are ALWAYS ON.

## Files of interest

- `train_reranker.py` – run this to create weak-supervised training data and train the Cross-Encoder SLM (1–3 epochs recommended).
- `reranker.py` – loads SLM and scores candidate chunks at inference.
- `generator.py` – deterministic persona templates (always on) and optional LLM polish.

## Reproducibility & Explainability

- Weak supervision labeling is printed and saved during reranker training.
- All retrieved chunk metadata and reranker scores are returned in API responses for transparency.
- The LLM (if used) only receives the retrieved chunks and the deterministic output to rephrase/polish (to minimize hallucinations). The core retrieval+SLM pipeline runs without any LLM.

## Limitations

- This is a prototype built for hackathon/demo purposes. For production:
  - Persist sessions and vector store to durable storage.
  - Add authentication and rate-limiting.
  - Add more robust OCR and chunking/tokenization (use tokenizers aligned to your LLM).
  - Expand training labeling strategies and validation sets.

If you need help running the training step or adapting this to GPU, tell me your environment and I will provide tailored instructions.
```
