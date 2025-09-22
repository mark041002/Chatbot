from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import tempfile
from typing import List, Optional
import uvicorn

from document_processor import DokumentProcessor
from vektor_store import VektorStore
from chat_handler import ChatHandlerADK
from chat_history import ChatHistoryManager  # NEU


# Pydantic Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # NEU: Optional Session-ID


class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    tools_used: List[str]
    success: bool
    mode: str
    session_id: Optional[str] = None  # NEU: Session-ID zurückgeben


class DocumentListResponse(BaseModel):
    documents: List[str]
    count: int


class ModelResponse(BaseModel):
    models: List[str]
    current_model: str
    ollama_available: bool


# NEU: Chat History Models
class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ChatSessionDetailResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[dict]


# FastAPI App erstellen
app = FastAPI(
    title="Lokaler KI-Chatbot API",
    description="API für den lokalen KI-Chatbot mit Dokumentensuche und Chat-Verlauf",
    version="2.0.0"
)

# CORS aktivieren
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Komponenten initialisieren
def initialize_components():
    """Initialisiert alle benötigten Komponenten"""
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("data/vektor_db", exist_ok=True)
    os.makedirs("data/chat_history", exist_ok=True)  # NEU
    os.makedirs("static", exist_ok=True)

    processor = DokumentProcessor()
    vektor_store = VektorStore()
    chat_handler = ChatHandlerADK(vektor_store)
    chat_history = ChatHistoryManager()  # NEU

    return processor, vektor_store, chat_handler, chat_history


