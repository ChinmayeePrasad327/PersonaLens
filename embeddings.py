# embeddings.py
from sentence_transformers import SentenceTransformer

# Load a lightweight, high-performance model
# 'all-MiniLM-L6-v2' is fast and good for hackathons
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embedding(text):
    return model.encode(text)

def get_embeddings(text_list):
    return model.encode(text_list)