import streamlit as st
import json
import os
import pandas as pd

# Set up the page layout
st.set_page_config(page_title="Study Dashboard", layout="centered")

# File to store your progress so it doesn't reset
DATA_FILE = "study_data.json"

# The updated database of courses and lectures
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
st.write("Track your course completion with automated charts.")
st.divider()

# Load the current state of your courses
data = load_data()

# Loop through each course to build the dashboard UI
for course, lectures in data.items():
    st.subheader(f"📖 {course}")
    
    # 1. Calculate the counts
    total_lectures = len(lectures)
    completed_lectures = sum(1 for status in lectures.values() if status)
    remaining_lectures = total_lectures - completed_lectures
    
    # 2. Render the visual progress bar
    if total_lectures > 0:
        progress_decimal = completed_lectures / total_lectures
    else:
        progress_decimal = 0.0
    st.progress(progress_decimal, text=f"{completed_lectures}/{total_lectures} Lectures Finished")

    # 3. Add the Visual Chart
    if total_lectures > 0:
        # Prepare data for the chart
        chart_df = pd.DataFrame({
            "Status": ["Done", "Remaining"],
            "Count": [completed_lectures, remaining_lectures]
        })
        # Display as a horizontal bar chart for better mobile viewing
        st.bar_chart(chart_df, x="Status", y="Count", color="#4CAF50" if completed_lectures > remaining_lectures else "#FF4B4B")

    # 4. Create the Checklist (Inside an expander to save space)
    with st.expander(f"View {course} Chapters"):
        for lecture, is_done in lectures.items():
            checked = st.checkbox(lecture, value=is_done, key=f"{course}_{lecture}")
            
            # If the checkbox state changes, save and refresh
            if checked != is_done:
                data[course][lecture] = checked
                save_data(data)
                st.rerun()
            
    st.divider()

# Footer
st.caption("Custom built for Bandar Alharbi - 2026")
