from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import redis

from app.config import SESSION_TTL_SECONDS, REDIS_HOST, REDIS_PORT
from app.pydantic_models import ExtractedIntelligence


@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    scam_detected: bool = True
    status: str = "active"
    final_callback_sent: bool = False
    persona_id: str = "busy-user-v1"

    agent_turns: int = 0
    total_messages_exchanged: int = 0
    conversationHistory: list[dict] = field(default_factory=list)
    extracted: ExtractedIntelligence = field(default_factory=ExtractedIntelligence)
    agent_notes: str = ""

    state: str = "START"
    summary: str = ""
    language: str = "English"


def _dump_extracted(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Cannot dump extracted of type {type(obj)}")


def _load_extracted(x):
    if isinstance(x, ExtractedIntelligence):
        return x
    if isinstance(x, dict):
        if hasattr(ExtractedIntelligence, "model_validate"):
            return ExtractedIntelligence.model_validate(x)
        return ExtractedIntelligence.parse_obj(x)
    if x is None:
        return ExtractedIntelligence()
    raise TypeError(f"extracted must be dict/ExtractedIntelligence, got {type(x)}")


class RedisSessionStore:
    def __init__(self, prefix: str = "session:"):
        self.prefix = prefix
        self._r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        try:
            self._r.ping()
        except Exception as e:
            raise RuntimeError(f"Redis not reachable at {REDIS_HOST}:{REDIS_PORT}") from e

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    def _serialize(self, st: SessionState) -> str:
        history = []
        for m in st.conversationHistory:
            if isinstance(m, dict):
                history.append(m)
            else:
                if hasattr(m, "model_dump"):
                    history.append(m.model_dump())
                elif hasattr(m, "dict"):
                    history.append(m.dict())
                else:
                    raise TypeError(f"conversationHistory must contain dicts, got {type(m)}")

        data = {
            "session_id": st.session_id,
            "created_at": st.created_at,
            "updated_at": st.updated_at,
            "scam_detected": st.scam_detected,
            "status": st.status,
            "final_callback_sent": st.final_callback_sent,
            "persona_id": st.persona_id,
            "agent_turns": st.agent_turns,
            "total_messages_exchanged": st.total_messages_exchanged,
            "conversationHistory": history,
            "extracted": _dump_extracted(st.extracted),
            "agent_notes": st.agent_notes,
            "state": st.state,
            "summary": st.summary,
            "language": st.language,
        }
        return json.dumps(data, ensure_ascii=False)

    def _deserialize(self, raw: str) -> SessionState:
        d = json.loads(raw)

        hist = d.get("conversationHistory", [])
        if not isinstance(hist, list):
            hist = []
        d["conversationHistory"] = [x for x in hist if isinstance(x, dict)]

        d["extracted"] = _load_extracted(d.get("extracted", {}))

        return SessionState(**d)

    def get_or_create(self, session_id: str) -> SessionState:
        key = self._key(session_id)
        raw = self._r.get(key)
        if raw:
            return self._deserialize(raw)

        st = SessionState(session_id=session_id)
        self.save(st)
        return st

    def save(self, st: SessionState) -> None:
        st.updated_at = time.time()
        key = self._key(st.session_id)
        self._r.setex(key, SESSION_TTL_SECONDS, self._serialize(st))


store = RedisSessionStore()