from __future__ import annotations

from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from .models import IncomingEvent, AgentResponse, FinalCallbackPayload
from .session_store import InMemorySessionStore
from .callback import send_final_callback
from .auth import api_key_auth
from .config import MAX_REPLY_CHARS
import time
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="Agentic Honeypot API", version="1.0.0")
store = InMemorySessionStore()

class LogAll(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        body = await request.body()
        print("==== INCOMING REQUEST ====")
        print("METHOD:", request.method)
        print("PATH:", request.url.path)
        print("QUERY:", request.url.query)
        print("HEADERS:", dict(request.headers))
        print("BODY_LEN:", len(body))
        # show only first 2000 bytes to avoid huge spam
        print("BODY_SNIP:", body[:2000])
        print("==========================")

        resp = await call_next(request)
        ms = int((time.time() - start) * 1000)
        print("==== RESPONSE ====")
        print("STATUS:", resp.status_code, "TIME_MS:", ms)
        print("==================")
        return resp

app.add_middleware(LogAll)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/v1/message", response_model=AgentResponse)
async def handle_message(
    event: IncomingEvent,
    background_tasks: BackgroundTasks,
    _: None = Depends(api_key_auth),
):
    print("Incoming Event", event)
    st = store.get_or_create(event.sessionId)

    # If session already closed, reply minimally
    if st.status == "closed":
        return AgentResponse(status="success", reply="Okay, thanks.")

    # -----------------------------
    # Scam detection (stub for now)
    # -----------------------------
    text_lower = event.message.text.lower()
    obvious = any(k in text_lower for k in ["upi", "verify", "account blocked", "otp", "suspend", "link"])
    if event.message.sender == "scammer" and obvious:
        st.scam_detected = True

    # -----------------------------
    # Agent reply (placeholder)
    # -----------------------------
    if st.scam_detected:
        reply = "Wait—why is it getting blocked? What exactly do I need to do?"
        st.agent_turns += 1
        st.agent_notes = "Used a cautious, confused tone to keep scammer engaged."
    else:
        reply = "Sorry, can you explain?"
        st.agent_turns += 1

    reply = reply[:MAX_REPLY_CHARS]

    # -----------------------------
    # Stop condition + callback (basic skeleton)
    # -----------------------------
    if st.scam_detected and (not st.final_callback_sent) and st.agent_turns >= 3:
        total_messages = len(event.conversationHistory) + 1 + st.agent_turns  # best-effort

        payload = FinalCallbackPayload(
            sessionId=event.sessionId,
            scamDetected=True,
            totalMessagesExchanged=total_messages,
            extractedIntelligence=st.extracted,  # empty for now; we’ll fill later
            agentNotes=st.agent_notes or "Engaged scammer to elicit details."
        )

        background_tasks.add_task(send_final_callback, payload)

        st.final_callback_sent = True
        st.status = "closed"

    store.save(st)
    return AgentResponse(status="success", reply=reply)


@app.exception_handler(Exception)
async def global_exception_handler(_, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "reply": "Sorry, something went wrong."},
    )