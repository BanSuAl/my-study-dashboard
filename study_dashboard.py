import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px

# Set up the page layout
st.set_page_config(page_title="Study Dashboard", layout="centered")

# File to store your progress so it doesn't reset
DATA_FILE = "study_data.json"

# Your Course Database
DEFAULT_DATA = {
    "CHE 306": {
        "Ch5 L1": False, "Ch7 L2": False, "Ch7 L3": False, "Ch7 L4": False,
        "Ch10 L5": False, "Ch10 L6": False, "Ch10 L7": False, "Ch12 L8": False,
        "Ch12 L9": False, "Ch12 L10": False, "Ch13 L11": False, "Ch13 L12": False,
        "Ch9 L13": False, "Ch9 L14": False, "Ch9 L15": False
    },
    "CHEM 311": {
        "Ch 35.1": False, "Ch 35.2": False, "Ch 35.3": False, "Ch 35.4": False,
        "Ch 35.5": False, "Ch 35.7": False, "Ch 35.8": False, "Ch 35.9": False,
        "Ch 35.10": False, "Ch 35.13": False, "Ch 35.14": False, "Ch 35.15": False,
        "Ch 36.1": False, "Ch 36.2": False, "Ch 36.3": False, "Ch 36.4": False,
        "Ch 36.5": False, "Ch 36.6": False
    },
    "CHE 309": {
        "HT part": False, "MT Part": False, "FM Part": False, "Final Lab Prep": False
    },
    "CHE 360": {
        "unit 6": False, "unit 8": False, "unit 9": False, "Project": False
    },
    "GS 495": {
        "week 8 & 9": False, "week 10": False, "week 11": False, "week 12": False, "Project": False
    },
    "CHEM 312": {
        "The Laboratory Safety, Lab Report/Rejection Rule, and Density": False,
        "Absorption Spectrum of Conjugated Dye": False,
        "Gas Viscosity": False,
        "Kinetics Using Spectroscopy": False,
        "Fluorescence quenching of Rhodamine B Dye": False,
        "Adsorption Isotherm of Acetic Acid": False
    }
}

# Function to load saved data or start fresh
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_DATA

# Function to save data when you click a checkbox
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

st.title("📚 Study Progress Dashboard")
st.divider()

# Load the current state
data = load_data()

# Loop through courses
for course, lectures in data.items():
    st.header(f"📖 {course}")
    
    total = len(lectures)
    done = sum(1 for status in lectures.values() if status)
    remaining = total - done
    
    # Progress Bar
    percent = (done / total) if total > 0 else 0
    st.progress(percent, text=f"{int(percent*100)}% Complete")

    # Pie Chart Logic
    if total > 0:
        df = pd.DataFrame({
            "Status": ["Completed", "Remaining"],
            "Count": [done, remaining]
        })
        
        fig = px.pie(
            df, 
            values='Count', 
            names='Status', 
            color='Status',
            color_discrete_map={'Completed': '#2ecc71', 'Remaining': '#e74c3c'},
            hole=0.4
        )
        
        fig.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            height=300,
            showlegend=True
        )
        
        # ADDED THE KEY HERE TO FIX THE ERROR
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{course}")

    # Checklist
    with st.expander(f"Update {course} Chapters"):
        for lecture, is_done in lectures.items():
            checked = st.checkbox(lecture, value=is_done, key=f"{course}_{lecture}")
            if checked != is_done:
                data[course][lecture] = checked
                save_data(data)
                st.rerun()
            
    st.divider()

st.caption("Updated April 2026 | KFUPM Student Dashboard")
