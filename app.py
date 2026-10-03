import re

import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE
)


# =====================================================
# APP CONFIGURATION
# =====================================================

MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(
    page_title="Snap & Study",
    page_icon="📚"
)


# =====================================================
# LOAD SECRETS
# =====================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]


# =====================================================
# CREATE GEMINI CLIENT
# =====================================================

@st.cache_resource
def get_gemini_client():

    return genai.Client(
        api_key=GEMINI_API_KEY
    )


# =====================================================
# CREATE TWILIO CLIENT
# =====================================================

@st.cache_resource
def get_twilio_client():

    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# =====================================================
# DISPLAY CHAT MESSAGE
# =====================================================

def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":

            st.write(message["content"])

        elif message["kind"] == "image":

            st.image(
                message["content"],
                use_container_width=True
            )


# =====================================================
# ADD MESSAGE
# =====================================================

def add_message(role, kind, content):

    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content
        }
    )

    render_message(
        st.session_state.messages[-1]
    )


# =====================================================
# ASK GEMINI
# =====================================================

def ask_gemini(parts):

    try:

        response = st.session_state.chat.send_message(
            parts
        )

        return response.text

    except Exception as error:

        return (
            "Sorry, something went wrong.\n\n"
            f"Error: {error}"
        )


# =====================================================
# NORMALIZE WHATSAPP NUMBER
# =====================================================

def normalize_whatsapp_number(phone_number):

    number = phone_number.strip()

    # Remove whatsapp: if user enters it
    if number.lower().startswith("whatsapp:"):

        number = number[len("whatsapp:"):].strip()

    # Remove spaces, brackets, dots and hyphens
    number = re.sub(
        r"[\s().-]",
        "",
        number
    )

    # Validate international number
    if not re.fullmatch(
        r"\+[1-9]\d{7,14}",
        number
    ):

        raise ValueError(
            "Enter a valid WhatsApp number with country code, "
            "for example +919876543210."
        )

    return number


# =====================================================
# CLEAN WHATSAPP TEXT
# =====================================================

def clean_whatsapp_text(text):

    if not text:

        return "No study summary available."

    text = text.strip()

    # Keep message reasonably sized
    if len(text) > 4000:

        text = text[:4000] + "..."

    return text


# =====================================================
# SEND WHATSAPP MESSAGE
# =====================================================

def send_whatsapp(
    to_number,
    user_name,
    summary
):

    try:

        whatsapp_message = f"""📚 SNAP & STUDY

Hi {user_name}! 👋

Here is your study summary:

{clean_whatsapp_text(summary)}

Keep learning! 🚀
"""


        message = twilio_client.messages.create(

            from_=TWILIO_WHATSAPP_FROM,

            to=f"whatsapp:{to_number}",

            body=whatsapp_message

        )


        # We only need to know that Twilio accepted
        # the message request.

        return True, message.sid


    except Exception as error:

        return False, str(error)


# =====================================================
# CREATE NEW GEMINI CHAT
# =====================================================

def create_new_chat():

    return gemini_client.chats.create(

        model=MODEL_NAME,

        config=types.GenerateContentConfig(

            system_instruction=SYSTEM_PROMPT

        )

    )


# =====================================================
# STEP 1 — ONBOARDING
# =====================================================

if "onboarded" not in st.session_state:

    st.title("📚 Snap & Study")

    st.caption(
        "Snap it. Understand it. Learn it."
    )


    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name"
        )


        whatsapp_number = st.text_input(

            "WhatsApp number (with country code)",

            placeholder="+91XXXXXXXXXX",

            help=(
                "This is the number Snap & Study "
                "will send your study summary to."
            )

        )


        submitted = st.form_submit_button(
            "Let's go 🚀"
        )


        if submitted:

            if (
                not name.strip()
                or not whatsapp_number.strip()
            ):

                st.warning(
                    "Please fill in both your name "
                    "and WhatsApp number."
                )

            else:

                try:

                    whatsapp_number = (
                        normalize_whatsapp_number(
                            whatsapp_number
                        )
                    )

                except ValueError as error:

                    st.error(str(error))

                    st.stop()


                st.session_state.name = (
                    name.strip()
                )


                st.session_state.whatsapp_number = (
                    whatsapp_number
                )


                # Create Gemini conversation

                st.session_state.chat = (
                    create_new_chat()
                )


                # Start empty chat history

                st.session_state.messages = []


                # Store last AI answer

                st.session_state.last_answer = ""


                # Mark onboarding complete

                st.session_state.onboarded = True


                st.rerun()


    st.stop()


