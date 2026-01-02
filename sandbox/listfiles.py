import streamlit as st

# Build a list of files in the sandbox/uploads directory
import os
file_list = os.listdir("sandbox/uploads")

@st.dialog("Delete file", dismissible=False)
def file_delete_confirmation(filename: str):
    st.text(f"Are you sure you want to delete the file '{filename}'?")
    if st.button("Yes, Delete File", type="primary"):
        os.remove(os.path.join("sandbox/uploads", filename))
        st.success(f"File '{filename}' deleted successfully!")
        st.rerun()
    if st.button("Cancel"):
        st.rerun()

st.title("Uploaded Files")
st.header("Files in sandbox/uploads")
if file_list:
    for filename in file_list:
        with st.container(horizontal=True, vertical_alignment="center"):
            if st.button("", key=filename, type="primary", icon=":material/delete:"):
                file_delete_confirmation(filename)
            st.text(filename)
