#!/usr/bin/env python3
"""
Ollama Debug-Tool
Diagnose-Script für Ollama-Verbindungsprobleme
"""

import requests
import json


def ollama_debug():
    """
    Führt verschiedene Tests für Ollama durch
    """
    ollama_url = "http://localhost:11434"

    print("🔍 Ollama Debug-Tool")
    print("=" * 50)

    # 1. Basis-Verbindung testen
    print("\n1️⃣ Teste Ollama-Verbindung...")
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama ist erreichbar")
        else:
            print(f"❌ Ollama antwortet mit Status {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Ollama nicht erreichbar: {e}")
        print("💡 Starte Ollama mit: ollama serve")
        return

    # 2. Verfügbare Modelle auflisten
    print("\n2️⃣ Verfügbare Modelle:")
    try:
        data = response.json()
        modelle = data.get("models", [])
        if modelle:
            for i, model in enumerate(modelle, 1):
                name = model["name"]
                size = model.get("size", 0) / (1024 ** 3)  # GB
                print(f"   {i}. {name} ({size:.1f} GB)")
        else:
            print("   ❌ Keine Modelle installiert!")
            print("   💡 Installiere ein Model mit: ollama pull llama3")
            return
    except Exception as e:
        print(f"   ❌ Fehler beim Laden der Modelle: {e}")
        return

    # 3. Jedes Model testen
    print("\n3️⃣ Teste Modelle:")
    for model in modelle:
        model_name = model["name"]  # Vollständiger Name mit Tag

        print(f"   Testing {model_name}...")

        # Test mit vollständigem Namen (empfohlen)
        success = test_model(ollama_url, model_name)
        if success:
            print(f"   ✅ {model_name} funktioniert")
        else:
            print(f"   ❌ {model_name} funktioniert nicht")

            # Fallback: Test ohne Tag
            base_name = model_name.split(":")[0]
            if base_name != model_name:
                print(f"   Teste auch {base_name}...")
                success = test_model(ollama_url, base_name)
                if success:
                    print(f"   ⚠️  {base_name} funktioniert (ohne Tag)")
                else:
                    print(f"   ❌ {base_name} funktioniert auch nicht")

    print("\n" + "=" * 50)
    print("Debug abgeschlossen! 🎉")


def test_model(ollama_url: str, model_name: str) -> bool:
    """
    Testet ein spezifisches Model
    """
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model_name,
                "prompt": "Hallo",
                "stream": False,
                "options": {"num_predict": 5}
            },
            timeout=15
        )

        if response.status_code == 200:
            result = response.json()
            if "response" in result:
                return True

        # Debug-Info bei Fehlern
        print(f"      Status: {response.status_code}")
        if response.status_code != 200:
            try:
                error_data = response.json()
                print(f"      Error: {error_data}")
            except:
                print(f"      Error: {response.text}")

        return False

    except Exception as e:
        print(f"      Exception: {e}")
        return False


if __name__ == "__main__":
    ollama_debug()