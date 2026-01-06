
import os
from groq import Groq
from dotenv import load_dotenv
from personas import get_persona_data

load_dotenv()

# 1. Initialize Groq Client
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

def generate_response(chunks, main_p, sub_p, user_query=None):
    """
    Generates a response using Groq (Llama 3.3).
    - If user_query is provided: Answers the specific question.
    - If user_query is empty/None: Generates a comprehensive summary based on the persona.
    """
    
    # Fetch persona details
    persona_info = get_persona_data(main_p, sub_p)
    
    # Context Construction
    # (Since chunks can come from multiple PDFs in the vector store, 
    # this implicitly handles multi-PDF context)
    context_text = "\n\n".join([c["chunk"] for c in chunks])
    
    # --- LOGIC FOR EMPTY QUERY (AUTO-SUMMARY) ---
    if not user_query or user_query.strip() == "":
        # Default instruction if no query is given
        task_specific_instruction = (
            "The user has not asked a specific question. "
            "Your task is to analyze the provided document content and generate a comprehensive summary. "
            "Highlight the main points, key themes, and conclusions relevant to your persona."
        )
        display_query = "Summarize the key points of the uploaded document(s)."
    else:
        # Instruction for specific questions
        task_specific_instruction = "Answer the user's specific question based strictly on the context provided."
        display_query = user_query

    # System Prompt
    system_prompt = f"""
    Role: You are an expert acting as a {main_p} with a focus on {sub_p}.
    Goal: {persona_info['intent']}
    Style Guide: {persona_info['prompt_style']}
    
    INSTRUCTIONS:
    1. {task_specific_instruction}
    2. Answer ONLY using the provided Context below.
    3. If the context contains information from multiple documents, synthesize them into a cohesive response.
    4. If the answer is missing in the text, say "Information not found."
    """
    
    # User Prompt
    user_prompt = f"""
    Context from Document(s):
    {context_text}
    
    User Request: {display_query}
    """

    try:
        # Call Groq API
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0.5,
        )
        
        return chat_completion.choices[0].message.content

    except Exception as e:
        return f"Error connecting to Groq: {str(e)}"