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


# Pydantic Models
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    tools_used: List[str]
    success: bool
    mode: str


class DocumentListResponse(BaseModel):
    documents: List[str]
    count: int


class ModelResponse(BaseModel):
    models: List[str]
    current_model: str
    ollama_available: bool


# FastAPI App erstellen
app = FastAPI(
    title="Lokaler KI-Chatbot API",
    description="API für den lokalen KI-Chatbot mit Dokumentensuche",
    version="1.0.0"
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
    os.makedirs("static", exist_ok=True)

    processor = DokumentProcessor()
    vektor_store = VektorStore()
    chat_handler = ChatHandlerADK(vektor_store)

    return processor, vektor_store, chat_handler


# Globale Komponenten
processor, vektor_store, chat_handler = initialize_components()


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat-Endpoint für Nachrichten"""
    try:
        if not chat_handler.ollama_verfuegbar():
            raise HTTPException(status_code=503, detail="Ollama ist nicht verfügbar")

        result = chat_handler.antwort_generieren(request.message)

        return ChatResponse(
            response=result["antwort"],
            sources=result["quellen"],
            tools_used=result["verwendete_tools"],
            success=result["success"],
            mode=result.get("modus", "unknown")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat-Fehler: {str(e)}")


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
    """Lädt ein Dokument hoch und verarbeitet es"""
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
                "text_length": processed_data['text_laenge']
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
        "current_model": chat_handler.model if ollama_status else None
    }


if __name__ == "__main__":
    print("🚀 Starte Lokaler KI-Chatbot API Server...")
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )