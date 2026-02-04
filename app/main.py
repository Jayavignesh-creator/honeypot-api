from __future__ import annotations
from queue import Empty

from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.session_store import store
from app.pydantic_models import IncomingEvent, AgentResponse
from app.auth import api_key_auth
from app.config import MAX_REPLY_CHARS, MODEL_PATH
from app.first_scam_gate import FirstLayerScamDetector
from app.agentic_persona import run_agentic_turn
from app.tools.extract_tool import merge_unique
from app.tools.callback_tool import final_callback

import time
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.request import urlopen
import shutil

models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector
    print("Downloading scam detection model...")

    url = "https://huggingface.co/spaces/jacksonwambali/Bert/resolve/main/bert_scam_detector.pth"
    out_path = Path(MODEL_PATH)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with urlopen(url) as response, open(out_path, "wb") as out_file:
        shutil.copyfileobj(response, out_file)

    print("Loading scam detection model...")
    detector = FirstLayerScamDetector()

    scam_model = detector.load_model(MODEL_PATH)
    if not scam_model:
        raise RuntimeError("Failed to load scam detection model")

    models["scam_detector"] = detector
    print("Model loaded")
    yield

app = FastAPI(title="Agentic Honeypot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    print("Conversation History", event.conversationHistory)
    st.language = event.metadata.language

    # -----------------------------
    # Scam detection (stub for now)
    # -----------------------------
    if not event.conversationHistory:
        text_lower = event.message.text.lower()
        detector_response = models["scam_detector"].predict_message(text_lower)
        print("Scam Detection", detector_response["prediction"])
        if event.message.sender == "scammer" and detector_response["prediction"] == "scam":
            st.scam_detected = True

    # -----------------------------
    # Agent reply (agentic + tool calls)
    # -----------------------------

    # Ensure these exist (backward compatible)
    if not hasattr(st, "state") or not st.state:
        st.state = "START"
    if not hasattr(st, "summary") or st.summary is None:
        st.summary = ""
    if not hasattr(st, "extracted") or st.extracted is None:
        st.extracted = {"upiIds": [], "urls": [], "phones": [], "accounts": []}

    if st.scam_detected:
        # Build a small tail from conversationHistory + latest scammer msg
        # Your IncomingEvent.conversationHistory should have {sender, text, timestamp}
        effective = [
            {"sender": h.sender, "text": h.text, "timestamp": h.timestamp}
            for h in event.conversationHistory
            if h.sender == "scammer"
        ]
        effective.append({"sender": "scammer", "text": event.message.text, "timestamp": event.message.timestamp})
        st.conversationHistory = effective
        history_tail = effective  # hard cap for cost + speed

        # Simple state update heuristic (optional but useful)
        txt = event.message.text.lower()
        if st.state == "START":
            st.state = "CONFUSED"
        if "otp" in txt or "password" in txt or "verify" in txt:
            st.state = "TRUST_BUILDING"
        if "link" in txt or "install" in txt:
            st.state = "INFO_EXTRACTION"
        if st.extracted.upiIds or st.extracted.bankAccounts:
            st.state = "STALLING"

        # Run one agentic turn: model calls tools -> we execute -> get extracted intel + reply
        reply, new_bits, dbg = run_agentic_turn(
            latest_scammer_msg=event.message.text,
            session_id=st.session_id,
            history_tail=history_tail,
            session_state=st.state,
            language=st.language,
            extracted=st.extracted,
            background_tasks=background_tasks
        )

        # Merge extracted intel into session
        st.extracted = merge_unique(st.extracted, new_bits)

        st.agent_turns += 1
        st.agent_notes = dbg

        # Optional: keep summary minimal for now (we can improve later)
        if not st.summary:
            st.summary = "Scammer claims account issue and demands urgent action."
    else:
        reply = "Sorry, can you explain?"
        st.agent_turns += 1

    reply = reply[:MAX_REPLY_CHARS]

    if not st.scam_detected:
        final_callback(st.session_id, "Scam not detected", background_tasks=background_tasks)

    elif st.scam_detected and st.agent_turns > 10:
        final_callback(st.session_id, "Number of conversations exceeded set max limit", background_tasks=background_tasks)

    store.save(st)
    return AgentResponse(status="success", reply=reply)


@app.exception_handler(Exception)
async def global_exception_handler(_, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"status": "error", "reply": "Sorry, something went wrong."},
    )