# Honeypot API

Agentic FastAPI service that simulates a victim in scam conversations, extracts scam intelligence (UPI IDs, bank accounts, phone numbers, links), and sends a final callback summary when the session ends.

## What This Project Does

- Accepts scammer messages over `/v1/message`.
- Maintains per-session state in memory.
- Uses an LLM persona to keep scammers engaged and collect intelligence.
- Runs regex-based extraction for key scam artifacts.
- Optionally runs a first-layer scam classifier for new conversations.
- Sends a best-effort final callback payload with extracted intelligence and scammer behavior notes.

## Repository Structure

- `app/main.py`: FastAPI app, startup model load, request handling, callback trigger logic.
- `app/honeypot_agent.py`: LLM orchestration and tool-call handling.
- `app/first_scam_gate.py`: BERT-based scam detector.
- `app/tools/extract_tool.py`: Entity extraction + merge logic.
- `app/tools/callback_tool.py`: Final callback payload assembly.
- `app/session_store.py`: In-memory session store with TTL cleanup.
- `app/pydantic_models.py`: Request/response and callback models.
- `test_api.py`: Manual/interactive API test script.
- `aca-streamlit-admin/app.py`: Streamlit admin app to update `SYSTEM_PROMPT` and `SCAM_GATE` in Azure Container Apps.

## Prerequisites

- Python `3.11`
- OpenAI API key
- (Optional) Docker + Docker Compose
- (Optional) Azure Managed Identity (for Streamlit admin app)

## Environment Variables

Create a `.env` file in the repo root.

Required for API:

- `API_KEY`: header auth value expected as `x-api-key`.
- `OPENAI_API_KEY`: OpenAI credential.

Common runtime variables:

- `GUVI_CALLBACK_URL`: URL to receive final callback payload.
- `SESSION_TTL_SECONDS`: session expiry window (default `1800`).
- `MAX_REPLY_CHARS`: max response length (default `280`).
- `MODEL_PATH`: local path for downloaded classifier model (default `./models/bert_scam_detector.pth`).
- `SCAM_GATE`: `true`/`false` to enable first-turn scam gating.
- `OPENAI_MODEL`: model for agentic turns (default `gpt-5-mini`; compose sets `gpt-5.2`).
- `LLM_MAX_OUTPUT_TOKENS`: output token cap per model call.
- `SYSTEM_PROMPT`: appended instruction block for agent persona behavior.

Variables used only by admin app (`aca-streamlit-admin/app.py`):

- `TARGET_SUBSCRIPTION_ID`
- `TARGET_RESOURCE_GROUP`
- `TARGET_CONTAINERAPP_NAME`
- `TARGET_CONTAINER_NAME` (optional)

## Local Development

1. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start API server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Docker Run

Build and run with Compose:

```bash
docker compose up --build
```

API will be available at `http://localhost:8000`.

## API Contract

### `POST /v1/message`

Headers:

- `x-api-key: <API_KEY>`
- `Content-Type: application/json`

Request body:

```json
{
  "sessionId": "session-123",
  "message": {
    "sender": "scammer",
    "text": "Your account is blocked. Share OTP now.",
    "timestamp": "2026-02-16T08:00:00Z"
  },
  "conversationHistory": [
    {
      "sender": "scammer",
      "text": "Previous message",
      "timestamp": "2026-02-16T07:59:00Z"
    }
  ],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

Response:

```json
{
  "status": "success",
  "reply": "Victim-like response text"
}
```

## Final Callback Payload

When stop conditions are met, the service schedules an async callback to `GUVI_CALLBACK_URL`.

Payload shape:

```json
{
  "sessionId": "session-123",
  "scamDetected": true,
  "totalMessagesExchanged": 8,
  "extractedIntelligence": {
    "bankAccounts": ["123456789012"],
    "upiIds": ["fraud@bank"],
    "phishingLinks": ["https://bad-link.example"],
    "phoneNumbers": ["+91-9876543210"],
    "suspiciousKeywords": ["KYC", "urgent", "verification"]
  },
  "agentNotes": "One-line scammer behavior summary"
}
```

## Testing

Run the included script:

```bash
python test_api.py
```

Notes:

- The script is interactive after turn 1 and asks for follow-up scammer messages.
- Update `ENDPOINT_URL` and `API_KEY` inside `test_api.py` if you are testing local or another deployment.

## Admin App (Streamlit)

The `aca-streamlit-admin` app updates Azure Container App environment values for:

- `SYSTEM_PROMPT`
- `SCAM_GATE`

Run locally:

```bash
cd aca-streamlit-admin
pip install -r requirements.txt
streamlit run app.py
```

Default port is `8501`.

## Implementation Notes

- Session store is in-memory only; restarting the server clears sessions.
- Classifier model is downloaded on app startup from Hugging Face.
- Request logging middleware prints incoming payload metadata/body snippets and response timings.
- CORS is currently open (`*`) for origins, methods, and headers.

## License

No license file is currently defined in this repository.
