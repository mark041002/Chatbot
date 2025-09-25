# Lokaler KI-Chatbot — Installations- und Startanleitung

Dieses Projekt stellt einen lokalen KI-Chatbot mit Dokumentensuche, Chat-Verlauf und OCR-Unterstützung bereit. Die Lösung basiert auf FastAPI, Ollama (für lokale Sprachmodelle), ChromaDB, Sentence Transformers sowie EasyOCR für Texterkennung.

## Voraussetzungen

**Hardwareempfehlung:**
Am besten eine GPU (NVIDIA empfohlen) für schnellere Modellinferenz. CPU funktioniert, aber langsamer.
Dabei ist muss die größe des Modells in den VRAM passen (z.B. 4-8 GB für kleinere Modelle, 16+ GB für größere).
Alternativ kann auch CPU-only genutzt werden, was aber deutlich langsamer ist.

**Softwareanforderungen:**
Leider kann ich nur bestätigen, dass es unter Windows 11 problemlos läuft. Ich vermute aber, dass Linux auch keine Probleme machen sollte

### 1. Python installieren
Sollte selbsterklärend sein.

### 2. Ollama installieren (für lokale KI-Modelle)

- **Windows:** (https://ollama.com/download)

Installationsprogramm herunterladen und ausführen.
Falls Ollama dann nicht startet, eine Konsole öffnen und `ollama serve` ausführen.

### 3. Benötigte Python-Pakete installieren

Am besten in einer eigenen Umgebung (virtualenv oder conda):

```bash

pip install pillow numpy fastapi requests chromadb sentence-transformers easyocr pdf2image PyPDF2 python-docx
```

#### Zusätzliche Abhängigkeiten für OCR

- **Poppler installieren (für PDF-OCR):**
 
  - **Windows:**  
  https://github.com/oschwartz10612/poppler-windows?tab=readme-ov-file
  Unter download die neueste Version herunterladen, entpacken und den `bin`-Ordner zum PATH hinzufügen.
  Wird nur für die OCR Unterstützung bei PDFs benötigt.

### 4. Modell mit Ollama herunterladen

Mindestens ein Sprachmodell muss lokal vorhanden sein. Beispiele:
In der Konsole:
```bash
ollama pull gemma3:4b

ollama pull qwen3:12b
```
Gemma3:4b braucht ca. 4GB VRAM, Qwen3:12b ca. 9GB VRAM.
Falls sie nur eine CPU haben, nutzen sie gemma3:4b oder gemma3:1b.
Prinzipiell können auch andere Modelle genutzt werden, die mit Ollama kompatibel sind.
Die Modellnamen finden sie unter https://ollama.com/library

### 6. Anwendung starten
1. **Ollama-Server starten** (falls nicht bereits aktiv):
   ```bash
   ollama serve
   ```
2. **API-Server starten:**
   ```bash
   python api_server.py
   ```
   oder mit Uvicorn:
   ```bash
   uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
   ```

Die API ist jetzt erreichbar unter:  
http://localhost:8000


### 8. Frontend öffnen

Nun können sie im Frontend die Webseite öffnen.
Oben Rechts sollte nun in Grün Ollama verbunden stehen und es sollte in der Mitte ein Popup erscheinen, wo steht Anwedung erfolgreich gestartet.

Nun können sie den Chatbot nutzen.

Zum Chatten einfach eine Nachricht eingeben und auf Senden klicken.
Rechts kann ein neuer Chat gestartet werden und auf alte Chats zugegriffen werden/gelöscht werden.
Darunter kann man die Kreativität des Modells einstellen (0 = sehr konservativ, 1 = sehr kreativ).
Weiter drunter kann per Dropdown zwischen den heruntergeladenen Modellen gewechselt werden und ein kurzer Check durchgeführt werden.
Auf der Rechten Seite können sie per Drag & Drop oder Dateiauswahl Dokumente hochladen (PDF, txt getestet, docx sollte gehen, habe das Dateiformat leider nicht parat).
Ebenfalls sehen sie dort alle hochgeladenen Dokumente und können diese auch wieder löschen.


**Viel Erfolg beim lokalen KI-Chatbot!**