# Globale Komponenten
processor, vektor_store, chat_handler, chat_history = initialize_components()


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat-Endpoint für Nachrichten - jetzt mit Session-Management"""
    try:
        if not chat_handler.ollama_verfuegbar():
            raise HTTPException(status_code=503, detail="Ollama ist nicht verfügbar")

        # Session-ID verwalten
        session_id = request.session_id
        if not session_id:
            session_id = chat_history.create_session()

        # Benutzer-Nachricht zur Session hinzufügen
        chat_history.add_message(session_id, "user", request.message)

        # Antwort generieren
        result = chat_handler.antwort_generieren(request.message)

        # Antwort zur Session hinzufügen
        chat_history.add_message(
            session_id,
            "assistant",
            result["antwort"],
            sources=result["quellen"],
            tools_used=result["verwendete_tools"]
        )

        return ChatResponse(
            response=result["antwort"],
            sources=result["quellen"],
            tools_used=result["verwendete_tools"],
            success=result["success"],
            mode=result.get("modus", "unknown"),
            session_id=session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat-Fehler: {str(e)}")


# NEU: Chat History Endpunkte
@app.get("/api/chat/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions():
    """Gibt die letzten 5 Chat-Sessions zurück"""
    try:
        sessions = chat_history.get_recent_sessions(limit=5)
        return [ChatSessionResponse(**session) for session in sessions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Sessions: {str(e)}")


@app.get("/api/chat/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(session_id: str):
    """Lädt eine spezifische Chat-Session mit allen Nachrichten"""
    try:
        session = chat_history.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session nicht gefunden")

        # Session zu Dict konvertieren
        messages = []
        for msg in session.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "sources": msg.sources or [],
                "tools_used": msg.tools_used or []
            })

        return ChatSessionDetailResponse(
            session_id=session.session_id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=messages
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Session: {str(e)}")


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Löscht eine Chat-Session"""
    try:
        success = chat_history.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session nicht gefunden")

        return {"message": f"Session '{session_id}' erfolgreich gelöscht"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")


@app.post("/api/chat/sessions")
async def create_chat_session(title: Optional[str] = None):
    """Erstellt eine neue Chat-Session"""
    try:
        session_id = chat_history.create_session(title)
        return {"session_id": session_id, "message": "Session erfolgreich erstellt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Erstellen der Session: {str(e)}")


@app.get("/api/documents", response_model=DocumentListResponse)
async def get_documents():
    """Listet verfügbare Dokumente auf"""
    try:
        documents = vektor_store.verfuegbare_dokumente_auflisten()
        return DocumentListResponse(
            documents=documents,
            count=len(documents)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Dokumente: {str(e)}")


@app.delete("/api/documents/{document_name}")
async def delete_document(document_name: str):
    """Löscht ein Dokument"""
    try:
        documents = vektor_store.verfuegbare_dokumente_auflisten()
        if document_name not in documents:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

        vektor_store.dokument_entfernen(document_name)
        return {"message": f"Dokument '{document_name}' erfolgreich gelöscht"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Lädt ein Dokument hoch und verarbeitet es - jetzt mit OCR-Unterstützung"""
    try:
        # Dateiformat prüfen
        allowed_extensions = ['.pdf', '.txt', '.docx']
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Nicht unterstütztes Dateiformat. Erlaubt: {', '.join(allowed_extensions)}"
            )

        # Temporäre Datei erstellen
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Dokument verarbeiten
            processed_data = processor.dokument_verarbeiten(temp_file_path, file.filename)

            # Zu Vektordatenbank hinzufügen
            vektor_store.dokument_hinzufuegen(
                processed_data['dokument_name'],
                processed_data['chunks']
            )

            return {
                "message": f"Dokument '{file.filename}' erfolgreich verarbeitet",
                "document_name": processed_data['dokument_name'],
                "chunks_created": processed_data['chunk_anzahl'],
                "text_length": processed_data['text_laenge'],
                "ocr_used": processed_data.get('ocr_used', False),  # NEU
                "processing_info": processed_data.get('processing_info', '')  # NEU
            }

        finally:
            # Temporäre Datei löschen
            os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler bei der Verarbeitung: {str(e)}")


@app.get("/api/models", response_model=ModelResponse)
async def get_models():
    """Gibt verfügbare Modelle zurück"""
    try:
        ollama_available = chat_handler.ollama_verfuegbar()
        models = chat_handler.verfuegbare_modelle_auflisten() if ollama_available else []
        current_model = chat_handler.model if ollama_available else ""

        return ModelResponse(
            models=models,
            current_model=current_model,
            ollama_available=ollama_available
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Laden der Modelle: {str(e)}")


@app.post("/api/models/{model_name}")
async def switch_model(model_name: str):
    """Wechselt das verwendete Modell"""
    try:
        if not chat_handler.ollama_verfuegbar():
            raise HTTPException(status_code=503, detail="Ollama ist nicht verfügbar")

        available_models = chat_handler.verfuegbare_modelle_auflisten()
        if model_name not in available_models:
            raise HTTPException(status_code=404, detail="Modell nicht gefunden")

        # Modell testen
        if not chat_handler.model_testen(model_name):
            raise HTTPException(status_code=400, detail="Modell funktioniert nicht korrekt")

        # Modell wechseln
        chat_handler.model_wechseln(model_name)

        return {
            "message": f"Modell erfolgreich zu '{model_name}' gewechselt",
            "current_model": model_name
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Wechseln des Modells: {str(e)}")


@app.get("/api/health")
async def health_check():
    """Gesundheitscheck für die API und Ollama"""
    ollama_status = chat_handler.ollama_verfuegbar()
    document_count = len(vektor_store.verfuegbare_dokumente_auflisten())

    return {
        "api_status": "healthy",
        "ollama_available": ollama_status,
        "document_count": document_count,
        "current_model": chat_handler.model if ollama_status else None,
        "features": {
            "chat_history": True,
            "ocr_support": processor.ocr_enabled  # NEU
        }
    }


if __name__ == "__main__":
    print("Starte Lokaler KI-Chatbot API Server...")
    print(f"OCR-Unterstützung: {'✅ Verfügbar' if processor.ocr_enabled else 'Nicht verfügbar'}")
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )