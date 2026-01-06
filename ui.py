import streamlit as st
import requests

# Backend URL
API_URL = "http://localhost:8000"

st.set_page_config(page_title="PDF Insight Tool", layout="centered")

# --- CUSTOM CSS FOR CLEAN LOOK ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #000000;
        color: white;
    }
    .main-header {
        text-align: center; 
        font-weight: 700;
        font-size: 30px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE MANAGEMENT ---
if "processed_file" not in st.session_state:
    st.session_state.processed_file = None

# --- HEADER ---
st.markdown('<div class="main-header">📄 Persona-Based PDF Analyzer</div>', unsafe_allow_html=True)

# --- 1. UPLOAD SECTION (Auto-Processing) ---
st.subheader("1. Upload Document")
uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"], label_visibility="collapsed")

if uploaded_file is not None:
    # Check if this file is new or already processed
    if st.session_state.processed_file != uploaded_file.name:
        with st.spinner("Processing document..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                response = requests.post(f"{API_URL}/upload", files=files)
                
                if response.status_code == 200:
                    st.session_state.processed_file = uploaded_file.name
                    st.success("File uploaded successfully!")
                else:
                    st.error("Failed to process file.")
            except Exception as e:
                st.error(f"Connection Error: {e}")

# --- 2. CONFIGURATION & INPUT ---
if st.session_state.processed_file:
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("2. Select Persona")
        persona_map = {
            "Student (Beginner)": "student_first_year",
            "Student (Exam Prep)": "student_exam_prep",
            "Researcher (Deep Dive)": "student_researcher",
            "Teacher (Lesson Plan)": "teacher_lesson_plan",
            "Gap Analysis": "researcher_gap_id"
        }
        selected_label = st.selectbox("Choose Persona", list(persona_map.keys()), label_visibility="collapsed")
        selected_persona_key = persona_map[selected_label]

    with col2:
        st.subheader("3. Your Question")
        user_query = st.text_input("Enter your query", placeholder="e.g. Summarize this topic", label_visibility="collapsed")

    # --- ACTION BUTTON ---
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Get Answer"):
        if not user_query:
            st.warning("Please enter a question.")
        else:
            with st.spinner("Generating answer..."):
                try:
                    payload = {"query": user_query, "persona": selected_persona_key}
                    response = requests.post(f"{API_URL}/query", json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # --- CLEAN OUTPUT DISPLAY ---
                        st.markdown("### Answer:")
                        st.info(data['answer'])
                        
                    else:
                        st.error("Could not generate answer.")
                        
                except Exception as e:
                    st.error(f"Error: {e}")

else:
    st.info("👆 Please upload a PDF to start.")