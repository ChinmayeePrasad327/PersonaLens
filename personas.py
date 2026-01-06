# personas.py

PERSONAS = {
    "student_first_year": {
        "intent": "Explain concepts using simple language and basic examples.",
        "keywords": ["example", "basic", "introduction", "what is"],
        "prompt_style": "Explain this like I am a beginner. Use analogies."
    },
    "student_exam_prep": {
        "intent": "Identify definitions, key points, and potential exam questions.",
        "keywords": ["define", "important", "summary", "conclusion", "difference"],
        "prompt_style": "Generate exam-oriented questions (definitions, comparisons, explain why). Focus on key terms."
    },
    "student_researcher": {
        "intent": "Analyze technical depth, assumptions, and references.",
        "keywords": ["assumption", "methodology", "reference", "limitations", "data"],
        "prompt_style": "Provide a technical analysis. Highlight methodology and gaps."
    },
    "teacher_lesson_plan": {
        "intent": "Structure content for teaching, breaking it into modules.",
        "keywords": ["objectives", "outcome", "steps", "chapter"],
        "prompt_style": "Create a structured lesson plan with learning objectives."
    },
    "researcher_gap_id": {
        "intent": "Identify missing information and research gaps.",
        "keywords": ["gap", "future work", "unresolved", "limitation"],
        "prompt_style": "Critically analyze the text to find research gaps and limitations."
    }
}

def get_persona_prompt(persona_key):
    return PERSONAS.get(persona_key, PERSONAS["student_first_year"])