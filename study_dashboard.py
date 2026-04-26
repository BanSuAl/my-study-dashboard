import streamlit as st
import json
import os

# Set up the page layout
st.set_page_config(page_title="Study Dashboard", layout="centered")

# File to store your progress so it doesn't reset
DATA_FILE = "study_data.json"

# The updated database of courses and lectures
DEFAULT_DATA = {
    "CHE 306": {
        "Ch5 L1": False,
        "Ch7 L2": False,
        "Ch7 L3": False,
        "Ch7 L4": False,
        "Ch10 L5": False,
        "Ch10 L6": False,
        "Ch10 L7": False,
        "Ch12 L8": False,
        "Ch12 L9": False,
        "Ch12 L10": False,
        "Ch13 L11": False,
        "Ch13 L12": False,
        "Ch9 L13": False,
        "Ch9 L14": False,
        "Ch9 L15": False
    },
    "CHEM 311": {
        "Ch 35.1": False,
        "Ch 35.2": False,
        "Ch 35.3": False,
        "Ch 35.4": False,
        "Ch 35.5": False,
        "Ch 35.7": False,
        "Ch 35.8": False,
        "Ch 35.9": False,
        "Ch 35.10": False,
        "Ch 35.13": False,
        "Ch 35.14": False,
        "Ch 35.15": False,
        "Ch 36.1:": False,
        "Ch 36.2:": False,
        "Ch 36.3:": False,
        "Ch 36.4:": False,
        "Ch 36.5:": False,
        "Ch 36.6:": False
        
    },
    "CHE 309": {
        "Lab 1": False,
        "Lab 2": False,
        "Final Lab Prep": False
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

# Load the current state of your courses
data = load_data()

# Loop through each course to build the dashboard UI
for course, lectures in data.items():
    st.subheader(course)
    
    # Mathematical logic for the automated progress bar
    total_lectures = len(lectures)
    completed_lectures = sum(1 for status in lectures.values() if status)
    
    # Avoid division by zero
    if total_lectures > 0:
        progress_decimal = completed_lectures / total_lectures
    else:
        progress_decimal = 0.0
        
    # Render the visual progress bar
    st.progress(progress_decimal, text=f"{completed_lectures}/{total_lectures} Completed ({int(progress_decimal * 100)}%)")
    
    # Create the To-Do list for the course
    for lecture, is_done in lectures.items():
        # The key ensures Streamlit knows which specific box is being clicked
        checked = st.checkbox(lecture, value=is_done, key=f"{course}_{lecture}")
        
        # If the checkbox state changes, save the new state and refresh
        if checked != is_done:
            data[course][lecture] = checked
            save_data(data)
            st.rerun()
            
    st.divider()
