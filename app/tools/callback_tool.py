from app.session_store import InMemorySessionStore
from app.tools.summarize import summarize_behaviour, extract_suspicious_keywords
from app.callback import send_final_callback
from app.pydantic_models import FinalCallbackPayload

store = InMemorySessionStore()

def final_callback(session_id: str, reason: str):
    st = store.get_or_create(session_id)
    total_messages = len(st.conversationHistory) + 1  # best-effort

    suspicious_keywords = extract_suspicious_keywords(st.conversationHistory)
    st.extracted.suspiciousKeywords = suspicious_keywords
    scammer_behaviour = summarize_behaviour(st.conversationHistory) + "\n\n" + reason

    print("Extracted keywords", suspicious_keywords)
    print("Scammer Behaviour", scammer_behaviour)

    payload = FinalCallbackPayload(
        sessionId=session_id,
        scamDetected=st.scam_detected,
        totalMessagesExchanged=total_messages,
        extractedIntelligence=st.extracted,
        agentNotes=scammer_behaviour
    )

    send_final_callback(payload)

    st.final_callback_sent = True
    st.status = "closed"