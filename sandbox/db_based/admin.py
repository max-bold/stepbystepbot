import streamlit as st

from typing import TYPE_CHECKING
import sys
import time

if TYPE_CHECKING:
    import database as db
else:
    if "streamlit" in sys.modules:
        import streamlit as st

        @st.cache_resource
        def get_models():
            import database as db
            return db

        db = get_models()
    else:
        import database as db


# simple startup timing to see where the first-run delay happens
_start_time = time.perf_counter()
_startup_marks: list[tuple[str, float]] = []


def _mark(label: str) -> None:
    _startup_marks.append((label, time.perf_counter()))


@st.dialog("Delete file", dismissible=False)
def file_delete_confirmation(file: db.File):
    st.text(f"Are you sure you want to delete the file '{file.filename}'?")
    if st.button("Yes, Delete File", type="primary"):
        db.delete_file(file.id)
        st.rerun()
    if st.button("Cancel"):
        st.rerun()


@st.dialog("Upload file", dismissible=True)
def file_upload_dialog(step: db.Step):
    uploaded_files = st.file_uploader("Upload Files", accept_multiple_files=True)
    with st.container(horizontal=True):
        if st.button("Upload"):
            db.add_files(step.id, uploaded_files)
            st.rerun()
        if st.button("Cancel"):
            st.rerun()


_mark("db import ready")
steps = db.get_all_steps()
_mark("loaded steps")
for step in steps:
    step_loop_start = time.perf_counter()
    with st.expander(f"Step {step.order}: {step.name}"):
        name = st.text_input("Step Name", value=step.name)
        text = st.text_area("Step Text", value=step.step_text)
        with st.container(border=True):
            files = db.get_files(step.id)
            _startup_marks.append((f"files for step {step.id}", time.perf_counter()))
            for file in files:
                with st.container(horizontal=True):
                    if st.button(
                        "",
                        type="primary",
                        icon=":material/delete:",
                        key=f"delete_file_{file.id}",
                    ):
                        file_delete_confirmation(file)
                    st.text(f"File: {file.filename}")
            if st.button(
                "Upload File",
                type="tertiary",
                icon=":material/upload_file:",
                key=f"upload_file_step_{step.id}",
            ):
                file_upload_dialog(step)
        if not name == step.name or not text == step.step_text:
            if st.button("Save Changes", type="primary", key=f"save_step_{step.id}"):
                db.update_step(step.id, name, text)
                st.rerun()

if st.session_state.get("adding_step", False):
    with st.form("add_step_form"):
        step_name = st.text_input("Step Name")
        step_text = st.text_area("Step Text")
        uploaded_files = st.file_uploader("Upload Files", accept_multiple_files=True)
        if st.form_submit_button("Add Step"):
            db.add_step(len(steps), step_name, step_text, uploaded_files)
            st.session_state["adding_step"] = False
            st.rerun()
        if st.form_submit_button("Cancel"):
            st.session_state["adding_step"] = False
            st.rerun()
else:
    if st.button("Add New Step", type="primary", icon=":material/add:"):
        st.session_state["adding_step"] = True
        st.rerun()


_mark("ui built")
if _startup_marks:
    timings = "\n".join(
        f"{label}: {(ts - _start_time) * 1000:.1f} ms" for label, ts in _startup_marks
    )
    st.caption("Startup timing (first run):\n" + timings)
