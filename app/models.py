from __future__ import annotations

from typing import Literal, List, Optional
from pydantic import BaseModel, Field

Sender = Literal["scammer", "user"]

class Message(BaseModel):
    sender: Sender
    text: str = Field(min_length=1, max_length=4000)
    timestamp: str

class Metadata(BaseModel):
    language: Optional[str] = None
    locale: Optional[str] = None

class IncomingEvent(BaseModel):
    sessionId: str = Field(min_length=3, max_length=200)
    message: Message
    conversationHistory: List[Message] = Field(default_factory=list)
    metadata: Optional[Metadata] = None

class AgentResponse(BaseModel):
    status: Literal["success", "error"] = "success"
    reply: str

class ExtractedIntelligence(BaseModel):
    bankAccounts: List[str] = Field(default_factory=list)
    upiIds: List[str] = Field(default_factory=list)
    phishingLinks: List[str] = Field(default_factory=list)
    phoneNumbers: List[str] = Field(default_factory=list)
    suspiciousKeywords: List[str] = Field(default_factory=list)

class FinalCallbackPayload(BaseModel):
    sessionId: str
    scamDetected: bool
    totalMessagesExchanged: int
    extractedIntelligence: ExtractedIntelligence
    agentNotes: str
