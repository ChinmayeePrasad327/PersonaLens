# app.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import logic modules
from pdf_processor import extract_text_from_pdf
from chunker import split_text
from vector_store import store
from embeddings import get_embedding
from relevance import calculate_hybrid_score
from generator import generate_response

app = FastAPI(title="Persona-Based RAG System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- UPDATED REQUEST MODEL ---
class QueryRequest(BaseModel):
    query: str
    main_persona: str  # e.g., "Student"
    sub_persona: str   # e.g., "Exam Preparation"

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        content = await file.read()
        raw_text = extract_text_from_pdf(content)
        chunks = split_text(raw_text)
        
        # NOTE: We DO NOT reset the store here to allow multiple file uploads
        # store.index.reset() 
        # store.chunks = []

        store.add_documents(chunks)
        
        return {"message": "PDF processed", "chunks_count": len(chunks)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_system(request: QueryRequest):
    if not store.chunks:
        raise HTTPException(status_code=400, detail="No documents uploaded.")

    # --- FIX START ---
    # Handle Empty Query (Summary Mode)
    if not request.query or request.query.strip() == "":
        # If query is empty, use a generic keyword to fetch broad context
        query_vec = get_embedding("summary main points overview")
    else:
        # If query exists, embed it normally
        query_vec = get_embedding(request.query)

    # Now 'initial_results' is ALWAYS defined
    initial_results = store.search(query_vec, k=15)
    # --- FIX END ---

    # Calculate scores
    ranked_results = calculate_hybrid_score(
        initial_results, 
        request.main_persona, 
        request.sub_persona, 
        request.query if request.query else "" # Pass empty string if None
    )
    
    top_k = ranked_results[:5]
    
    # Generate response
    answer = generate_response(
        top_k, 
        request.main_persona, 
        request.sub_persona, 
        request.query # Pass raw query (None or string)
    )
    
    return {"answer": answer, "context": [r["chunk"] for r in top_k]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)