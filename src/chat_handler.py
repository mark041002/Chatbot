import requests
import json
import re
from typing import Tuple, List, Dict, Any, Optional
from google.adk.agents import LlmAgent
from google.adk.tools import BaseTool, FunctionTool
from google.adk.models import BaseLlm

# Optional: Alternative Planner falls BuiltInPlanner Probleme macht
try:
    from google.adk.planners import BuiltInPlanner

    PLANNER_AVAILABLE = True
except ImportError:
    PLANNER_AVAILABLE = False


class DokumentenSucheTool(BaseTool):
    """
    Tool für Dokumentensuche mit dem VektorStore
    """

    def __init__(self, vektor_store):
        self.vektor_store = vektor_store
        super().__init__(
            name="dokumente_suchen",
            description="Sucht in den verfügbaren Dokumenten nach relevanten Informationen. Nutze dieses Tool nur wenn der Benutzer explizit nach Informationen aus Dokumenten fragt oder wenn seine Frage sich auf spezifische Inhalte bezieht die in Dokumenten stehen könnten."
        )

    def process_llm_request(self, query: str, dokument_name: Optional[str] = None, anzahl_ergebnisse: int = 5) -> Dict[
        str, Any]:
        """
        Führt die Dokumentensuche aus
        """
        try:
            if dokument_name:
                # Spezifische Dokumentensuche
                ergebnisse = self.vektor_store.nach_dokument_suchen(dokument_name, query, anzahl_ergebnisse)
                if not ergebnisse:
                    # Fallback zu allgemeiner Suche
                    ergebnisse = self.vektor_store.aehnliche_suchen(query, anzahl_ergebnisse)
                    return {
                        "success": True,
                        "message": f"Dokument '{dokument_name}' nicht gefunden. Suche in allen Dokumenten durchgeführt.",
                        "ergebnisse": ergebnisse,
                        "anzahl_gefunden": len(ergebnisse)
                    }
            else:
                # Allgemeine Suche
                ergebnisse = self.vektor_store.aehnliche_suchen(query, anzahl_ergebnisse)

            # Ergebnisse für LLM formatieren
            formatierte_ergebnisse = []
            for ergebnis in ergebnisse:
                formatierte_ergebnisse.append({
                    "dokument": ergebnis['dokument'],
                    "text": ergebnis['text'],
                    "relevanz": f"{(1 - ergebnis['distance']):.2f}"
                })

            return {
                "success": True,
                "message": f"Gefunden: {len(ergebnisse)} relevante Abschnitte",
                "ergebnisse": formatierte_ergebnisse,
                "anzahl_gefunden": len(ergebnisse)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Fehler bei der Suche: {str(e)}",
                "ergebnisse": [],
                "anzahl_gefunden": 0
            }


class DokumentenListeTool(BaseTool):
    """
    Tool zum Auflisten verfügbarer Dokumente
    """

    def __init__(self, vektor_store):
        self.vektor_store = vektor_store
        super().__init__(
            name="dokumente_auflisten",
            description="Listet alle verfügbaren Dokumente auf. Nutze dieses Tool nur wenn der Benutzer explizit wissen möchte welche Dokumente verfügbar sind."
        )

    def process_llm_request(self) -> Dict[str, Any]:
        """
        Listet verfügbare Dokumente auf
        """
        try:
            dokumente = self.vektor_store.verfuegbare_dokumente_auflisten()
            return {
                "success": True,
                "dokumente": dokumente,
                "anzahl": len(dokumente),
                "message": f"Verfügbare Dokumente: {', '.join(dokumente) if dokumente else 'Keine'}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Fehler beim Laden der Dokumente: {str(e)}",
                "dokumente": [],
                "anzahl": 0
            }


