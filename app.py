import json
import logging
import mimetypes
import re
from typing import Optional

import streamlit as st
from google import genai
from google.genai import types
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from prompts import SUMMARY_REQUEST_PROMPT, SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE

MODEL_NAME = "gemini-2.0-flash"

logger = logging.getLogger("macrosnap")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def validate_phone_number(phone_number: str) -> bool:
    """Validate a basic international phone format with country code."""
    if not phone_number or not phone_number.strip():
        return False
    cleaned = phone_number.strip()
    if cleaned.startswith("whatsapp:"):
        cleaned = cleaned.replace("whatsapp:", "", 1)
    if not cleaned.startswith("+"):
        return False
    digits = re.sub(r"\D", "", cleaned)
    return len(digits) >= 8 and len(digits) <= 15


def initialize_session_state():
    """Set required session variables once per browser session."""
    st.session_state.setdefault("profile_complete", False)
    st.session_state.setdefault("name", "")
    st.session_state.setdefault("whatsapp_number", "")
    st.session_state.setdefault("chat", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("pending_image", None)


@st.cache_resource
def get_gemini_client():
    """Create the Gemini client once per Streamlit session."""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

    if not api_key or not str(api_key).strip():
        return None

    try:
        return genai.Client(api_key=str(api_key).strip())
    except Exception:
        logger.exception("Gemini client initialization failed")
        return None


@st.cache_resource
def get_twilio_client():
    """Create the Twilio client once per Streamlit session."""
    try:
        account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
        auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
    except Exception:
        account_sid = ""
        auth_token = ""

    if not account_sid or not auth_token:
        return None

    try:
        return Client(str(account_sid).strip(), str(auth_token).strip())
    except Exception:
        logger.exception("Twilio client initialization failed")
        return None


def add_message(role: str, kind: str, content, **extra):
    """Append a message to the session conversation state."""
    st.session_state.messages.append({"role": role, "kind": kind, "content": content, **extra})


def render_message(message: dict):
    """Render a single message from the session history."""
    with st.chat_message(message["role"]):
        if message["kind"] == "image":
            st.image(message["content"], use_container_width=True)
            if message.get("caption"):
                st.caption(message["caption"])
        else:
            st.markdown(message["content"])


def clean_whatsapp_text(message: str) -> str:
    """Sanitize a summary before sending as a WhatsApp template variable."""
    text = message.strip()
    text = text.replace("```", "")
    text = re.sub(r"\*\*|__|~~", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text[:1400]
    return text.strip()


def get_chat_session():
    """Ensure the Gemini chat session is available with the MacroSnap system prompt."""
    client = get_gemini_client()
    if client is None:
        return None

    if st.session_state.chat is None:
        st.session_state.chat = client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
    return st.session_state.chat


def ask_gemini(prompt: str, image_bytes: Optional[bytes] = None, mime_type: str = "image/jpeg") -> Optional[str]:
    """Send a prompt to Gemini and return the assistant response."""
    client = get_gemini_client()
    if client is None:
        st.error("Gemini API key is missing. Add it to the Streamlit secrets configuration.")
        return None

    try:
        if image_bytes:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    types.Part.from_text(prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
        else:
            chat = get_chat_session()
            if chat is None:
                st.error("Gemini chat session could not be created.")
                return None
            response = chat.send_message(prompt)

        content = getattr(response, "text", None)
        if not content:
            text = str(response)
            return text[:2000] if text else "I could not generate a helpful answer for that image."
        return content.strip()
    except Exception:
        logger.exception("Gemini request failed")
        st.error("I couldn't analyze that request right now. Please check the Gemini configuration or try again.")
        return None


def send_whatsapp(summary_text: str, user_name: str, phone_number: str) -> bool:
    """Send a concise nutrition summary to the user via Twilio WhatsApp template API."""
    client = get_twilio_client()
    if client is None:
        st.error("Twilio is not configured. Add your account SID, auth token, and content template details.")
        return False

    if not validate_phone_number(phone_number):
        st.error("Please enter a valid WhatsApp number before sending the summary.")
        return False

    try:
        from_number = st.secrets.get("TWILIO_WHATSAPP_FROM", "")
        content_sid = st.secrets.get("TWILIO_CONTENT_SID", "")

        if not from_number or not content_sid:
            st.error("Twilio WhatsApp sender or content template is missing. Check the secrets configuration.")
            return False

        to_number = phone_number.strip()
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=str(content_sid).strip(),
            content_variables=json.dumps({"1": user_name, "2": summary_text}),
        )
        return True
    except TwilioException as exc:
        logger.exception("An error occurred while sending the Twilio WhatsApp summary")
        st.error(f"WhatsApp delivery failed. Please verify your Twilio template and sender configuration. Details: {exc}")
        return False
    except Exception:
        logger.exception("Unexpected Twilio error during message send")
        st.error("The summary could not be sent right now. Please verify the Twilio credentials and template.")
        return False


def show_onboarding():
    """Capture profile information before entering the main chat interface."""
    st.title("🥗 MacroSnap")
    st.caption("Snap it. Track it. Understand your food.")

    gemini_client = get_gemini_client()
    if gemini_client is None:
        st.warning("Gemini API key is missing. Add it to .streamlit/secrets.toml before continuing.")

    with st.form("onboarding_form"):
        name = st.text_input("Name", value=st.session_state.get("name", ""), placeholder="Enter your name")
        phone_number = st.text_input(
            "WhatsApp number with country code",
            value=st.session_state.get("whatsapp_number", ""),
            placeholder="+91XXXXXXXXXX",
        )

        submitted = st.form_submit_button("Start tracking")

        if submitted:
            cleaned_name = name.strip()
            cleaned_phone = phone_number.strip()

            if not cleaned_name:
                st.error("Name cannot be empty.")
                return
            if not validate_phone_number(cleaned_phone):
                st.error("Please enter a valid WhatsApp number with country code, for example +91XXXXXXXXXX.")
                return

            st.session_state.name = cleaned_name
            st.session_state.whatsapp_number = cleaned_phone
            st.session_state.profile_complete = True
            st.session_state.messages = []
            st.session_state.chat = None

            welcome_message = WELCOME_MESSAGE_TEMPLATE.format(name=cleaned_name)
            add_message("assistant", "text", welcome_message)

            if get_gemini_client() is not None:
                try:
                    st.session_state.chat = get_gemini_client().chats.create(
                        model=MODEL_NAME,
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                    )
                except Exception:
                    logger.exception("Failed to create Gemini chat session during onboarding")
                    st.warning("Your setup is saved, but Gemini chat is not available right now.")

            st.rerun()


def show_chat():
    """Display the main chat and nutrition assistant interface."""
    st.title("🥗 MacroSnap")
    st.caption("Snap it. Track it. Understand your food.")

    with st.sidebar:
        st.markdown("### Profile")
        st.write(f"👤 {st.session_state.name}")
        st.write(f"📱 {st.session_state.whatsapp_number}")

        if st.button("Reset session"):
            for key in ["name", "whatsapp_number", "profile_complete", "chat", "messages"]:
                st.session_state.pop(key, None)
            st.rerun()

    if not st.session_state.messages:
        welcome = WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name)
        add_message("assistant", "text", welcome)

    for message in st.session_state.messages:
        render_message(message)

    st.markdown("### Meal tracker")
    uploaded_file = st.file_uploader(
        "Upload a meal photo",
        type=["jpg", "jpeg", "png"],
        help="Include a clear meal photo when you want Gemini to estimate calories and macros.",
    )

    user_prompt = st.chat_input("Ask about your meal, calories, protein, or upload a food photo...")

    if uploaded_file is not None:
        st.session_state["pending_image"] = uploaded_file

    if user_prompt is not None:
        message_text = user_prompt.strip()
        uploaded = st.session_state.get("pending_image")

        if not message_text and uploaded is None:
            st.warning("Please type a meal question or upload a photo before sending.")
            st.stop()

        if uploaded is not None:
            image_bytes = uploaded.getvalue()
            image_mime_type = mimetypes.guess_type(uploaded.name)[0] or "image/jpeg"
            add_message("user", "image", image_bytes, caption=uploaded.name)

            if not message_text:
                message_text = "What is this meal? Estimate the calories and macros. Explain that the values are approximate."
            add_message("user", "text", message_text)

            with st.spinner("Analyzing your meal with Gemini..."):
                response = ask_gemini(message_text, image_bytes=image_bytes, mime_type=image_mime_type)
                if response:
                    add_message("assistant", "text", response)
            st.session_state.pop("pending_image", None)
            st.rerun()

        if message_text:
            add_message("user", "text", message_text)
            with st.spinner("Thinking..."):
                response = ask_gemini(message_text)
                if response:
                    add_message("assistant", "text", response)
            st.rerun()

    has_meal_history = any(message["role"] == "user" for message in st.session_state.messages)
    st.markdown("---")
    if st.button("📤 Send details to WhatsApp", disabled=not has_meal_history):
        try:
            meal_summary_prompt = (
                f"{SUMMARY_REQUEST_PROMPT}\n\n"
                "Here is the conversation log to summarize:\n"
                + "\n".join(
                    f"{message['role']}: {message['content']}"
                    for message in st.session_state.messages
                    if message["kind"] == "text"
                )
            )
            summary_response = ask_gemini(meal_summary_prompt)
            if not summary_response:
                st.error("I could not generate a WhatsApp summary from the meal history.")
            else:
                cleaned = clean_whatsapp_text(summary_response)
                if not cleaned:
                    st.error("The generated summary was empty. Please try again.")
                elif send_whatsapp(cleaned, st.session_state.name, st.session_state.whatsapp_number):
                    st.success("Sent! Check your WhatsApp 📲")
        except Exception:
            logger.exception("Error while generating WhatsApp summary")
            st.error("The message summary could not be prepared. Please try again.")


def main():
    """Run the MacroSnap app."""
    initialize_session_state()

    if not st.session_state.get("profile_complete", False):
        show_onboarding()
        return

    if not st.session_state.get("name") or not st.session_state.get("whatsapp_number"):
        show_onboarding()
        return

    try:
        st.write("")
        show_chat()
    except Exception:
        logger.exception("Application runtime error")
        st.error("Something went wrong while running MacroSnap. Please refresh and try again.")


if __name__ == "__main__":
    main()
