from turtle import save
import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

def save_file(uploaded: UploadedFile) -> None:
    bytes_data = uploaded.read()
    with open(f"sandbox/uploads/{uploaded.name}", "wb") as f:
        f.write(bytes_data)

uploaded_file = st.file_uploader("Choose a file", accept_multiple_files=True)
for file in uploaded_file:
    if file is not None:
        save_file(file)
        st.success(f"Saved file: {file.name}")