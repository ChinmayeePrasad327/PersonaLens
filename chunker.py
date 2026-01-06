# chunker.py

def split_text(text, chunk_size=300, overlap=50):
    """
    Simple sliding window chunker. 
    In production, use RecursiveCharacterTextSplitter from LangChain for better results.
    """
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        
    return chunks