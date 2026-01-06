# relevance.py
from personas import get_persona_data

def calculate_hybrid_score(retrieved_chunks, main_p, sub_p, query_text):
    # Fetch data using the new helper function
    persona_data = get_persona_data(main_p, sub_p)
    target_keywords = persona_data.get("keywords", [])
    
    reranked_results = []
    
    for item in retrieved_chunks:
        chunk_text = item["chunk"].lower()
        base_score = 1 / (1 + item["score"]) 
        
        heuristic_score = 0
        
        # Keyword Overlap
        for kw in target_keywords:
            if kw in chunk_text:
                heuristic_score += 0.1
        
        # Query Overlap
        query_words = query_text.lower().split()
        overlap = sum(1 for word in query_words if word in chunk_text)
        heuristic_score += (overlap * 0.05)
        
        # Weighted Score
        final_score = (0.7 * base_score) + (0.3 * heuristic_score)
        
        reranked_results.append({
            "chunk": item["chunk"],
            "final_score": final_score
        })
    
    reranked_results.sort(key=lambda x: x["final_score"], reverse=True)
    return reranked_results