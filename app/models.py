from __future__ import annotations

from typing import Literal, List, Optional, Any
from pydantic import BaseModel, Field

Sender = Literal["scammer", "user"]
Channel = Literal["SMS", "WhatsApp", "Email", "Chat"]

class Message(BaseModel):
    sender: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=4000)
    timestamp: Optional[Any] = None

class Metadata(BaseModel):
    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None

class IncomingEvent(BaseModel):
    sessionId: str = Field(min_length=3, max_length=200)
    message: Message
    conversationHistory: Optional[List[Message]] = None
    metadata: Optional[Metadata] = None

class AgentResponse(BaseModel):
    status: str = "success"
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
