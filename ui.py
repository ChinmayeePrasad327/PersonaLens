import streamlit as st
import requests
from personas import PERSONA_HIERARCHY  # Ensure personas.py is in the same folder

# Backend URL
API_URL = "http://localhost:8000"

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Insight AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (Modern UI Styles) ---
st.markdown("""
    <style>
    /* Import modern font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* Global Font Application */
    .stApp {
        background-color: #f8f9fa;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #1a1a2e;
        font-weight: 700;
    }
    
    /* Input Fields */
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        padding: 10px;
    }

    /* Gradient Button */
    .stButton > button {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Result Card Style */
    .result-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border-left: 5px solid #4b6cb7;
        margin-top: 20px;
    }
    .result-header {
        color: #4b6cb7;
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE MANAGEMENT ---
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.markdown("## 📂 Document Hub")
    st.caption("Upload your knowledge base.")

    # 1. MULTIPLE FILE UPLOADER
    uploaded_files = st.file_uploader(
        "Upload PDFs", 
        type=["pdf"], 
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    # Process files immediately upon selection
    if uploaded_files:
        # Check if there are any NEW files to process
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_files]
        
        if new_files:
            with st.status(f"⚙️ Processing {len(new_files)} new file(s)...", expanded=True) as status:
                for file in new_files:
                    try:
                        # Upload files one by one to the backend
                        files_payload = {"file": (file.name, file, "application/pdf")}
                        response = requests.post(f"{API_URL}/upload", files=files_payload)
                        
                        if response.status_code == 200:
                            st.session_state.processed_files.add(file.name)
                            st.write(f"✅ Indexed: {file.name}")
                        else:
                            st.error(f"❌ Failed: {file.name}")
                    except Exception as e:
                        st.error(f"⚠️ Connection Error: {e}")
                
                status.update(label="✅ Documents Ready!", state="complete", expanded=False)
    
    # Show list of active files
    if st.session_state.processed_files:
        st.markdown(f"**Active Documents ({len(st.session_state.processed_files)}):**")
        for fname in st.session_state.processed_files:
            st.caption(f"📄 {fname}")

    st.markdown("---")
    
    # 2. INDEPENDENT PERSONA SELECTION
    st.markdown("### 🎭 Analysis Mode")
    
    # Dropdown 1: Main Role
    main_roles = list(PERSONA_HIERARCHY.keys())
    selected_role = st.selectbox("I am a:", main_roles)
    
    # Dropdown 2: Sub-Persona (Dynamic based on Role)
    available_sub_personas = list(PERSONA_HIERARCHY[selected_role].keys())
    selected_sub = st.selectbox("My Goal is:", available_sub_personas)

# --- MAIN CONTENT AREA ---
col1, col2 = st.columns([1, 6])

with col2:
    st.title("Insight AI")
    st.markdown(f"Generate tailored insights as a **{selected_role}** focused on **{selected_sub}**.")

# Spacer
st.markdown("###")

if not st.session_state.processed_files:
    # Empty State Hero
    st.markdown("""
    <div style="text-align: center; padding: 50px; color: #666;">
        <h2>👋 Welcome!</h2>
        <p>Please upload one or more PDFs in the sidebar to get started.</p>
    </div>
    """, unsafe_allow_html=True)

else:
    # Query Interface
    query = st.text_input(
        "What would you like to know?", 
        placeholder="Leave empty to generate a full summary of the uploaded documents..."
    )

    # Dynamic Button Label
    btn_label = "✨ Generate Answer" if query else "📑 Generate Summary"

    if st.button(btn_label):
        with st.spinner("Analyzing document context..."):
            try:
                # Prepare Payload (Allow empty query)
                payload = {
                    "query": query if query else "", 
                    "main_persona": selected_role, 
                    "sub_persona": selected_sub
                }
                
                response = requests.post(f"{API_URL}/query", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data['answer']
                    
                    # Display Result in Custom Card
                    st.markdown(f"""
                        <div class="result-card">
                            <div class="result-header">🤖 AI Analysis ({selected_role} - {selected_sub})</div>
                            <div style="line-height: 1.6; color: #2d3436;">
                                {answer.replace(chr(10), '<br>')}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    st.error(f"Server Error: {response.text}")
                    
            except Exception as e:
                st.error(f"Connection Failed: {e}")