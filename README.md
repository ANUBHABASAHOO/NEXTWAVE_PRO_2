# MacroSnap

MacroSnap is an AI nutrition buddy that helps users estimate calories and macronutrients from meal descriptions and meal photos. It uses Streamlit, the Google Gemini API, and Twilio WhatsApp messaging to create a simple, student-friendly nutrition assistant.

## Features

- Guided onboarding with name and WhatsApp number
- Text-based meal analysis with Gemini
- Photo-based meal analysis with Gemini vision
- Conversation memory during the current session
- Follow-up nutrition questions
- WhatsApp summary generation for meals discussed
- Twilio WhatsApp delivery through a Content Template
- Friendly, production-style Streamlit UI

## Tech Stack

- Python 3.9+
- Streamlit
- Google GenAI SDK (`google-genai`)
- Twilio Python SDK
- Streamlit secrets for configuration

## Project Structure

```text
macrosnap/
├── app.py
├── prompts.py
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    ├── secrets.toml.example
    └── secrets.toml
```

## Prerequisites

- Python 3.9+
- Gemini API key
- Twilio account
- Twilio WhatsApp Sandbox or approved WhatsApp sender

## Installation

```bash
cd macrosnap
python -m venv venv
```

Windows:

```powershell
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configure Secrets

Copy the example secrets file and update it with your own credentials:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

On Linux/macOS:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

The secrets file should contain:

```toml
GEMINI_API_KEY = "your-gemini-api-key-here"
TWILIO_ACCOUNT_SID = "your-twilio-account-sid-here"
TWILIO_AUTH_TOKEN = "your-twilio-auth-token-here"
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
TWILIO_CONTENT_SID = "your-content-template-sid-here"
```

### Secret explanations

- `GEMINI_API_KEY`: Your Google AI Studio API key for Gemini.
- `TWILIO_ACCOUNT_SID`: Your Twilio account SID.
- `TWILIO_AUTH_TOKEN`: Your Twilio auth token. Keep it secret.
- `TWILIO_WHATSAPP_FROM`: The approved WhatsApp sender number, usually `whatsapp:+14155238886` in the sandbox.
- `TWILIO_CONTENT_SID`: The content template SID configured for your approved WhatsApp message.

## Gemini Setup

1. Open Google AI Studio.
2. Create or select a project.
3. Generate an API key.
4. Store it in `.streamlit/secrets.toml` under `GEMINI_API_KEY`.

## Twilio WhatsApp Sandbox Setup

1. Create a Twilio account.
2. Open the WhatsApp Sandbox in the Twilio console.
3. Find the sandbox number and join it with your WhatsApp number.
4. Create a WhatsApp Content Template that uses variables such as:
   - `{{1}}` for the user name
   - `{{2}}` for the nutrition summary
5. Copy the content template SID into `TWILIO_CONTENT_SID`.
6. Confirm the sender is configured as `TWILIO_WHATSAPP_FROM`.

## Run

From the project directory:

```bash
streamlit run app.py
```

Expected local URL:

```text
http://localhost:8501
```

## How to Test

1. Enter a name and WhatsApp number on onboarding.
2. Ask a meal-related text question.
3. Upload a meal photo and ask for an estimate.
4. Ask a follow-up question about protein or carbs.
5. Click the WhatsApp summary button and verify the generated summary.

## Deployment

This app can be deployed on Streamlit Community Cloud. Before deployment, configure your secrets in the Streamlit app dashboard and never commit a local `.streamlit/secrets.toml` file to Git.

## Model Compatibility Note

The original reference guide showed an older Gemini model name. This project uses the current Google GenAI SDK and selects `gemini-2.0-flash`, which is a supported Gemini Flash model and keeps the app compatible with the current SDK.

## Important

- Never commit `secrets.toml`.
- Never hardcode API keys or Twilio credentials.
- Use Streamlit secrets for all environment configuration.
