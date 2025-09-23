"""
Chat Handler - Intelligente Chat-Logik mit Dokumentensuche und Kontextverarbeitung
"""

import re
from typing import Tuple, List, Dict, Any, Optional
from google.adk.agents import LlmAgent

from ollama_client import OllamaLLM

try:
    from google.adk.planners import BuiltInPlanner
    PLANNER_AVAILABLE = True
except ImportError:
    PLANNER_AVAILABLE = False


class ChatHandlerADK:
    """Chat Handler für intelligente Konversationsverarbeitung mit Dokumentenintegration"""

    def __init__(self, vektor_store, ollama_url: str = "http://localhost:11434", model: str = "llama3"):
        """
        Initialisiert den Chat Handler mit allen notwendigen Komponenten.

        Args:
            vektor_store: Vektordatenbank für Dokumentensuche
            ollama_url (str): URL des Ollama-Servers
            model (str): Standard-LLM-Modell
        """
        self.vektor_store = vektor_store
        self.llm = OllamaLLM(ollama_url, model)

        from document_processor import DokumentProcessor
        self.doc_processor = DokumentProcessor(vektor_store=vektor_store)

        self.agent = LlmAgent(
            name="Assistent",
            model=self.llm,
            tools=[self.doc_processor.search_tool, self.doc_processor.list_tool]
        )

    def _chat_history_formatieren(self, session_history: List[Dict[str, Any]], max_nachrichten: int = 8) -> str:
        """
        Formatiert den Chat-Verlauf für die Kontextverarbeitung.

        Args:
            session_history (List[Dict]): Liste aller Nachrichten der Session
            max_nachrichten (int): Maximale Anzahl zu berücksichtigender Nachrichten

        Returns:
            str: Formatierter Chat-Kontext für das LLM
        """
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

    def _ist_persoenliche_frage(self, query: str) -> bool:
        """
        Analysiert ob eine Frage persönlich/kontextbezogen ist.

        Args:
            query (str): Benutzeranfrage

        Returns:
            bool: True wenn die Frage Gesprächskontext benötigt
        """
        keywords = [
            'wie heiße ich', 'mein name', 'vorhin', 'zuvor', 'was habe ich',
            'erinnerst du dich', 'weißt du noch', 'wer bin ich', 'letzte frage'
        ]
        return any(keyword in query.lower() for keyword in keywords)

    def _braucht_dokumentensuche(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Analysiert ob eine Anfrage Dokumentensuche benötigt und extrahiert Dokumentnamen.

        Args:
            query (str): Benutzeranfrage

        Returns:
            Tuple[bool, Optional[str]]: (Suche nötig, spezifisches Dokument)
        """
        query_lower = query.lower()

        # Explizite Dokumentreferenz mit #
        dokument_match = re.search(r'#(\w+)', query)
        if dokument_match:
            return True, dokument_match.group(1)

        # Dokumentbezogene Keywords
        dokument_keywords = [
            'in den dokumenten', 'im dokument', 'laut dokument', 'steht geschrieben',
            'welche dokumente', 'verfügbare dokumente', 'findest du', 'suche nach'
        ]

        if any(keyword in query_lower for keyword in dokument_keywords):
            return True, None

        # Komplexe Fragen automatisch durchsuchen
        if len(query.split()) > 6:
            return True, None

        return False, None

    def antwort_generieren(self, query: str, session_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Hauptfunktion für intelligente Antwortgenerierung mit Multi-Modus-Erkennung.

        Args:
            query (str): Benutzeranfrage
            session_history (List[Dict]): Optionaler Chat-Verlauf für Kontext

        Returns:
            Dict[str, Any]: Strukturierte Antwort mit Metadaten und verwendeten Tools
        """
        chat_kontext = self._chat_history_formatieren(session_history) if session_history else ""

        # Fähigkeiten-Anfrage erkennen
        if any(word in query.lower() for word in ['was kannst du', 'deine fähigkeiten', 'hilfe']):
            return {
                "antwort": "Ich kann normale Fragen beantworten, in deinen Dokumenten suchen und mich an unser Gespräch erinnern. Was möchtest du wissen?",
                "quellen": [],
                "verwendete_tools": [],
                "success": True,
                "modus": "faehigkeiten"
            }

        # Persönliche/Kontext-Fragen
        if self._ist_persoenliche_frage(query):
            if not chat_kontext:
                antwort = "Entschuldigung, ich habe noch keinen Gesprächsverlauf mit dir."
            else:
                prompt = f"""{chat_kontext}
Beantworte die Frage basierend auf unserem Gespräch: {query}

Antwort:"""
                antwort = self.llm.generate_content(prompt, temperature=0.7)

            return {
                "antwort": antwort,
                "quellen": [],
                "verwendete_tools": ["chat_memory"],
                "success": True,
                "modus": "persoenlich"
            }

        # Dokumentensuche-Bedarf prüfen
        braucht_suche, dokument_name = self._braucht_dokumentensuche(query)
        if braucht_suche:
            return self._antwort_mit_dokumenten(query, dokument_name, chat_kontext)

        return self._normale_antwort(query, chat_kontext)

    def _normale_antwort(self, query: str, chat_kontext: str = "") -> Dict[str, Any]:
        """
        Generiert normale Antworten ohne Dokumentensuche.

        Args:
            query (str): Benutzeranfrage
            chat_kontext (str): Optionaler Gesprächskontext

        Returns:
            Dict[str, Any]: Standard-Antwort mit Kontext
        """
        prompt = f"""{chat_kontext if chat_kontext else "Du bist ein hilfsreicher Assistent."}
Beantworte freundlich auf Deutsch: {query}

Antwort:"""

        antwort = self.llm.generate_content(prompt, temperature=0.8)
        tools_used = ["chat_memory"] if chat_kontext else []

        return {
            "antwort": antwort,
            "quellen": [],
            "verwendete_tools": tools_used,
            "success": True,
            "modus": "normal"
        }

    def _antwort_mit_dokumenten(self, query: str, dokument_name: Optional[str] = None, chat_kontext: str = "") -> Dict[str, Any]:
        """
        Generiert Antworten mit Dokumentensuche und Quellenangaben.

        Args:
            query (str): Benutzeranfrage
            dokument_name (Optional[str]): Spezifisches Dokument für die Suche
            chat_kontext (str): Gesprächskontext

        Returns:
            Dict[str, Any]: Antwort mit Dokumentenquellen und Suchmetadaten
        """
        # Spezielle Behandlung für Dokumentenliste
        if 'welche dokumente' in query.lower():
            list_result = self.doc_processor.list_documents()
            if list_result.get("success"):
                dokumente = list_result.get("dokumente", [])
                antwort = f"Verfügbare Dokumente: {', '.join(dokumente)}" if dokumente else "Keine Dokumente verfügbar."
                return {
                    "antwort": antwort,
                    "quellen": dokumente,
                    "verwendete_tools": ["dokumente_auflisten"],
                    "success": True,
                    "modus": "dokumentenliste"
                }

        # Dokumentensuche durchführen
        search_result = self.doc_processor.search_documents(query, dokument_name)
        tools_used = ["dokumente_suchen"]
        if chat_kontext:
            tools_used.append("chat_memory")

        if search_result.get("success") and search_result.get("ergebnisse"):
            dokument_kontext = self.doc_processor.format_search_results(search_result["ergebnisse"])
            quellen = list(set([erg["dokument"] for erg in search_result["ergebnisse"]]))

            prompt = f"""{chat_kontext}
DOKUMENT-KONTEXT:
{dokument_kontext}

Beantworte basierend auf den Dokumenten: {query}

Antwort:"""

            antwort = self.llm.generate_content(prompt)

            return {
                "antwort": antwort,
                "quellen": quellen,
                "verwendete_tools": tools_used,
                "success": True,
                "modus": "dokumentensuche"
            }
        else:
            return {
                "antwort": "Keine relevanten Informationen in den Dokumenten gefunden.",
                "quellen": [],
                "verwendete_tools": tools_used,
                "success": True,
                "modus": "dokumentensuche_leer"
            }

    def ollama_verfuegbar(self) -> bool:
        """Prüft Ollama-Verfügbarkeit"""
        return self.llm.is_available()

    def verfuegbare_modelle_auflisten(self) -> List[str]:
        """Listet alle verfügbaren Ollama-Modelle auf"""
        return self.llm.get_available_models()

    def model_testen(self, model_name: str) -> bool:
        """Testet ob ein Modell funktionsfähig ist"""
        return self.llm.test_model(model_name)

    def model_wechseln(self, neues_model: str):
        """Wechselt zu einem neuen LLM-Modell"""
        self.llm.switch_model(neues_model)

    @property
    def model(self):
        """Gibt das aktuell verwendete Modell zurück"""
        return self.llm.model_name