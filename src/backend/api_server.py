from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    version="2.0.0"
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

    return processor, vektor_store, chat_handler, chat_history


processor, vektor_store, chat_handler, chat_history = initialize_components()


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Hauptendpoint für Chat-Nachrichten mit automatischem Session-Management.

    Args:
        request (ChatRequest): Chat-Anfrage mit Nachricht und optionaler Session-ID

    Returns:
        ChatResponse: Antwort mit generiertem Text, Quellen und verwendeten Tools
    """
    if not chat_handler or not chat_handler.ollama_verfuegbar():
        raise HTTPException(status_code=503, detail="Ollama ist nicht verfügbar")

    session_id = request.session_id
    if not session_id:
        session_id = chat_history.create_session()

    # Session-Verlauf laden für Kontext
    session_data = None
    session_history = []
    if chat_history:
        session_data = chat_history.get_session(session_id)
        if session_data:
            session_history = session_data.get("messages", [])

    chat_history.add_message(session_id, "user", request.message)

    result = chat_handler.antwort_generieren(request.message, session_history)

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
    if not chat_history:
        raise HTTPException(status_code=503, detail="Chat History nicht verfügbar")

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
    if not chat_history:
        raise HTTPException(status_code=503, detail="Chat History nicht verfügbar")

    success = chat_history.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    return {"message": f"Session '{session_id}' erfolgreich gelöscht"}


@app.post("/api/chat/sessions")
async def create_chat_session(title: Optional[str] = None):
    """
    Erstellt eine neue Chat-Session.

    Args:
        title (Optional[str]): Optionaler Titel für die Session

    Returns:
        dict: Session-ID und Bestätigungsnachricht
    """
    if not chat_history:
        raise HTTPException(status_code=503, detail="Chat History nicht verfügbar")

    session_id = chat_history.create_session(title)
    return {"session_id": session_id, "message": "Session erfolgreich erstellt"}


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
    if not vektor_store:
        raise HTTPException(status_code=503, detail="Vektor Store nicht verfügbar")

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


@app.get("/api/uploads")
async def get_uploaded_files():
    """
    Listet alle hochgeladenen Dateien mit detaillierten Metadaten auf.

    Returns:
        dict: Liste aller Dateien mit Größe, Änderungsdatum und Anzahl
    """
    upload_dir = "data/uploads"
    if not os.path.exists(upload_dir):
        return {"files": [], "count": 0}

    files = []
    for filename in os.listdir(upload_dir):
        file_path = os.path.join(upload_dir, filename)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            file_modified = os.path.getmtime(file_path)

            files.append({
                "filename": filename,
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "modified_timestamp": file_modified,
                "extension": os.path.splitext(filename)[1].lower()
            })

    files.sort(key=lambda x: x["modified_timestamp"], reverse=True)
    return {"files": files, "count": len(files)}


@app.get("/api/uploads/{filename}")
async def download_uploaded_file(filename: str):
    """
    Lädt eine hochgeladene Datei herunter.

    Args:
        filename (str): Name der herunterzuladenden Datei

    Returns:
        FileResponse: Datei als Download
    """
    file_path = os.path.join("data/uploads", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


@app.delete("/api/uploads/{filename}")
async def delete_uploaded_file(filename: str):
    """
    Löscht eine Datei aus dem Upload-Ordner.

    Args:
        filename (str): Name der zu löschenden Datei

    Returns:
        dict: Bestätigungsnachricht
    """
    file_path = os.path.join("data/uploads", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    os.remove(file_path)
    return {"message": f"Datei '{filename}' erfolgreich entfernt"}


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
    current_model = chat_handler.model if ollama_available else ""

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
    if not chat_handler:
        raise HTTPException(status_code=503, detail="Chat Handler nicht verfügbar")

    if not chat_handler.ollama_verfuegbar():
        raise HTTPException(status_code=503, detail="Ollama ist nicht verfügbar")

    available_models = chat_handler.verfuegbare_modelle_auflisten()
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
    if chat_handler:
        ollama_status = chat_handler.ollama_verfuegbar()
        current_model = chat_handler.model if ollama_status else None

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

    return {
        "api_status": "healthy",
        "components": components_status,
        "ollama_available": ollama_status,
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
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )