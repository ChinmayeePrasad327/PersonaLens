# relevance.py
from personas import PERSONAS

def calculate_hybrid_score(retrieved_chunks, persona_key, query_text):
    """
    Re-ranks FAISS results based on heuristic signals.
    """
    persona_data = PERSONAS.get(persona_key, PERSONAS["student_first_year"])
    target_keywords = persona_data.get("keywords", [])
    
    reranked_results = []
    
    for item in retrieved_chunks:
        chunk_text = item["chunk"].lower()
        base_score = 1 / (1 + item["score"]) # Convert L2 distance to Similarity (0-1)
        
        heuristic_score = 0
        
        # Signal 1: Keyword Overlap (Persona specific)
        for kw in target_keywords:
            if kw in chunk_text:
                heuristic_score += 0.1
        
        # Signal 2: Query Overlap
        query_words = query_text.lower().split()
        overlap = sum(1 for word in query_words if word in chunk_text)
        heuristic_score += (overlap * 0.05)
        
        # Signal 3: Definitions (Exam Persona)
        if "exam" in persona_key and ("is defined as" in chunk_text or "refers to" in chunk_text):
            heuristic_score += 0.2

        # Weighted Combination
        # 70% Semantic, 30% Heuristic
        final_score = (0.7 * base_score) + (0.3 * heuristic_score)
        
        reranked_results.append({
            "chunk": item["chunk"],
            "final_score": final_score
        })
    
    # Sort by final_score descending
    reranked_results.sort(key=lambda x: x["final_score"], reverse=True)
    
    return reranked_results