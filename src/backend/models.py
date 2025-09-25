from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class ChatRequest(BaseModel):
    """Chat-Anfrage mit optionaler Session-ID und Temperature"""
    message: str = Field(..., description="Die Chat-Nachricht des Benutzers")
    session_id: Optional[str] = Field(None, description="Optionale Session-ID für bestehende Gespräche")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=1.0, description="Temperature für KI-Generierung (0.0-1.0)")

class ChatResponse(BaseModel):
    """Chat-Antwort mit Metadaten"""
    response: str = Field(..., description="Die generierte Antwort")
    success: bool = Field(..., description="Erfolgsstatus der Anfrage")
    session_id: str = Field(..., description="Session-ID für das Gespräch")

class DocumentListResponse(BaseModel):
    """Response für Dokumentenliste"""
    documents: List[str] = Field(..., description="Liste aller verfügbaren Dokumente")
    count: int = Field(..., description="Anzahl der Dokumente")

class ModelResponse(BaseModel):
    """Response für verfügbare Modelle"""
    models: List[str] = Field(..., description="Liste aller verfügbaren Modelle")
    current_model: str = Field(..., description="Aktuell verwendetes Modell")
    ollama_available: bool = Field(..., description="Ollama-Verfügbarkeitsstatus")

class ChatSession(BaseModel):
    """Chat-Session Model"""
    session_id: str = Field(..., description="Eindeutige Session-ID")
    title: str = Field(..., description="Session-Titel")
    created_at: str = Field(..., description="Erstellungszeitpunkt")
    updated_at: str = Field(..., description="Letztes Update")

    @classmethod
    def create_new(cls, title: str = None) -> 'ChatSession':
        """Erstellt eine neue Chat-Session"""
        now = datetime.now().isoformat()
        return cls(
            session_id=str(uuid.uuid4()),
            title=title or "Neuer Chat",
            created_at=now,
            updated_at=now
        )

class ChatSessionResponse(BaseModel):
    """Response für Chat-Session-Liste"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int

class ChatMessage(BaseModel):
    """Chat-Message Model"""
    role: str
    content: str
    timestamp: str

class ChatSessionDetailResponse(BaseModel):
    """Detaillierte Chat-Session Response"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessage]