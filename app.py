# app.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

# Import your logic modules
from pdf_processor import extract_text_from_pdf
from chunker import split_text
from vector_store import store
from embeddings import get_embedding
from relevance import calculate_hybrid_score
from generator import generate_response

app = FastAPI(title="Persona-Based RAG System")

# --- ENABLE CORS FOR FRONTEND COMMUNICATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (ok for hackathons)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    persona: str

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        content = await file.read()
        raw_text = extract_text_from_pdf(content)
        chunks = split_text(raw_text)
        
        # Reset store for demo purposes (optional)
        # store.index.reset() 
        # store.chunks = []

        store.add_documents(chunks)
        
        return {
            "message": "PDF processed successfully", 
            "filename": file.filename,
            "chunks_count": len(chunks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_system(request: QueryRequest):
    if not store.chunks:
        raise HTTPException(status_code=400, detail="No documents uploaded yet.")

    # 1. Embed & Search
    query_vec = get_embedding(request.query)
    initial_results = store.search(query_vec, k=20) # Fetch more for reranking
    
    # 2. Rerank (Hybrid Score)
    ranked_results = calculate_hybrid_score(initial_results, request.persona, request.query)
    top_k = ranked_results[:5]
    
    # 3. Generate
    answer = generate_response(top_k, request.persona, request.query)
    
    return {
        "persona": request.persona,
        "answer": answer,
        "context": [r["chunk"] for r in top_k],
        "scores": [r["final_score"] for r in top_k]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)