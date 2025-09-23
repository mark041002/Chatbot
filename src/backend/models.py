"""
Zentrale Datenmodelle für den KI-Chatbot
Alle dataclasses an einem Ort für bessere Wartbarkeit
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import uuid


# ============ CHAT HISTORY MODELS ============

@dataclass
class ChatMessage:
    """Einzelne Chat-Nachricht"""
    role: str  # 'user' oder 'assistant'
    content: str
    timestamp: str
    sources: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)


@dataclass
class ChatSession:
    """Chat-Session Metadaten"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

    @classmethod
    def create_new(cls, title: str = None) -> 'ChatSession':
        """Factory method für neue Sessions"""
        timestamp = datetime.now().isoformat()
        return cls(
            session_id=str(uuid.uuid4()),
            title=title or f"Chat vom {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            created_at=timestamp,
            updated_at=timestamp
        )


# ============ API MODELS ============

@dataclass
class ChatRequest:
    """Request für Chat-Endpoint"""
    message: str
    session_id: Optional[str] = None


@dataclass
class ChatResponse:
    """Response vom Chat-Endpoint"""
    response: str
    sources: List[str]
    tools_used: List[str]
    success: bool
    mode: str
    session_id: Optional[str] = None


@dataclass
class DocumentListResponse:
    """Response für Dokumenten-Liste"""
    documents: List[str]
    count: int


@dataclass
class ModelResponse:
    """Response für verfügbare Modelle"""
    models: List[str]
    current_model: str
    ollama_available: bool


@dataclass
class ChatSessionResponse:
    """Response für Session-Liste"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


@dataclass
class ChatSessionDetailResponse:
    """Response für Session-Details"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[dict]


# ============ DOCUMENT PROCESSING MODELS ============

@dataclass
class ProcessedDocument:
    """Verarbeitetes Dokument"""
    dokument_name: str
    chunks: List[str]
    chunk_anzahl: int
    text_laenge: int
    ocr_used: bool = False
    processing_info: str = ""


@dataclass
class SearchResult:
    """Suchergebnis aus Vektordatenbank"""
    dokument: str
    text: str
    distance: float
    chunk_index: int
    relevanz: float = field(init=False)

    def __post_init__(self):
        """Relevanz aus Distance berechnen"""
        self.relevanz = 1.0 - self.distance


# ============ TOOL RESULTS ============

@dataclass
class ToolResult:
    """Generisches Tool-Ergebnis"""
    success: bool
    message: str
    data: dict = field(default_factory=dict)


@dataclass
class DocumentSearchResult(ToolResult):
    """Spezifisches Dokumenten-Suchergebnis"""
    ergebnisse: List[SearchResult] = field(default_factory=list)
    anzahl_gefunden: int = 0

    def __post_init__(self):
        if not self.anzahl_gefunden:
            self.anzahl_gefunden = len(self.ergebnisse)