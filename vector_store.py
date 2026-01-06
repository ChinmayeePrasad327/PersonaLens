# vector_store.py
import faiss
import numpy as np

# Dimension of all-MiniLM-L6-v2 is 384
DIMENSION = 384 

class VectorStore:
    def __init__(self):
        self.index = faiss.IndexFlatL2(DIMENSION)
        self.chunks = [] # Metadata storage (1:1 mapping with index)

    def add_documents(self, chunk_list):
        if not chunk_list:
            return
        
        # Generate embeddings
        from embeddings import get_embeddings
        vectors = get_embeddings(chunk_list)
        
        # Add to FAISS
        self.index.add(np.array(vectors).astype('float32'))
        self.chunks.extend(chunk_list)

    def search(self, query_vector, k=10):
        D, I = self.index.search(np.array([query_vector]).astype('float32'), k)
        
        results = []
        for i, idx in enumerate(I[0]):
            if idx != -1:
                results.append({
                    "chunk": self.chunks[idx],
                    "score": float(D[0][i]) # L2 distance (lower is better)
                })
        return results

# Global instance for the hackathon prototype
store = VectorStore()