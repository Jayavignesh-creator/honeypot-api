from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict

from app.config import SESSION_TTL_SECONDS
from app.pydantic_models import ExtractedIntelligence


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    scam_detected: bool = False
    status: str = "active"
    final_callback_sent: bool = False
    persona_id: str = "busy-user-v1"

    agent_turns: int = 0
    total_messages_exchanged: int = 0

    extracted: ExtractedIntelligence = field(default_factory=ExtractedIntelligence)
    agent_notes: str = ""

    state: str = "START"
    summary: str = ""

class InMemorySessionStore:
    """
    Minimal in-memory session store with TTL cleanup.
    Good enough for hackathon MVP.
    """

    def __init__(self):
        self._store: Dict[str, SessionState] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired_ids = []
        for sid, st in self._store.items():
            if (now - st.updated_at) > SESSION_TTL_SECONDS:
                expired_ids.append(sid)

        for sid in expired_ids:
            del self._store[sid]

    def get_or_create(self, session_id: str) -> SessionState:
        self._cleanup()
        st = self._store.get(session_id)
        if st is None:
            st = SessionState(session_id=session_id)
            self._store[session_id] = st
        return st

    def save(self, st: SessionState) -> None:
        st.updated_at = time.time()
        self._store[st.session_id] = st
