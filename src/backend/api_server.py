from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
from typing import List, Optional
import uvicorn

from document_processor import DokumentProcessor
from vektor_store import VektorStore
from chat_handler import ChatHandlerADK
from chat_history import ChatHistoryManager

from models import (
    ChatRequest, ChatResponse, DocumentListResponse,
    ModelResponse, ChatSessionResponse, ChatSessionDetailResponse
)

app = FastAPI(
    title="Lokaler KI-Chatbot API",
    description="API für den lokalen KI-Chatbot mit Dokumentensuche, Chat-Verlauf und OCR-Unterstützung",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def initialize_components():
    """
    Initialisiert alle Systemkomponenten und erstellt notwendige Verzeichnisse.
    Returns:
        tuple: (processor, vektor_store, chat_handler, chat_history) - Alle initialisierten Komponenten
    """
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("data/vektor_db", exist_ok=True)

    processor = DokumentProcessor()
    vektor_store = VektorStore()
    chat_handler = ChatHandlerADK(vektor_store)
    chat_history = ChatHistoryManager()

    # Automatische Modellinitialisierung
    if chat_handler.ollama_verfuegbar():
        verfuegbare_modelle = chat_handler.verfuegbare_modelle_auflisten()
        if verfuegbare_modelle:
            # Nimm das erste verfügbare Modell
            erstes_model = verfuegbare_modelle[0]
            chat_handler.model_wechseln(erstes_model)
        else:
            print("WARNUNG: Ollama ist verfügbar, aber keine Modelle gefunden!")
            print("Bitte laden Sie ein Modell herunter mit: ollama pull llama3")
    else:
        print("WARNUNG: Ollama ist nicht verfügbar!")

    return processor, vektor_store, chat_handler, chat_history


processor, vektor_store, chat_handler, chat_history = initialize_components()


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Add validation checks
        if not chat_handler:
            raise HTTPException(status_code=503, detail="Chat handler not initialized")

        if not chat_history:
            raise HTTPException(status_code=503, detail="Chat history not initialized")

        # Prüfe ob Ollama verfügbar ist und Modelle vorhanden sind
        if not chat_handler.ollama_verfuegbar():
            raise HTTPException(
                status_code=503,
                detail="Ollama ist nicht verfügbar. Bitte starten Sie Ollama zuerst."
            )

        verfuegbare_modelle = chat_handler.verfuegbare_modelle_auflisten()
        if not verfuegbare_modelle:
            raise HTTPException(
                status_code=503,
                detail="Keine Modelle verfügbar. Bitte laden Sie ein Modell herunter mit: ollama pull llama3"
            )

        # Stelle sicher, dass ein Modell gesetzt ist
        if not chat_handler.model_name or chat_handler.model_name not in verfuegbare_modelle:
            erstes_model = verfuegbare_modelle[0]
            chat_handler.model_wechseln(erstes_model)
            print(f"Automatisch zu Modell '{erstes_model}' gewechselt")

        session_id = request.session_id

        # Session only creation when no session exists and message is sent
        if not session_id:
            session_id = chat_history.create_session()

        # Load session history for context
        session_data = None
        session_history = []
        if chat_history:
            session_data = chat_history.get_session(session_id)
            if session_data:
                session_history = session_data.get("messages", [])

        # Add message to session
        chat_history.add_message(session_id, "user", request.message)


        result = chat_handler.antwort_generieren(
            request.message,
            session_history,
            temperature=request.temperature,
        )

        # Add assistant response to session
        chat_history.add_message(
            session_id,
            "assistant",
            result["antwort"],
            sources=result.get("quellen", []),
            tools_used=result.get("verwendete_tools", [])
        )

        return ChatResponse(
            response=result["antwort"],
            sources=result.get("quellen", []),
            tools_used=result.get("verwendete_tools", []),
            success=result.get("success", True),
            mode=result.get("modus", "unknown"),
            session_id=session_id
        )

    except HTTPException:
        raise
    except Exception as e:
        # Add proper error logging
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/chat/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions():
    """
    Gibt die letzten Chat-Sessions zurück.
    Returns:
        List[ChatSessionResponse]: Liste der letzten 5 Chat-Sessions
    """
    if not chat_history:
        return []
    sessions = chat_history.get_recent_sessions(limit=5)
    return [ChatSessionResponse(**session) for session in sessions]


@app.get("/api/chat/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(session_id: str):
    """
    Lädt eine spezifische Chat-Session mit allen Nachrichten.
    Args:
        session_id (str): Eindeutige Session-ID
    Returns:
        ChatSessionDetailResponse: Vollständige Session-Daten mit Nachrichtenverlauf
    """

    session = chat_history.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    return ChatSessionDetailResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        messages=session["messages"]
    )


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """
    Löscht eine Chat-Session permanent.
    Args:
        session_id (str): ID der zu löschenden Session
    Returns:
        dict: Bestätigungsnachricht
    """
    success = chat_history.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    return {"message": f"Session '{session_id}' erfolgreich gelöscht"}


@app.get("/api/documents", response_model=DocumentListResponse)
async def get_documents():
    """
    Listet alle verfügbaren Dokumente in der Vektordatenbank auf.
    Returns:
        DocumentListResponse: Liste aller Dokumente mit Anzahl
    """
    if not vektor_store:
        return DocumentListResponse(documents=[], count=0)

    documents = vektor_store.verfuegbare_dokumente_auflisten()
    return DocumentListResponse(documents=documents, count=len(documents))


@app.delete("/api/documents/{document_name}")
async def delete_document(document_name: str):
    """
    Löscht ein Dokument aus der Vektordatenbank und dem Upload-Ordner.
    Args:
        document_name (str): Name des zu löschenden Dokuments
    Returns:
        dict: Bestätigungsnachricht
    """
    documents = vektor_store.verfuegbare_dokumente_auflisten()
    if document_name not in documents:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden")

    vektor_store.dokument_entfernen(document_name)

    upload_dir = "data/uploads"
    extensions = ['.pdf', '.docx', '.txt']

    for ext in extensions:
        file_path = os.path.join(upload_dir, f"{document_name}{ext}")
        if os.path.exists(file_path):
            os.remove(file_path)

    return {"message": f"Dokument '{document_name}' erfolgreich gelöscht"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Lädt ein Dokument hoch, verarbeitet es und fügt es zur Vektordatenbank hinzu.
    Args:
        file (UploadFile): Hochgeladene Datei (PDF, DOCX oder TXT)
    Returns:
        dict: Detaillierte Informationen über die verarbeitete Datei
    """
    if not processor or not vektor_store:
        raise HTTPException(status_code=503, detail="Document Processor oder Vektor Store nicht verfügbar")

    allowed_extensions = ['.pdf', '.txt', '.docx']
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Nicht unterstütztes Dateiformat. Erlaubt: {', '.join(allowed_extensions)}"
        )

    content = await file.read()

    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in '._-').rstrip()
    if not safe_filename:
        safe_filename = f"document{file_extension}"

    upload_path = os.path.join("data/uploads", safe_filename)
    counter = 1
    original_name = safe_filename
    while os.path.exists(upload_path):
        name_without_ext = os.path.splitext(original_name)[0]
        upload_path = os.path.join("data/uploads", f"{name_without_ext}_{counter}{file_extension}")
        safe_filename = f"{name_without_ext}_{counter}{file_extension}"
        counter += 1

    with open(upload_path, 'wb') as f:
        f.write(content)

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
        temp_file.write(content)
        temp_file_path = temp_file.name

    try:
        processed_data = processor.dokument_verarbeiten(temp_file_path, file.filename)

        vektor_store.dokument_hinzufuegen(
            processed_data['dokument_name'],
            processed_data['chunks']
        )

        response_message = f"Dokument '{file.filename}' erfolgreich verarbeitet und gespeichert"
        if processed_data.get('ocr_used'):
            response_message += " (OCR verwendet)"

        return {
            "message": response_message,
            "document_name": processed_data['dokument_name'],
            "stored_filename": safe_filename,
            "stored_path": upload_path,
            "chunks_created": processed_data['chunk_anzahl'],
            "text_length": processed_data['text_laenge'],
            "ocr_used": processed_data.get('ocr_used', False),
            "processing_info": processed_data.get('processing_info', 'Standard-Textextraktion')
        }

    finally:
        os.unlink(temp_file_path)


@app.get("/api/models", response_model=ModelResponse)
async def get_models():
    """
    Gibt alle verfügbaren Ollama-Modelle zurück.
    Returns:
        ModelResponse: Liste aller Modelle mit aktuellem Modell und Verfügbarkeitsstatus
    """
    if not chat_handler:
        return ModelResponse(models=[], current_model="", ollama_available=False)

    ollama_available = chat_handler.ollama_verfuegbar()
    models = chat_handler.verfuegbare_modelle_auflisten() if ollama_available else []
    current_model = chat_handler.model_name if ollama_available else ""

    # Automatisch erstes Modell setzen falls keins gesetzt ist
    if ollama_available and models and (not current_model or current_model not in models):
        erstes_model = models[0]
        chat_handler.model_wechseln(erstes_model)
        current_model = erstes_model
        print(f"Automatisch Modell '{erstes_model}' gesetzt")

    return ModelResponse(
        models=models,
        current_model=current_model,
        ollama_available=ollama_available
    )


@app.post("/api/models/{model_name}")
async def switch_model(model_name: str):
    """
    Wechselt das verwendete LLM-Modell nach Validierung.
    Args:
        model_name (str): Name des neuen Modells
    Returns:
        dict: Bestätigung des Modellwechsels
    """
    if not chat_handler.ollama_verfuegbar():
        raise HTTPException(status_code=503, detail="Ollama ist nicht verfügbar")

    available_models = chat_handler.verfuegbare_modelle_auflisten()
    if not available_models:
        raise HTTPException(
            status_code=503,
            detail="Keine Modelle verfügbar. Bitte laden Sie ein Modell herunter mit: ollama pull llama3"
        )

    if model_name not in available_models:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")

    if not chat_handler.model_testen(model_name):
        raise HTTPException(status_code=400, detail="Modell funktioniert nicht korrekt")

    chat_handler.model_wechseln(model_name)

    return {
        "message": f"Modell erfolgreich zu '{model_name}' gewechselt",
        "current_model": model_name
    }


@app.get("/api/health")
async def health_check():
    """
    Umfassender Gesundheitscheck der API und aller Systemkomponenten.
    Returns:
        dict: Detaillierte Statusinformationen über alle Komponenten und Statistiken
    """
    components_status = {
        "processor": processor is not None,
        "vektor_store": vektor_store is not None,
        "chat_handler": chat_handler is not None,
        "chat_history": chat_history is not None
    }

    ollama_status = False
    current_model = None
    available_models = []

    if chat_handler:
        ollama_status = chat_handler.ollama_verfuegbar()
        if ollama_status:
            available_models = chat_handler.verfuegbare_modelle_auflisten()
            current_model = chat_handler.model_name if available_models else None

            # Automatisch erstes Modell setzen falls keins gesetzt ist
            if available_models and (not current_model or current_model not in available_models):
                erstes_model = available_models[0]
                chat_handler.model_wechseln(erstes_model)
                current_model = erstes_model
                print(f"Health Check: Automatisch Modell '{erstes_model}' gesetzt")

    document_count = 0
    if vektor_store:
        document_count = len(vektor_store.verfuegbare_dokumente_auflisten())

    upload_count = 0
    upload_size = 0
    upload_dir = "data/uploads"

    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            if os.path.isfile(file_path):
                upload_count += 1
                upload_size += os.path.getsize(file_path)

    health_issues = []
    if not ollama_status:
        health_issues.append("Ollama ist nicht verfügbar")
    elif not available_models:
        health_issues.append("Keine Modelle verfügbar - bitte laden Sie ein Modell herunter")

    return {
        "api_status": "healthy" if not health_issues else "warning",
        "health_issues": health_issues,
        "components": components_status,
        "ollama_available": ollama_status,
        "available_models": available_models,
        "document_count": document_count,
        "uploaded_files_count": upload_count,
        "uploaded_files_size_mb": round(upload_size / (1024 * 1024), 2),
        "current_model": current_model,
        "features": {
            "chat_history": components_status["chat_history"],
            "file_storage": True,
            "chat_memory": True
        }
    }


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")