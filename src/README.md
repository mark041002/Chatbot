# Lokaler KI-Chatbot - Setup Anleitung

## 1. Ollama installieren

```bash
# Linux/macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: Download von https://ollama.ai/download
```

## 2. Ollama-Model herunterladen

```bash
# LLaMA 3 (empfohlen)
ollama pull llama3

# Oder andere Modelle
ollama pull mistral
ollama pull codellama
```

## 3. Python-Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

## 4. Projektstruktur erstellen

```bash
mkdir -p data/uploads data/vektor_db
```

## 5. Ollama starten

```bash
ollama serve
```

## 6. Streamlit-App starten

```bash
streamlit run main.py
```

## Verwendung

1. **Dokumente hochladen**: PDF, DOCX oder TXT-Dateien über die Sidebar hochladen
2. **Chatten**: 
   - Normale Fragen: "Was ist das Hauptthema?"
   - Spezifische Dokumente: "#vertrag Was sind die Kündigungsfristen?"

## Troubleshooting

- **Ollama nicht erreichbar**: Prüfe ob `ollama serve` läuft
- **Modell nicht gefunden**: Installiere das gewünschte Modell mit `ollama pull <model>`
- **Memory-Probleme**: Reduziere `chunk_groesse` in `DokumentProcessor`