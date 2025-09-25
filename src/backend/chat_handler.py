"""
Chat Handler - Mit integriertem Ollama Client und Dokumentensuche
"""

import requests
import json
import re
from typing import Tuple, List, Dict, Any, Optional

class ChatHandlerADK:
    """Chat Handler mit Ollama Client und echtem RAG"""

    def __init__(self, vektor_store, ollama_url: str = "http://localhost:11434"):
        self.vektor_store = vektor_store
        self.ollama_url = ollama_url
        self.model_name = None
        self.initialize_model()
        from document_processor import DokumentProcessor
        self.doc_processor = DokumentProcessor(vektor_store=vektor_store)

    def initialize_model(self):
        """Initialisiert das erste verfügbare Modell"""
        if not self.ollama_verfuegbar():
            raise ConnectionError("Ollama Server ist nicht erreichbar.")
        verfuegbare_modelle = self.verfuegbare_modelle_auflisten()
        if not verfuegbare_modelle:
            raise ValueError(
                "Keine Ollama-Modelle gefunden! Bitte lade zuerst ein Modell herunter."
            )
        self.model_name = verfuegbare_modelle[0]

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

    def document_search(self, suchbegriff: str, dateien: List[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Führt eine echte semantische Suche in den Dokumenten durch
        """
        try:
            # Erstelle Embedding für den Suchbegriff
            query_embedding = self.vektor_store.embedding_model.encode([suchbegriff]).tolist()[0]

            # Führe die Suche durch
            where_filter = None
            if dateien:
                where_filter = {"dokument": {"$in": dateien}}

            results = self.vektor_store.collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results,
                where=where_filter
            )

            # Formatiere die Ergebnisse
            if not results['documents'][0]:
                return []

            formatted_results = []
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'dokument': results['metadatas'][0][i]['dokument'],
                    'text': results['documents'][0][i],
                    'distance': results['distances'][0][i],
                    'chunk_index': results['metadatas'][0][i]['chunk_index']
                })

            return formatted_results

        except Exception as e:
            print(f"Fehler bei Dokumentensuche: {e}")
            return []

    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Parst Tool-Calls aus dem Modell-Output
        Sucht nach Mustern wie: document_search.{"suchbegriff":"xyz","dateien":["abc.pdf"]}
        """
        tool_calls = []

        # Regex für Tool-Calls
        pattern = r'document_search\.(\{[^}]+\})'
        matches = re.findall(pattern, text)

        for match in matches:
            try:
                # Parse JSON-Parameter
                params = json.loads(match)
                tool_calls.append({
                    'tool': 'document_search',
                    'parameters': params
                })
            except json.JSONDecodeError:
                print(f"Konnte Tool-Call nicht parsen: {match}")

        return tool_calls

    def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> str:
        """
        Führt die erkannten Tool-Calls aus
        """
        results = []

        for tool_call in tool_calls:
            if tool_call['tool'] == 'document_search':
                params = tool_call['parameters']
                suchbegriff = params.get('suchbegriff', '')
                dateien = params.get('dateien', None)

                search_results = self.document_search(suchbegriff, dateien)

                if search_results:
                    result_text = f"\n**Suchergebnisse für '{suchbegriff}':**\n\n"
                    for i, result in enumerate(search_results[:3], 1):  # Top 3 Ergebnisse
                        result_text += f"**Quelle {i} ({result['dokument']}):**\n"
                        result_text += f"{result['text']}\n\n"
                    results.append(result_text)
                else:
                    results.append(f"\nKeine Ergebnisse für '{suchbegriff}' gefunden.\n")

        return "\n".join(results) if results else ""

    def generate_content(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Generiert Text mit Ollama und verarbeitet Tool-Calls"""
        if not self.model_name:
            return "Fehler: Kein Modell verfügbar"

        print(f"=== PROMPT SENT TO OLLAMA ===")
        print(prompt)
        print(f"=== END PROMPT ===")

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

            print(f"=== OLLAMA RESPONSE ===")
            print(response)
            print(response.json())

            if response.status_code == 200:
                model_output = response.json()["response"]
                print(f"Model Output: {model_output}")

                # Prüfe auf Tool-Calls
                tool_calls = self.parse_tool_calls(model_output)

                if tool_calls:
                    print(f"🔧 TOOL-CALLS ERKANNT: {tool_calls}")

                    # Führe Tool-Calls aus
                    tool_results = self.execute_tool_calls(tool_calls)

                    if tool_results:
                        # Erstelle einen neuen Prompt mit den Tool-Ergebnissen
                        enhanced_prompt = f"""{prompt}

TOOL-ERGEBNISSE:
{tool_results}

Basierend auf diesen Suchergebnissen, beantworte die Frage ausführlich und präzise. Zitiere konkrete Stellen aus den Dokumenten."""

                        # Zweiter API-Call mit den Tool-Ergebnissen
                        enhanced_response = requests.post(
                            f"{self.ollama_url}/api/generate",
                            json={
                                "model": self.model_name,
                                "prompt": enhanced_prompt,
                                "stream": False,
                                "options": {
                                    "temperature": temperature,
                                    "num_predict": max_tokens
                                }
                            },
                            timeout=200
                        )

                        if enhanced_response.status_code == 200:
                            final_output = enhanced_response.json()["response"]
                            print(f"=== ENHANCED RESPONSE ===")
                            print(final_output)
                            print(f"=== END ENHANCED RESPONSE ===")
                            return final_output

                print(f"=== FINAL RESPONSE ===")
                print(model_output)
                print(f"=== END RESPONSE ===")
                return model_output
            else:
                return f"Ollama-Fehler {response.status_code}: {response.text}"
        except Exception as e:
            return f"Ollama nicht erreichbar: {str(e)}"

    def chat_history_formatieren(self, session_history: List[Dict[str, Any]], max_nachrichten: int = 8) -> str:
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

    def get_system_prompt(self) -> str:
        """
        System-Prompt mit Markdown und Tools
        """
        verfuegbare_dokumente = self.vektor_store.verfuegbare_dokumente_auflisten()
        dokument_info = ""
        if verfuegbare_dokumente:
            dokument_liste = ", ".join(verfuegbare_dokumente)
            dokument_info = f"""

VERFÜGBARE DOKUMENTE: {dokument_liste}

TOOLS:
- **document_search**: Durchsuche Dokumente nach relevanten Informationen
  Format: document_search.{{"suchbegriff":"SUCHBEGRIFF","dateien":["DATEINAME.pdf"]}}
  GENAU IN DIESEM FORMAT UND NICHT ANDERS!!!
  
  
Du kannst dieses Tool verwenden wenn:
- Nutzer nach spezifischen Informationen aus Dokumenten fragt
- Du detaillierte Inhalte aus den Dokumenten benötigst
- Die Frage konkrete Fakten, Zahlen oder Zitate erfordert

WICHTIG: Verwende das Tool NUR wenn du spezifische Informationen aus den Dokumenten brauchst!"""
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
        Antwortgenerierung mit RAG-Unterstützung
        """
        if not self.model_name:
            return {
                "antwort": "**Fehler:** Kein Ollama-Modell verfügbar. Bitte lade zuerst ein Modell herunter.",
                "success": False,
            }

        chat_kontext = self.chat_history_formatieren(session_history) if session_history else ""
        prompt = f"""{self.get_system_prompt()}

{chat_kontext if chat_kontext else ""}
Beantworte freundlich und strukturiert: {query}
Falls du nichts dazu weißt, gib das klar an.
Gib keine erfundenen Informationen wieder.
Gib keinen leeren Text zurück.
Antwort:"""
        antwort = self.generate_content(prompt, temperature=temperature)
        return {
            "antwort": antwort,
            "success": True,
        }

    @property
    def model(self):
        """Gibt das aktuell verwendete Modell zurück"""
        return self.model_name