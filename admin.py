import streamlit as st
import json
import datetime as dt

if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    st.info("Please log in to access the admin panel.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Log In"):
        if username == "admin" and password == "password":
            st.session_state["logged_in"] = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")


def steps_page():

    def changed():
        st.session_state["changed"] = True

    def remove_content(script, step_index, content_index):
        script[step_index]["content"].pop(content_index)
        changed()

    if "script" not in st.session_state:
        with open("script.json", "r", encoding="utf-8") as f:
            st.session_state["script"] = json.load(f)
    script = st.session_state["script"]
    st.title("Manage Steps")

    for i, step in enumerate(script):
        with st.expander(f"Step {i}: {step['title']}") as ex:
            step["title"] = st.text_input(
                f"Title",
                value=step["title"],
                key=f"title_{i}",
                on_change=changed,
            )
            step["description"] = st.text_area(
                f"Description",
                value=step["description"],
                key=f"description_{i}",
                on_change=changed,
            )

            for j, content in enumerate(step["content"]):
                with st.container(border=True):
                    content_type = content.get("type", None)

                    c1, c2 = st.columns([10, 1])
                    with c1:
                        st.text(content_type)
                    with c2:
                        st.button(
                            "",
                            key=f"remove_step_{i}_content_{j}",
                            on_click=remove_content,
                            args=(script, i, j),
                            icon=":material/delete:",
                            help="Remove this content item",
                            width="stretch",
                        )
                    if content_type == "text":
                        content["value"] = st.text_area(
                            f"Text",
                            value=content["value"],
                            key=f"step_{i}_content_{j}_text",
                            on_change=changed,
                        )
                    else:
                        content["file_id"] = st.text_input(
                            f"File ID",
                            value=content["file_id"],
                            key=f"step_{i}_content_{j}_photo_file_id",
                            on_change=changed,
                        )
                        content["caption"] = st.text_input(
                            f"Caption",
                            value=content["caption"],
                            key=f"step_{i}_content_{j}_photo_caption",
                            on_change=changed,
                        )

            c1, c2 = st.columns([9, 1])
            with c1:
                with st.container(horizontal=True):
                    if st.button(
                        "",
                        key=f"add_text_step_{i}",
                        icon=":material/text_fields:",
                        help="Add text content",
                    ):
                        step["content"].append({"type": "text", "value": ""})
                        changed()
                        st.rerun()

                    if st.button(
                        "",
                        key=f"add_photo_step_{i}",
                        icon=":material/image:",
                        help="Add photo content",
                    ):
                        step["content"].append(
                            {"type": "photo", "file_id": "", "caption": ""}
                        )
                        changed()
                        st.rerun()

                    if st.button(
                        "",
                        key=f"add_video_step_{i}",
                        icon=":material/videocam:",
                        help="Add video content",
                    ):
                        step["content"].append(
                            {"type": "video", "file_id": "", "caption": ""}
                        )
                        changed()
                        st.rerun()

                    if st.button(
                        "",
                        key=f"add_video_note_step_{i}",
                        icon=":material/fiber_manual_record:",
                        help="Add video note content",
                    ):
                        step["content"].append(
                            {"type": "video note", "file_id": "", "caption": ""}
                        )
                        changed()
                        st.rerun()

                    if st.button(
                        "",
                        key=f"add_audio_step_{i}",
                        icon=":material/audiotrack:",
                        help="Add audio content",
                    ):
                        step["content"].append(
                            {"type": "audio", "file_id": "", "caption": ""}
                        )
                        changed()
                        st.rerun()

                    if st.button(
                        "",
                        key=f"add_voice_step_{i}",
                        icon=":material/keyboard_voice:",
                        help="Add voice content",
                    ):
                        step["content"].append(
                            {"type": "voice", "file_id": "", "caption": ""}
                        )
                        changed()
                        st.rerun()

                    if st.button(
                        "",
                        key=f"add_document_step_{i}",
                        icon=":material/description:",
                        help="Add document content",
                    ):
                        step["content"].append(
                            {"type": "document", "file_id": "", "caption": ""}
                        )
                        changed()
                        st.rerun()
            with c2:
                if st.button(
                    "",
                    key=f"remove_step_{i}",
                    icon=":material/delete:",
                    help="Remove this step",
                    width="stretch",
                    type="primary",
                ):
                    script.pop(i)
                    changed()
                    st.rerun()
    with st.container(horizontal=True):

        if "changed" in st.session_state and st.session_state["changed"]:
            if st.button("Save All", type="primary"):
                with open("script.json", "w", encoding="utf-8") as f:
                    json.dump(script, f, indent=4, ensure_ascii=False)
                st.session_state["changed"] = False
                st.success("Changes saved successfully!")
                st.rerun()

        if st.button("Add New Step", type="secondary"):
            script.append({"title": "New Step", "description": "", "content": []})
            st.session_state["changed"] = True
            st.rerun()


def setings_page():

    def settings_changed():
        st.session_state["settings_changed"] = True

    if True:  # "settings" not in st.session_state:
        with open("settings.json", "r", encoding="utf-8") as f:
            st.session_state["settings"] = json.load(f)
    settings = st.session_state["settings"]

    st.title("Settings")
    with st.container(border=True):
        st.text("General Settings")
        settings["create_paid_users"] = st.toggle(
            "Create paid users (for debugging)",
            settings["create_paid_users"],
            on_change=settings_changed,
        )
    with st.container(border=True):
        st.text("Notifications Settings")
        settings["next_step_delay"]["type"] = st.selectbox(
            "Next Step Delay Type",
            options=["Period", "Fixed time"],
            index=0 if settings["next_step_delay"]["type"] == "Period" else 1,
            on_change=settings_changed,
        )
        if settings["next_step_delay"]["type"] == "Period":
            label = "Next Step Delay HH:MM"
        else:
            label = "Next Step Delivery Time HH:MM"
        value = settings["next_step_delay"]["value"]
        h = value // 3600
        m = (value % 3600) // 60
        time = dt.time(h, m)
        time = st.time_input(
            label,
            value=time,
            on_change=settings_changed,
        )
        value = time.hour * 3600 + time.minute * 60 + time.second
        settings["next_step_delay"]["value"] = value

    with st.container(border=True):
        st.text("Messages and texts")
        for key, value in settings["messages"].items():
            settings["messages"][key] = st.text_area(
                key,
                value,
                on_change=settings_changed,
            )

            if key == "step_invite":
                st.caption(
                    "Available placeholders: {step_number}, {title}, {description}"
                )

    if "settings_changed" in st.session_state and st.session_state["settings_changed"]:
        if st.button("Save Settings", type="primary"):
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            st.session_state["settings"] = settings
            st.session_state["settings_changed"] = False
            st.rerun()


if "logged_in" in st.session_state and st.session_state["logged_in"]:
    page = st.navigation(
        [
            st.Page(steps_page, title="Manage Steps"),
            st.Page(setings_page, title="Settings"),
        ],
        position="top",
    )
    page.run()
