import asyncio
import streamlit as st
import json
import datetime as dt
from dotenv import load_dotenv
import os
import hashlib
import secrets
import requests
import re

load_dotenv()
admin_password = os.getenv("ADMIN_PASSWORD")
admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH")
admin_password_salt = os.getenv("ADMIN_PASSWORD_SALT")
reload_api_url = os.getenv("RELOAD_API_URL", "http://localhost:8000")
log_file_path = os.getenv("BOT_LOG_PATH", "bot.log")


async def start_admin_panel() -> asyncio.subprocess.Process | None:
    try:
        process = await asyncio.create_subprocess_exec(
            "streamlit",
            "run",
            "admin.py",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return process
    except FileNotFoundError:
        return None


async def stop_admin_panel(process: asyncio.subprocess.Process | None) -> None:
    if process is None or process.returncode is not None:
        return
    process.terminate()
    await process.wait()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()


def is_admin_password_valid(password: str) -> bool:
    if admin_password_hash and admin_password_salt:
        return secrets.compare_digest(
            _hash_password(password, admin_password_salt), admin_password_hash
        )
    if not admin_password:
        return False
    return secrets.compare_digest(password, admin_password)


def notify_reload(endpoint: str) -> None:
    try:
        response = requests.post(f"{reload_api_url}{endpoint}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        st.warning(f"Failed to notify bot about changes: {exc}")


def request_promo_code() -> str | None:
    try:
        response = requests.post(f"{reload_api_url}/promo/generate", timeout=5)
        response.raise_for_status()
        return response.json().get("code")
    except requests.RequestException as exc:
        st.warning(f"Failed to generate promo code: {exc}")
        return None


def render_login_form() -> None:
    if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
        st.info("Please log in to access the admin panel.")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Log In"):
            if username == "admin" and is_admin_password_valid(password):
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
                notify_reload("/reload/script")
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
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                st.session_state["settings"] = json.load(f)
        except FileNotFoundError:
            with open("default_settings.json", "r", encoding="utf-8") as f:
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
        settings["payment_amount"] = st.number_input(
            "Payment amount (RUB)",
            min_value=1,
            value=int(settings.get("payment_amount", 100)),
            step=1,
            on_change=settings_changed,
        )
        settings["goods_name"] = st.text_input(
            "Название товара (для чека)",
            value=settings.get("goods_name", ""),
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

            if key == "next_step_timeout":
                st.caption(
                    'Where {time} will be replaced with time in "HH:MM МСК" format'
                )

    if "settings_changed" in st.session_state and st.session_state["settings_changed"]:
        if st.button("Save Settings", type="primary"):
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            notify_reload("/reload/settings")
            st.session_state["settings"] = settings
            st.session_state["settings_changed"] = False
            st.rerun()


def promo_codes_page():
    st.title("Promo Codes")
    st.write("Generate a new promo code using the bot API.")
    if st.button("Generate promo code", type="primary"):
        code = request_promo_code()
        if code:
            st.success("Promo code generated:")
            st.code(code)


def logs_page():
    st.title("Bot Logs")
    st.write(f"Log file: {log_file_path}")
    st.caption("Logs are rotated daily by the bot (TimedRotatingFileHandler).")
    st.button("Refresh logs", type="primary")
    log_level = st.selectbox(
        "Filter by level",
        ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        index=0,
    )
    try:
        with open(log_file_path, "r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
        if log_level != "ALL":
            level_pattern = re.compile(rf" - {log_level} - ")
            lines = [line for line in lines if level_pattern.search(line)]
        log_preview_lines = lines[-500:]
        colored_lines = []
        for line in log_preview_lines:
            if " - ERROR - " in line or " - CRITICAL - " in line:
                color = "#dc3545"
            elif " - WARNING - " in line:
                color = "#f0ad4e"
            elif " - INFO - " in line:
                color = "#0d6efd"
            elif " - DEBUG - " in line:
                color = "#6c757d"
            else:
                color = "#212529"
            colored_lines.append(
                f'<span style="color: {color}; font-family: monospace;">{line.rstrip()}</span>'
            )
        st.markdown(
            "<br>".join(colored_lines) or "_No logs to display_",
            unsafe_allow_html=True,
        )
    except FileNotFoundError:
        st.warning("Log file not found.")
    try:
        log_dir = os.path.dirname(log_file_path) or "."
        log_name = os.path.basename(log_file_path)
        rotated = sorted(
            [fname for fname in os.listdir(log_dir) if fname.startswith(log_name + ".")]
        )
        if rotated:
            st.caption(f"Rotated logs: {', '.join(rotated)}")
    except OSError:
        st.warning("Unable to list rotated logs.")


def run_admin_app() -> None:
    render_login_form()

    if "logged_in" in st.session_state and st.session_state["logged_in"]:
        page = st.navigation(
            [
                st.Page(steps_page, title="Manage Steps"),
                st.Page(setings_page, title="Settings"),
                st.Page(promo_codes_page, title="Promo Codes"),
                st.Page(logs_page, title="Logs"),
            ],
            position="top",
        )
        page.run()


if __name__ == "__main__":
    run_admin_app()
