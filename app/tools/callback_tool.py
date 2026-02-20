from fastapi import BackgroundTasks
from app.session_store import store
from app.tools.summarize import summarize_behaviour, extract_suspicious_keywords
from app.callback import send_final_callback
from app.pydantic_models import FinalCallbackPayload
import json
import time

def final_callback(session_id: str, reason: str, background_tasks: BackgroundTasks):
    st = store.get_or_create(session_id)
    total_messages = len(st.conversationHistory) + 1  # best-effort

    print("Conversation history from callback tool", st.conversationHistory)
    session_created_time = st.created_at
    engagement_duration = int(time.time() - session_created_time)

    print("Total engagement time : ",engagement_duration)

    suspicious_keywords = extract_suspicious_keywords(json.dumps(st.conversationHistory))
    st.extracted.suspiciousKeywords = suspicious_keywords
    scammer_behaviour = summarize_behaviour(json.dumps(st.conversationHistory)) + "\n\n" + reason

    print("Extracted keywords", suspicious_keywords)
    print("Scammer Behaviour", scammer_behaviour)

    payload = FinalCallbackPayload(
        sessionId=session_id,
        scamDetected=st.scam_detected,
        totalMessagesExchanged=total_messages,
        engagementDurationSeconds=engagement_duration,
        extractedIntelligence=st.extracted,
        agentNotes=scammer_behaviour
    )

    background_tasks.add_task(send_final_callback, payload)

    st.final_callback_sent = True
    st.status = "closed"