class OllamaLLM(BaseLlm):
    """
    Ollama LLM Wrapper für Google ADK
    """

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3"):
        # Zuerst BaseLlm mit model initialisieren
        super().__init__(model=model)

        # Dann unsere eigenen Attribute setzen
        self._ollama_url = ollama_url
        self._model_name = model

    @property
    def ollama_url(self):
        return self._ollama_url

    @property
    def model_name(self):
        return self._model_name

    @model_name.setter
    def model_name(self, value):
        self._model_name = value
        # Auch das model attribute der Basisklasse aktualisieren
        object.__setattr__(self, 'model', value)

    def supported_models(self) -> List[str]:
        """
        Gibt unterstützte Modelle zurück
        """
        try:
            response = requests.get(f"{self._ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                modelle = response.json().get("models", [])
                return [model["name"] for model in modelle]
            return []
        except:
            return []

    def connect(self):
        """
        Verbindung zu Ollama herstellen
        """
        try:
            response = requests.get(f"{self._ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    async def generate_content_async(self, prompt: str, **kwargs) -> str:
        """
        Generiert Text mit Ollama (async wrapper)
        """
        return self.generate_content(prompt, **kwargs)

    def generate_content(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        Generiert Text mit Ollama
        """
        try:
            response = requests.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": self._model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                return response.json()["response"]
            else:
                try:
                    error_detail = response.json()
                    return f"Ollama-Fehler {response.status_code}: {error_detail.get('error', 'Unbekannter Fehler')}"
                except:
                    return f"Ollama-Fehler {response.status_code}. Prüfe ob das Model '{self._model_name}' installiert ist."

        except requests.exceptions.RequestException as e:
            return f"Verbindungsfehler zu Ollama: {str(e)}. Stelle sicher dass 'ollama serve' läuft."


class ChatHandlerADK:
    """
    Intelligenter Chat Handler mit Google ADK - Entscheidet automatisch wann Dokumentensuche nötig ist
    """

    def __init__(self, vektor_store, ollama_url: str = "http://localhost:11434", model: str = "llama3"):
        """
        Initialisiert den ADK-basierten Chat Handler

        Args:
            vektor_store: VektorStore Instanz für Dokumentensuche
            ollama_url: URL des Ollama-Servers
            model: Name des zu verwendenden Modells
        """
        self.ollama_url = ollama_url
        self.model = model
        self.vektor_store = vektor_store

        # Ollama LLM initialisieren
        self.llm = OllamaLLM(ollama_url, model)

        # Tools definieren
        self.dokument_suche_tool = DokumentenSucheTool(vektor_store)
        self.dokument_liste_tool = DokumentenListeTool(vektor_store)

        # Agent mit oder ohne Planner erstellen
        agent_kwargs = {
            "name": "IntelligenterAssistent",
            "description": "Ein intelligenter Assistent für normale Unterhaltungen und dokumenten-basierte Fragen",
            "instruction": self._system_prompt_erstellen(),
            "model": self.llm,
            "tools": [self.dokument_suche_tool, self.dokument_liste_tool]
        }

        # Planner nur hinzufügen wenn verfügbar
        if PLANNER_AVAILABLE:
            try:
                agent_kwargs["planner"] = BuiltInPlanner(thinking_config=None)
            except TypeError:
                # Falls thinking_config nicht funktioniert, ohne Planner
                pass

        self.agent = LlmAgent(**agent_kwargs)

    def _ist_faehigkeiten_frage(self, query: str) -> bool:
        """
        Prüft ob nach den Fähigkeiten des Bots gefragt wird
        """
        query_lower = query.lower()
        faehigkeiten_keywords = [
            'was kannst du', 'was kann der bot', 'deine fähigkeiten', 'was bietest du',
            'hilfe', 'was machst du', 'funktionen', 'möglichkeiten',
            'was geht', 'features', 'können sie', 'was ist möglich'
        ]

        return any(keyword in query_lower for keyword in faehigkeiten_keywords)

    def _faehigkeiten_antwort_generieren(self) -> str:
        """
        Generiert eine Antwort über die Fähigkeiten des Bots
        """
        verfuegbare_docs = self.vektor_store.verfuegbare_dokumente_auflisten()
        docs_info = f" Aktuell sind {len(verfuegbare_docs)} Dokumente verfügbar: {', '.join(verfuegbare_docs)}" if verfuegbare_docs else ""

        return f"""Hallo! Ich bin dein KI-Assistent und kann dir auf verschiedene Weise helfen:

🗣️ **Normale Unterhaltungen**
- Fragen zu allen möglichen Themen beantworten
- Erklärungen und Hilfestellungen geben
- Tipps und Ratschläge anbieten
- Einfach mit mir plaudern

📄 **Dokumenten-Chat**
- Du kannst Dokumente (PDF, Word, TXT) hochladen
- Ich durchsuche dann diese Dokumente für dich
- Beantworte Fragen basierend auf deinen Dokumenten
- Nutze "#dokumentname Frage" für spezifische Suchen

🔍 **Intelligente Suche**
- Erkenne automatisch wann Dokumentensuche nötig ist
- Finde relevante Informationen in deinen Dateien
- Gebe Quellen zu meinen Antworten an

{docs_info}

Was möchtest du wissen oder wobei kann ich dir helfen?"""

    def _braucht_dokumentensuche(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Analysiert ob eine Dokumentensuche nötig ist

        Returns:
            Tuple (braucht_suche: bool, dokument_name: Optional[str])
        """
        query_lower = query.lower()

        # 1. Explizite Dokumentenreferenz mit #
        dokument_match = re.search(r'#(\w+)', query)
        if dokument_match:
            return True, dokument_match.group(1)

        # 2. Verfügbare Dokumente abrufen für intelligente Erkennung
        verfuegbare_docs = self.vektor_store.verfuegbare_dokumente_auflisten()

        # 3. Dokument explizit erwähnt
        for doc in verfuegbare_docs:
            if doc.lower() in query_lower:
                return True, doc

        # 4. Keywords die auf Dokumentensuche hindeuten
        dokument_keywords = [
            'in den dokumenten', 'im dokument', 'in meinen dateien',
            'laut dokument', 'steht geschrieben', 'im text',
            'was sagt', 'findest du', 'suche nach',
            'welche informationen', 'was steht über', 'erkläre aus'
        ]

        for keyword in dokument_keywords:
            if keyword in query_lower:
                return True, None

        # 5. Frage nach verfügbaren Dokumenten
        if any(phrase in query_lower for phrase in [
            'welche dokumente', 'was für dokumente', 'verfügbare dokumente',
            'dokumente sind', 'dateien hast du', 'was ist verfügbar'
        ]):
            return True, None

        # 6. Spezifische/technische Begriffe die wahrscheinlich in Dokumenten stehen
        # Diese werden durch LLM-Analyse ergänzt
        if self._scheint_spezifisch(query):
            return True, None

        return False, None

    def _scheint_spezifisch(self, query: str) -> bool:
        """
        Prüft ob die Frage spezifisch genug ist um in Dokumenten zu suchen
        """
        # Sehr allgemeine Fragen brauchen keine Dokumentensuche
        allgemeine_fragen = [
            'wie geht', 'was machst du', 'hallo', 'hi', 'guten tag',
            'wie funktioniert', 'was ist', 'erkläre mir', 'kannst du',
            'hilf mir', 'was sind', 'warum', 'weshalb', 'wieso'
        ]

        query_lower = query.lower()

        # Wenn es eine sehr allgemeine Frage ist
        for allgemein in allgemeine_fragen:
            if query_lower.startswith(allgemein):
                # Außer es folgen spezifische Begriffe
                if len(query.split()) > 3:  # Längere Fragen könnten spezifisch sein
                    continue
                return False

        # Wenn die Frage sehr spezifische Begriffe enthält
        if len(query.split()) > 5:  # Längere Fragen sind oft spezifischer
            return True

        return False

    def dokument_referenz_parsen(self, nachricht: str) -> Tuple[str, str]:
        """
        Parst Dokumentenreferenzen aus der Nachricht

        Args:
            nachricht: Benutzer-Nachricht

        Returns:
            Tuple (dokument_name oder None, bereinigte_nachricht)
        """
        match = re.search(r'#(\w+)', nachricht)

        if match:
            dokument_name = match.group(1)
            bereinigte_nachricht = re.sub(r'#\w+\s*', '', nachricht).strip()
            return dokument_name, bereinigte_nachricht

        return None, nachricht

    def antwort_generieren(self, query: str) -> Dict[str, Any]:
        """
        Generiert eine intelligente Antwort - mit oder ohne Dokumentensuche

        Args:
            query: Benutzer-Query

        Returns:
            Dictionary mit Antwort und Metadaten
        """
        try:
            # 1. Prüfen ob nach Fähigkeiten gefragt wird
            if self._ist_faehigkeiten_frage(query):
                return {
                    "antwort": self._faehigkeiten_antwort_generieren(),
                    "quellen": [],
                    "verwendete_tools": [],
                    "success": True,
                    "modus": "faehigkeiten"
                }

            # 2. Prüfen ob Dokumentensuche nötig ist
            braucht_suche, dokument_name = self._braucht_dokumentensuche(query)

            if braucht_suche:
                return self._antwort_mit_dokumenten(query, dokument_name)
            else:
                return self._normale_antwort(query)

        except Exception as e:
            return {
                "antwort": f"Fehler bei der Antwort-Generierung: {str(e)}",
                "quellen": [],
                "verwendete_tools": [],
                "success": False
            }

    def _normale_antwort(self, query: str) -> Dict[str, Any]:
        """
        Generiert eine normale Antwort ohne Dokumentensuche
        """
        # Prompt für normale Unterhaltung - OHNE THINKING
        prompt = f"""Du bist ein hilfsreicher AI-Assistent. Beantworte die folgende Frage freundlich und hilfreich auf Deutsch. 

WICHTIG: Gib KEINE Denkprozesse oder "thinking" aus. Antworte direkt und ohne Umschweife.

Frage: {query}

Antwort:"""

        antwort = self.llm.generate_content(prompt, temperature=0.8)

        # Bereinige mögliche "thinking" Reste
        antwort = self._bereinige_thinking(antwort)

        return {
            "antwort": antwort,
            "quellen": [],
            "verwendete_tools": [],
            "success": True,
            "modus": "normale_unterhaltung"
        }

    def _antwort_mit_dokumenten(self, query: str, dokument_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generiert eine Antwort basierend auf Dokumentensuche
        """
        # Dokumentenreferenz parsen falls noch nicht geschehen
        if not dokument_name:
            dokument_name, query = self.dokument_referenz_parsen(query)

        # Spezielle Behandlung für "Dokumente auflisten"
        if any(phrase in query.lower() for phrase in [
            'welche dokumente', 'verfügbare dokumente', 'dokumente sind'
        ]):
            list_result = self.dokument_liste_tool.process_llm_request()

            if list_result.get("success") and list_result.get("dokumente"):
                dokumente_text = ", ".join(list_result["dokumente"])
                antwort = f"Hier sind die verfügbaren Dokumente: {dokumente_text}"
            else:
                antwort = "Es sind derzeit keine Dokumente verfügbar."

            return {
                "antwort": antwort,
                "quellen": list_result.get("dokumente", []),
                "verwendete_tools": ["dokumente_auflisten"],
                "success": True,
                "modus": "dokumentensuche"
            }

        # Normale Dokumentensuche
        search_result = self.dokument_suche_tool.process_llm_request(query, dokument_name)
        verwendete_tools = ["dokumente_suchen"]
        quellen = []

        if search_result.get("success") and search_result.get("ergebnisse"):
            # Quellen sammeln
            for ergebnis in search_result["ergebnisse"]:
                if ergebnis["dokument"] not in quellen:
                    quellen.append(ergebnis["dokument"])

            # Kontext für finale Antwort erstellen
            kontext = self._format_search_results(search_result["ergebnisse"])

            # Besserer Prompt mit verfügbaren Dokumenten - OHNE THINKING
            verfuegbare_docs = self.vektor_store.verfuegbare_dokumente_auflisten()
            docs_info = f"\nVerfügbare Dokumente: {', '.join(verfuegbare_docs)}" if verfuegbare_docs else ""

            final_prompt = f"""Du bist ein hilfsreicher Assistent der Fragen basierend auf verfügbaren Dokumenten beantwortet.{docs_info}

WICHTIG: Gib KEINE Denkprozesse oder "thinking" aus. Antworte direkt und ohne Umschweife auf Deutsch.

GEFUNDENER KONTEXT AUS DOKUMENTEN:
{kontext}

BENUTZER-FRAGE: {query}

Beantworte die Frage basierend auf dem gefundenen Kontext. Wenn der Kontext die Frage nicht vollständig beantwortet, sage das ehrlich und erkläre was du aus den verfügbaren Dokumenten weißt.

Antwort:"""

            final_response = self.llm.generate_content(final_prompt)
            final_response = self._bereinige_thinking(final_response)

            return {
                "antwort": final_response,
                "quellen": quellen,
                "verwendete_tools": verwendete_tools,
                "success": True,
                "modus": "dokumentensuche"
            }
        else:
            # Keine relevanten Dokumente gefunden
            verfuegbare_docs = self.vektor_store.verfuegbare_dokumente_auflisten()

            if verfuegbare_docs:
                antwort = f"Ich konnte keine relevanten Informationen zu '{query}' in den verfügbaren Dokumenten finden. Verfügbare Dokumente: {', '.join(verfuegbare_docs)}"
            else:
                antwort = "Es sind derzeit keine Dokumente verfügbar, die ich durchsuchen könnte."

            return {
                "antwort": antwort,
                "quellen": [],
                "verwendete_tools": verwendete_tools,
                "success": True,
                "modus": "dokumentensuche_leer"
            }

    def _bereinige_thinking(self, text: str) -> str:
        """
        Entfernt thinking-Texte und ähnliche Ausdrücke aus der Antwort
        """
        # Muster für thinking-Texte
        thinking_patterns = [
            r'<thinking>.*?</thinking>',
            r'\*thinking\*.*?\*/thinking\*',
            r'Ich denke\.\.\.',
            r'Lass mich überlegen\.\.\.',
            r'Hmm\.\.\.',
            r'\*überlegt\*',
            r'\[thinking\].*?\[/thinking\]',
            r'Zunächst muss ich.*?überlegen',
        ]

        cleaned_text = text
        for pattern in thinking_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL | re.IGNORECASE)

        # Mehrfache Leerzeilen entfernen
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)

        return cleaned_text.strip()

    def _format_search_results(self, ergebnisse: List[Dict]) -> str:
        """
        Formatiert Suchergebnisse für das LLM
        """
        if not ergebnisse:
            return "Keine relevanten Dokumente gefunden."

        formatted = []
        for ergebnis in ergebnisse:
            formatted.append(f"""
---
Dokument: {ergebnis['dokument']}
Relevanz: {ergebnis['relevanz']}
Inhalt: {ergebnis['text']}
---
            """)

        return "\n".join(formatted)

    def ollama_verfuegbar(self) -> bool:
        """
        Prüft ob Ollama erreichbar ist
        """
        return self.llm.connect()

    def verfuegbare_modelle_auflisten(self) -> List[str]:
        """
        Listet verfügbare Ollama-Modelle auf
        """
        return self.llm.supported_models()

    def model_testen(self, model_name: str) -> bool:
        """
        Testet ob ein Model funktioniert
        """
        try:
            test_llm = OllamaLLM(self.ollama_url, model_name)
            if not test_llm.connect():
                return False

            response = test_llm.generate_content("Test", max_tokens=1)
            return "Ollama-Fehler" not in response and "Verbindungsfehler" not in response
        except:
            return False

    def model_wechseln(self, neues_model: str):
        """
        Wechselt das verwendete Ollama-Model
        """
        self.model = neues_model
        self.llm.model_name = neues_model

        # Agent mit neuem Model neu erstellen
        agent_kwargs = {
            "name": "IntelligenterAssistent",
            "description": "Ein intelligenter Assistent für normale Unterhaltungen und dokumenten-basierte Fragen",
            "instruction": self._system_prompt_erstellen(),
            "model": self.llm,
            "tools": [self.dokument_suche_tool, self.dokument_liste_tool]
        }

        # Planner nur hinzufügen wenn verfügbar
        if PLANNER_AVAILABLE:
            try:
                agent_kwargs["planner"] = BuiltInPlanner(thinking_config=None)
            except TypeError:
                pass

        self.agent = LlmAgent(**agent_kwargs)

    def _system_prompt_erstellen(self) -> str:
        """
        Erstellt den System-Prompt für den Agent
        """
        return """Du bist ein intelligenter AI-Assistent der sowohl normale Unterhaltungen führen als auch dokumenten-basierte Fragen beantworten kann.

WICHTIG: Gib NIEMALS Denkprozesse, "thinking", Überlegungen oder ähnliches aus. Antworte immer direkt und ohne Umschweife auf Deutsch.

DEINE FÄHIGKEITEN:
- Normale Unterhaltungen ohne Dokumentensuche
- Durchsuche Dokumente mit dem "dokumente_suchen" Tool NUR wenn nötig
- Liste verfügbare Dokumente mit "dokumente_auflisten" auf NUR wenn explizit danach gefragt
- Erkläre deine Fähigkeiten wenn danach gefragt wird

WANN DOKUMENTE NUTZEN:
- Nur wenn der Benutzer explizit nach Informationen aus Dokumenten fragt
- Wenn spezifische Dokumentnamen erwähnt werden (#dokumentname)
- Wenn nach verfügbaren Dokumenten gefragt wird
- Bei sehr spezifischen Fragen die wahrscheinlich in Dokumenten stehen

WANN KEINE DOKUMENTE NUTZEN:
- Bei normalen Unterhaltungen (Hallo, Wie geht's, etc.)
- Bei allgemeinen Wissensfragen
- Bei persönlichen Gesprächen
- Bei Fragen nach deinen Fähigkeiten
- Wenn keine Dokumente relevant sind

ARBEITSWEISE:
1. Entscheide ZUERST ob Dokumentensuche nötig ist
2. Für normale Fragen → Antworte direkt und freundlich
3. Für dokumenten-basierte Fragen → Nutze entsprechende Tools
4. Sei immer ehrlich wenn du keine relevanten Informationen findest

REGELN:
- Nutze Tools nur wenn wirklich nötig
- Sei freundlich und hilfsreich
- Antworte auf Deutsch
- Gib Quellen an wenn du Dokumente nutzt
- NIEMALS thinking oder Denkprozesse ausgeben
- Direkte, klare Antworten ohne Umschweife"""