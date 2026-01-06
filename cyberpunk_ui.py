import streamlit as st
import requests
import time
from personas import PERSONA_HIERARCHY

# Backend URL
API_URL = "http://localhost:8000"

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="CyberGrid RAG",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (Cyberpunk Theme) ---
st.markdown("""
    <style>
    /* Import futuristic font */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Rajdhani:wght@300;500;700&display=swap');

    /* Global Theme */
    .stApp {
        background-color: #050510;
        background-image: 
            linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
        background-size: 30px 30px;
        color: #e0faff;
        font-family: 'Rajdhani', sans-serif;
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Orbitron', sans-serif;
        color: #00f3ff;
        text-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
        letter-spacing: 2px;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0a0a1a;
        border-right: 1px solid #bc13fe;
        box-shadow: 5px 0 15px rgba(188, 19, 254, 0.2);
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        background-color: #0f0f2d;
        color: #00f3ff;
        border: 1px solid #bc13fe;
        border-radius: 0px;
        font-family: 'Rajdhani', monospace;
    }
    .stTextInput > div > div > input:focus {
        border-color: #00f3ff;
        box-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
    }

    /* Selectbox */
    .stSelectbox > div > div {
        background-color: #0f0f2d;
        color: #00f3ff;
        border: 1px solid #bc13fe;
        border-radius: 0px;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(45deg, #bc13fe, #00f3ff);
        color: #000;
        border: none;
        border-radius: 0px; /* Cyberpunk sharp edges */
        padding: 12px 24px;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        text-transform: uppercase;
        width: 100%;
        clip-path: polygon(10% 0, 100% 0, 100% 70%, 90% 100%, 0 100%, 0 30%); /* Futuristic shape */
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 20px rgba(0, 243, 255, 0.8);
        color: white;
    }

    /* Mission Report Card (Response Area) */
    .mission-report {
        background: rgba(10, 10, 26, 0.9);
        border: 1px solid #00f3ff;
        border-left: 5px solid #00f3ff;
        border-right: 5px solid #bc13fe;
        padding: 25px;
        border-radius: 5px;
        box-shadow: 0 0 15px rgba(0, 243, 255, 0.2), inset 0 0 20px rgba(0, 0, 0, 0.5);
        position: relative;
        overflow: hidden;
        margin-top: 20px;
    }
    .mission-report::before {
        content: "STATUS: DECLASSIFIED";
        position: absolute;
        top: 5px;
        right: 10px;
        font-size: 0.7rem;
        color: #bc13fe;
        font-family: 'Orbitron';
        opacity: 0.7;
    }
    .report-header {
        color: #bc13fe;
        font-size: 1.2rem;
        font-family: 'Orbitron';
        margin-bottom: 15px;
        border-bottom: 1px solid rgba(188, 19, 254, 0.3);
        padding-bottom: 5px;
    }
    
    /* XP Bar Container */
    .xp-container {
        width: 100%;
        background-color: #1a1a2e;
        border: 1px solid #555;
        height: 20px;
        margin-bottom: 20px;
        position: relative;
    }
    
    /* XP Bar Fill */
    .xp-fill {
        height: 100%;
        background: linear-gradient(90deg, #bc13fe, #00f3ff);
        width: 0%; /* Dynamic */
        transition: width 0.5s ease;
        box-shadow: 0 0 10px #00f3ff;
    }
    
    .xp-text {
        position: absolute;
        width: 100%;
        text-align: center;
        top: 0;
        line-height: 20px;
        font-size: 0.7rem;
        color: #fff;
        font-weight: bold;
        text-shadow: 0 0 2px #000;
        z-index: 1;
    }

    /* Toast styling override (Streamlit toasts are hard to style fully, but we try generally) */
    
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE MANAGEMENT ---
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()
if "xp" not in st.session_state:
    st.session_state.xp = 0
if "level" not in st.session_state:
    st.session_state.level = 1

# --- SIDEBAR: LOADOUT ---
with st.sidebar:
    st.title("💾 CyberDeck Link")
    
    # XP Bar Display
    xp_percent = min(st.session_state.xp % 100, 100) # Simple loop for demo
    st.markdown(f"""
        <div style="margin-bottom: 5px; font-family: 'Orbitron'; color: #00f3ff; font-size: 0.8rem;">
            LEVEL {st.session_state.level} DISK
        </div>
        <div class="xp-container">
            <div class="xp-text">{st.session_state.xp} XP</div>
            <div class="xp-fill" style="width: {xp_percent}%;"></div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Load data shards into the neural net.")

    # 1. MULTIPLE FILE UPLOADER -> 'Equip Knowledge Crystal'
    uploaded_files = st.file_uploader(
        "Equip Knowledge Crystal (PDF)", 
        type=["pdf"], 
        accept_multiple_files=True
    )
    
    # Process files
    if uploaded_files:
        # Check for new files
        new_files = [f for f in uploaded_files if f.name not in st.session_state.processed_files]
        
        if new_files:
            with st.status(f"⚡ Initializing Upload Sequence...", expanded=True) as status:
                for file in new_files:
                    try:
                        # Upload to backend
                        files_payload = {"file": (file.name, file, "application/pdf")}
                        response = requests.post(f"{API_URL}/upload", files=files_payload)
                        
                        if response.status_code == 200:
                            st.session_state.processed_files.add(file.name)
                            st.write(f"🟢 Integrated: {file.name}")
                            
                            # GAMIFICATION: Add XP and Toast
                            st.session_state.xp += 20
                            if st.session_state.xp >= 100:
                                st.session_state.level += 1
                                st.session_state.xp = 0 # Preset logic
                                st.toast(f"🎉 LEVEL UP! You are now Level {st.session_state.level}!", icon="🆙")
                            
                            # Achievement Unlock
                            st.toast("🏆 Achievement Unlocked: Data Hoarder", icon="💾")
                            
                        else:
                            st.error(f"🔴 Upload Failed: {file.name}")
                    except Exception as e:
                        st.error(f"⚠️ Netrunner Error: {e}")
                
                status.update(label="✅ Data Synchronization Complete", state="complete", expanded=False)
                # Force rerun to update XP bar instantly
                time.sleep(1)
                st.rerun()

    # List active files
    if st.session_state.processed_files:
        st.markdown(f"**<span style='color:#00f3ff'>Active Shards ({len(st.session_state.processed_files)}):</span>**", unsafe_allow_html=True)
        for fname in st.session_state.processed_files:
            st.caption(f"🔮 {fname}")

    st.markdown("---")
    
    # 2. SELECTION -> 'Choose Character Class'
    st.markdown("### 🧬 Avatar Config")
    
    main_roles = list(PERSONA_HIERARCHY.keys())
    selected_role = st.selectbox("Choose Character Class:", main_roles)
    
    available_sub_personas = list(PERSONA_HIERARCHY[selected_role].keys())
    selected_sub = st.selectbox("Select Specialization:", available_sub_personas)

# --- MAIN CONTENT ---
col1, col2 = st.columns([1, 8])

with col2:
    st.markdown("# 🏙️ NEON CITY <span style='color:#bc13fe'>INTEL</span>", unsafe_allow_html=True)
    st.markdown(f"Operating as **<span style='color:#00f3ff'>{selected_role}</span>** | Spec: **<span style='color:#bc13fe'>{selected_sub}</span>**", unsafe_allow_html=True)

st.markdown("###")

if not st.session_state.processed_files:
    # Empty State
    st.markdown("""
    <div style="text-align: center; padding: 50px; border: 1px dashed #333; border-radius: 10px;">
        <h2 style="color: #00f3ff;">⚠️ SYSTEM OFFLINE</h2>
        <p style="color: #888;">Equip a Knowledge Crystal to power up the inference engine.</p>
    </div>
    """, unsafe_allow_html=True)

else:
    # Query -> 'Execute Mission'
    query = st.text_input(
        "Execute Mission (Enter Query Directive):", 
        placeholder="Awaiting command input..."
    )

    # Button -> 'Cast Analysis Spell'
    btn_label = "⚡ Cast Analysis Spell" if query else "📑 Run System Diagnostics (Summary)"

    if st.button(btn_label):
        with st.spinner("🔄 Decrypting Neural Patterns..."):
            try:
                payload = {
                    "query": query if query else "", 
                    "main_persona": selected_role, 
                    "sub_persona": selected_sub
                }
                
                response = requests.post(f"{API_URL}/query", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data['answer']
                    
                    # Display Result in Mission Report Card
                    st.markdown(f"""
                        <div class="mission-report">
                            <div class="report-header">💾 MISSION REPORT // {selected_role.upper()}</div>
                            <div style="line-height: 1.6; color: #e0faff; font-family: 'Rajdhani', sans-serif; font-size: 1.1rem;">
                                {answer.replace(chr(10), '<br>')}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                else:
                    st.error(f"🔴 Mainframe Error: {response.text}")
                    
            except Exception as e:
                st.error(f"⚠️ Connection Terminated: {e}")
