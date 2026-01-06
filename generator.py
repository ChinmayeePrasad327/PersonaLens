# generator.py (UPDATED GROQ VERSION)
import os
from groq import Groq
from dotenv import load_dotenv
from personas import get_persona_prompt

load_dotenv()

# 1. Initialize Groq Client
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

def generate_response(chunks, persona_key, user_query):
    persona_info = get_persona_prompt(persona_key)
    
    # Context
    context_text = "\n\n".join([c["chunk"] for c in chunks])
    
    # System Prompt (Persona)
    system_prompt = f"""
    You are an expert acting as: {persona_key}.
    Goal: {persona_info['intent']}
    Style: {persona_info['prompt_style']}
    
    INSTRUCTIONS:
    1. Answer ONLY using the provided Context.
    2. If the answer is missing, say "Information not found."
    3. Be concise and professional.
    """
    
    # User Prompt
    user_prompt = f"""
    Context:
    {context_text}
    
    Question: {user_query}
    """

    try:
        # 2. Call Groq with the NEW Model Name
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # UPDATED MODEL NAME BELOW:
            model="llama-3.3-70b-versatile", 
            temperature=0.5,
        )
        
        return chat_completion.choices[0].message.content

    except Exception as e:
        return f"Error connecting to Groq: {str(e)}"