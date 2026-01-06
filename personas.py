# personas.py

PERSONA_HIERARCHY = {
    "Student": {
        "First Year (Basics)": {
            "intent": "Explain concepts using simple language and analogies.",
            "keywords": ["example", "basic", "introduction", "analogy", "what is"],
            "prompt_style": "Explain this like I am a beginner. Use real-world analogies."
        },
        "Exam Preparation": {
            "intent": "Identify definitions, key points, and potential exam questions.",
            "keywords": ["define", "important", "summary", "conclusion", "difference"],
            "prompt_style": "Generate exam-oriented questions (definitions, comparisons). Focus on key terms."
        },
        "Researcher (Deep Dive)": {
            "intent": "Analyze technical depth, assumptions, and references.",
            "keywords": ["assumption", "methodology", "reference", "limitations", "data"],
            "prompt_style": "Provide a technical analysis. Highlight methodology and gaps."
        }
    },
    "Teacher": {
        "Lesson Planning": {
            "intent": "Structure content for teaching, breaking it into modules.",
            "keywords": ["objectives", "outcome", "steps", "chapter", "teaching"],
            "prompt_style": "Create a structured lesson plan with learning objectives and timeline."
        },
        "Quiz Generation": {
             "intent": "Create short quizzes to test understanding.",
             "keywords": ["quiz", "test", "multiple choice", "question"],
             "prompt_style": "Create 5 multiple-choice questions with answers based on the text."
        }
    },
    "Researcher": {
        "Literature Review": {
             "intent": "Summarize related work and context.",
             "keywords": ["related work", "background", "context", "history"],
             "prompt_style": "Summarize the background and literature review sections."
        },
        "Gap Identification": {
            "intent": "Identify missing information and future research directions.",
            "keywords": ["gap", "future work", "unresolved", "limitation"],
            "prompt_style": "Critically analyze the text to find research gaps and limitations."
        }
    }
}

def get_persona_data(main_persona, sub_persona):
    """Safe lookup for nested dictionary"""
    try:
        return PERSONA_HIERARCHY[main_persona][sub_persona]
    except KeyError:
        # Fallback to a default if something goes wrong
        return PERSONA_HIERARCHY["Student"]["First Year (Basics)"]