# =====================================================
# STEP 2 — MAIN CHAT
# =====================================================


# -----------------------------------------------------
# HEADER
# -----------------------------------------------------

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)


with header_col:

    st.title("📚 Snap & Study")


with button_col:

    if st.button(
        "🔄 New Chat",
        use_container_width=True
    ):

        st.session_state.chat = (
            create_new_chat()
        )

        st.session_state.messages = []

        st.session_state.last_answer = ""

        st.rerun()


# =====================================================
# USER INFORMATION
# =====================================================

st.caption(

    f"Logged in as {st.session_state.name} - "
    f"study summaries go to "
    f"{st.session_state.whatsapp_number}"

)


# =====================================================
# SHOW CHAT HISTORY
# =====================================================

if not st.session_state.messages:

    add_message(

        "assistant",

        "text",

        WELCOME_MESSAGE_TEMPLATE.format(

            name=st.session_state.name

        )

    )

else:

    for message in st.session_state.messages:

        render_message(message)


# =====================================================
# CHAT INPUT
# =====================================================

user_input = st.chat_input(

    "Ask a study question, or attach a study photo",

    accept_file=True,

    file_type=[
        "jpg",
        "jpeg",
        "png",
        "webp"
    ]

)


# =====================================================
# PROCESS USER INPUT
# =====================================================

if user_input:

    photo = (

        user_input.files[0]

        if user_input.files

        else None

    )


    text = (

        user_input.text.strip()

        if user_input.text

        else ""

    )


    parts = []


    # -------------------------------------------------
    # IMAGE
    # -------------------------------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()


        add_message(

            "user",

            "image",

            photo_bytes

        )


        parts.append(

            types.Part.from_bytes(

                data=photo_bytes,

                mime_type=photo.type

            )

        )


    # -------------------------------------------------
    # TEXT
    # -------------------------------------------------

    if text:

        add_message(

            "user",

            "text",

            text

        )


        parts.append(text)


    # -------------------------------------------------
    # IMAGE ONLY
    # -------------------------------------------------

    elif photo is not None:

        parts.append(

            """
Analyze this study material carefully.

The image may contain textbook pages,
class notes, handwritten notes, questions,
diagrams, formulas, tables, or other
educational material.

Explain the content in simple language.

If it contains a question,
solve it step by step.

If it contains notes or textbook content,
summarize the important points.

If it contains a diagram,
explain its components and working.

If it contains a mathematical problem,
show the calculation clearly.

If it is useful for an exam,
give exam-friendly points.

Do not guess text that is not readable.
"""
        )


    # -------------------------------------------------
    # VALIDATION
    # -------------------------------------------------

    if not parts:

        st.warning(
            "Please type a study question "
            "or upload a study image."
        )

        st.stop()


    # -------------------------------------------------
    # ASK GEMINI
    # -------------------------------------------------

    with st.spinner(
        "📚 Snap & Study is analyzing..."
    ):

        answer = ask_gemini(parts)


    # -------------------------------------------------
    # SAVE LAST ANSWER
    # -------------------------------------------------

    st.session_state.last_answer = answer


    # -------------------------------------------------
    # DISPLAY AI ANSWER
    # -------------------------------------------------

    add_message(

        "assistant",

        "text",

        answer

    )


# =====================================================
# WHATSAPP SUMMARY
# =====================================================

if st.session_state.get("last_answer"):

    st.markdown("---")


    st.subheader(
        "📲 Send Study Summary to WhatsApp"
    )


    st.caption(
        "Get a short revision-friendly summary "
        "of your current study conversation."
    )


    if st.button(
        "📲 Send to WhatsApp",
        use_container_width=True
    ):

        # -------------------------------------------------
        # GENERATE STUDY SUMMARY
        # -------------------------------------------------

        with st.spinner(
            "📝 Preparing your study summary..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )


        # -------------------------------------------------
        # SEND TO WHATSAPP
        # -------------------------------------------------

        with st.spinner(
            "📲 Sending to WhatsApp..."
        ):

            success, info = send_whatsapp(

                st.session_state.whatsapp_number,

                st.session_state.name,

                summary

            )


        # -------------------------------------------------
        # SIMPLE RESULT
        # -------------------------------------------------

        if success:

            st.success(
                "✅ Study summary sent to WhatsApp!"
            )

        else:

            st.error(
                f"❌ Couldn't send the study summary: {info}"
            )