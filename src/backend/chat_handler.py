"""
Chat Handler - Vereinfacht mit integriertem Ollama Client und intelligenter Dokumentensuche
"""

import requests
import json
from typing import Tuple, List, Dict, Any, Optional


class ChatHandlerADK:
    """Vereinfachter Chat Handler mit integriertem Ollama Client"""

    def __init__(self, vektor_store, ollama_url: str = "http://localhost:11434"):
        """
        Initialisiert den Chat Handler.

        Args:
            vektor_store: Vektordatenbank für Dokumentensuche
            ollama_url (str): URL des Ollama-Servers
        """
        self.vektor_store = vektor_store
        self.ollama_url = ollama_url
        self.model_name = None  # Wird automatisch gesetzt

        # Automatische Modell-Auswahl
        self._initialize_model()

        from document_processor import DokumentProcessor
        self.doc_processor = DokumentProcessor(vektor_store=vektor_store)

    def _initialize_model(self):
        """Initialisiert automatisch das erste verfügbare Modell"""
        if not self.ollama_verfuegbar():
            raise ConnectionError("Ollama Server ist nicht erreichbar. Stelle sicher, dass Ollama läuft.")

        verfuegbare_modelle = self.verfuegbare_modelle_auflisten()

        if not verfuegbare_modelle:
            raise ValueError(
                "Keine Ollama-Modelle gefunden! "
                "Bitte lade zuerst ein Modell herunter mit: 'ollama pull llama3' oder 'ollama pull mistral'"
            )

        # Wähle das erste verfügbare Modell
        self.model_name = verfuegbare_modelle[0]
        print(f"Automatisch ausgewähltes Modell: {self.model_name}")

    def ollama_verfuegbar(self) -> bool:
        """Prüft ob Ollama verfügbar ist"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def verfuegbare_modelle_auflisten(self) -> List[str]:
        """Gibt alle verfügbaren Modelle zurück"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                modelle = response.json().get("models", [])
                return [model["name"] for model in modelle]
        except requests.RequestException:
            pass
        return []

    def model_testen(self, model_name: str) -> bool:
        """Testet ob ein Modell funktioniert"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "Test",
                    "stream": False,
                    "options": {"num_predict": 1}
                },
                timeout=10
            )
            return response.status_code == 200 and "response" in response.json()
        except requests.RequestException:
            return False

    def model_wechseln(self, neues_model: str):
        """Wechselt zu einem neuen Modell"""
        self.model_name = neues_model

    def _generate_content(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Generiert Text mit Ollama"""
        if not self.model_name:
            return "Fehler: Kein Modell verfügbar"

        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=200
            )

            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"Ollama-Fehler {response.status_code}: {response.text}"

        except Exception as e:
            return f"Ollama nicht erreichbar: {str(e)}"

    def _chat_history_formatieren(self, session_history: List[Dict[str, Any]], max_nachrichten: int = 8) -> str:
        """Formatiert den Chat-Verlauf"""
        if not session_history:
            return ""

        recent_messages = session_history[-max_nachrichten:]
        if not recent_messages:
            return ""

        formatted = "\n=== GESPRÄCH ===\n"
        for msg in recent_messages:
            role = "Du" if msg.get("role") == "user" else "Ich"
            content = msg.get("content", "")
            formatted += f"{role}: {content}\n"

        return formatted + "=== AKTUELLE FRAGE ===\n"

    def _get_system_prompt(self) -> str:
        """
        System-Prompt mit Markdown-Unterstützung und Tools.
        """
        verfuegbare_dokumente = self.vektor_store.verfuegbare_dokumente_auflisten()
        dokument_info = ""

        if verfuegbare_dokumente:
            dokument_liste = ", ".join(verfuegbare_dokumente)
            dokument_info = f"""

VERFÜGBARE DOKUMENTE: {dokument_liste}

TOOLS:
- **document_search**: Durchsuche Dokumente nach relevanten Informationen

Du kannst diese Tools verwenden wenn:
- Nutzer nach Informationen fragt die in Dokumenten stehen könnten
- Nutzer explizit nach Dokumenten fragt
- Die Frage komplex genug ist dass eine Dokumentensuche hilfreich wäre

Entscheide selbstständig ob du Tools verwenden möchtest oder direkt antworten kannst."""

        return f"""Du bist ein hilfsreicher KI-Assistent mit Zugang zu hochgeladenen Dokumenten.

MARKDOWN-FORMATIERUNG:
- Nutze **fett** für wichtige Begriffe
- Nutze *kursiv* für Betonungen  
- Nutze `Code` für technische Begriffe
- Nutze ## Überschriften bei längeren Antworten
- Nutze - Listen für Aufzählungen
- Nutze > Blockquotes für wichtige Hinweise{dokument_info}

Antworte auf Deutsch und strukturiere deine Antworten klar."""

    def antwort_generieren(self, query: str, session_history: List[Dict[str, Any]] = None, temperature: float = 0.7) -> Dict[str, Any]:
        """
        Hauptfunktion für intelligente Antwortgenerierung
        """
        # Prüfe ob ein Modell verfügbar ist
        if not self.model_name:
            return {
                "antwort": "**Fehler:** Kein Ollama-Modell verfügbar. Bitte lade zuerst ein Modell herunter:\n\n```bash\nollama pull llama3\n# oder\nollama pull mistral\n```",
                "success": False,
            }

        chat_kontext = self._chat_history_formatieren(session_history) if session_history else ""

        prompt = f"""{self._get_system_prompt()}

{chat_kontext if chat_kontext else ""}
Beantworte freundlich und strukturiert: {query}
Falls du nichts dazu weißt, gib das klar an.
Gib keine erfundenen Informationen wieder.
Gib keinen leeren Text zurück.
Antwort:"""
        antwort = self._generate_content(prompt, temperature=temperature)

        return {
            "antwort": antwort,
            "success": True,
        }


    @property
    def model(self):
        """Gibt das aktuell verwendete Modell zurück"""
        return self.model_name