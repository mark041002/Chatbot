"""
Vereinfachter Ollama Client mit integriertem Management und LLM-Funktionalität
"""

import requests
import json
from typing import List
from google.adk.models import BaseLlm


class OllamaClient(BaseLlm):
    """Vereinfachter Ollama Client mit Management- und LLM-Funktionen"""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3"):
        """
        Initialisiert den Ollama Client.

        Args:
            ollama_url (str): URL des Ollama-Servers
            model (str): Standard-Modellname
        """
        super().__init__(model=model)
        self.ollama_url = ollama_url
        self.model_name = model

    def is_available(self) -> bool:
        """
        Prüft ob der Ollama-Server erreichbar ist.

        Returns:
            bool: True wenn Ollama verfügbar ist
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_available_models(self) -> List[str]:
        """
        Gibt alle verfügbaren Modelle vom Ollama-Server zurück.

        Returns:
            List[str]: Liste aller verfügbaren Modellnamen
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                modelle = response.json().get("models", [])
                return [model["name"] for model in modelle]
        except requests.RequestException:
            pass
        return []

    def test_model(self, model_name: str) -> bool:
        """
        Testet ob ein spezifisches Modell funktionsfähig ist.

        Args:
            model_name (str): Name des zu testenden Modells

        Returns:
            bool: True wenn Modell funktioniert
        """
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

    def download_model(self, model_name: str) -> bool:
        """
        Lädt ein Modell über die Ollama API herunter.

        Args:
            model_name (str): Name des herunterzuladenden Modells

        Returns:
            bool: True wenn Download erfolgreich
        """
        try:
            response = requests.post(
                f"{self.ollama_url}/api/pull",
                json={"name": model_name},
                timeout=300
            )
            return response.status_code == 200
        except Exception:
            return False

    def generate_content(self, prompt: str, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        Generiert Text mit dem Ollama-Modell.

        Args:
            prompt (str): Eingabeprompt für das Modell
            temperature (float): Kreativitätsparameter (0.0-1.0)
            max_tokens (int): Maximale Anzahl generierter Tokens

        Returns:
            str: Generierter Text oder Fehlermeldung
        """
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
                timeout=60
            )

            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"Ollama-Fehler {response.status_code}"

        except Exception as e:
            return f"Ollama nicht erreichbar: {str(e)}"

    def switch_model(self, model_name: str):
        """
        Wechselt zu einem neuen Modell.

        Args:
            model_name (str): Name des neuen Modells
        """
        self.model_name = model_name
        object.__setattr__(self, 'model', model_name)

    def get_model_info(self, model_name: str) -> dict:
        """
        Gibt detaillierte Informationen über ein Modell zurück.

        Args:
            model_name (str): Name des Modells

        Returns:
            dict: Modellinformationen mit Größe und Verfügbarkeitsstatus
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                for model in models:
                    if model["name"] == model_name:
                        return {
                            "name": model["name"],
                            "size": model.get("size", 0),
                            "size_gb": round(model.get("size", 0) / (1024 ** 3), 2),
                            "modified_at": model.get("modified_at", ""),
                            "available": True
                        }
        except requests.RequestException:
            pass
        return {"name": model_name, "available": False}

    def debug_connection(self) -> dict:
        """
        Führt umfassendes Debugging der Ollama-Verbindung durch.

        Returns:
            dict: Detaillierte Debug-Informationen über Verbindung und Modelle
        """
        result = {
            "ollama_url": self.ollama_url,
            "connection": False,
            "models": [],
            "current_status": "unknown",
            "error": None
        }

        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                result["connection"] = True
                result["current_status"] = "online"

                data = response.json()
                models = data.get("models", [])
                result["models"] = [
                    {
                        "name": model["name"],
                        "size_gb": round(model.get("size", 0) / (1024 ** 3), 2)
                    }
                    for model in models
                ]

                # Ein kleines Modell herunterladen wenn keine vorhanden
                if not models:
                    self.download_model("llama3.2:1b")

            else:
                result["current_status"] = f"http_error_{response.status_code}"
                result["error"] = f"HTTP {response.status_code}"

        except requests.exceptions.ConnectionError:
            result["current_status"] = "connection_refused"
            result["error"] = "Verbindung verweigert - Ist Ollama gestartet?"
        except requests.exceptions.Timeout:
            result["current_status"] = "timeout"
            result["error"] = "Timeout - Ollama antwortet nicht"
        except Exception as e:
            result["current_status"] = "unknown_error"
            result["error"] = str(e)

        return result


def ollama_debug():
    """
    Hauptfunktion für Ollama-Debugging mit detaillierter Ausgabe.

    Returns:
        dict: Debug-Informationen über Ollama-Status
    """
    client = OllamaClient()
    debug_info = client.debug_connection()

    print("Ollama Debug-Analyse")
    print("=" * 50)
    print(f"Ollama URL: {debug_info['ollama_url']}")
    print(f"Verbindung: {'OK' if debug_info['connection'] else 'Fehler'}")
    print(f"Status: {debug_info['current_status']}")

    if debug_info['error']:
        print(f"Fehler: {debug_info['error']}")

    if debug_info['connection'] and debug_info['models']:
        print(f"\nVerfügbare Modelle ({len(debug_info['models'])}):")
        for i, model in enumerate(debug_info['models'], 1):
            print(f"   {i}. {model['name']} ({model['size_gb']} GB)")

        print("\nTeste Modelle:")
        for model in debug_info['models']:
            model_name = model['name']
            status = "OK" if client.test_model(model_name) else "Fehler"
            print(f"   {model_name}: {status}")

    elif debug_info['connection']:
        print("\nKeine Modelle installiert!")
        print("   Installiere ein Model mit: ollama pull llama3")

    else:
        print("\nLösungsvorschläge:")
        print("   1. Starte Ollama: ollama serve")
        print("   2. Prüfe URL: http://localhost:11434")
        print("   3. Prüfe Firewall-Einstellungen")

    print("\nDebug abgeschlossen!")
    return debug_info


if __name__ == "__main__":
    ollama_debug()