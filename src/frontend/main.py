"""
Streamlit Frontend - Alternative Web-UI die über die API kommuniziert
"""

import streamlit as st
import requests
import os
import tempfile
from typing import Dict, Any, List

# API Configuration
API_BASE_URL = "http://localhost:8000"


# Streamlit App Configuration
st.set_page_config(
    page_title="Lokaler KI-Chatbot (API Version)",
    page_icon="🤖",
    layout="wide"
)

# CSS für besseres Design
st.markdown("""
<style>
.chat-message {
    padding: 1rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
}
.user-message {
    background-color: #e3f2fd;
    border-left: 4px solid #2196f3;
}
.assistant-message {
    background-color: #f1f8e9;
    border-left: 4px solid #4caf50;
}
.source-info {
    font-size: 0.8rem;
    color: #616161;
    font-style: italic;
    margin-top: 0.5rem;
}
</style>
""", unsafe_allow_html=True)


def api_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """
    Zentrale Funktion für API-Requests

    Args:
        method: HTTP-Methode ('GET', 'POST', 'DELETE')
        endpoint: API-Endpoint (z.B. '/api/health')
        **kwargs: Zusätzliche Argumente für requests

    Returns:
        Dict mit API-Response oder Fehlerinformationen
    """
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.request(method, url, timeout=30, **kwargs)

        if response.status_code == 200:
            return response.json()
        else:
            # Fehlerbehandlung
            try:
                error_data = response.json()
                return {'error': error_data.get('detail', f'HTTP {response.status_code}')}
            except:
                return {'error': f'HTTP {response.status_code}'}

    except requests.exceptions.Timeout:
        return {'error': 'Request timeout - API antwortet nicht'}
    except requests.exceptions.ConnectionError:
        return {'error': 'Verbindung zur API fehlgeschlagen'}
    except Exception as e:
        return {'error': f'Unbekannter Fehler: {str(e)}'}


def main():
    """
    Hauptfunktion der Streamlit-App
    """
    st.title("Lokaler KI-Chatbot (API Version)")

    # Sidebar für System-Management
    with st.sidebar:
        st.header("System-Status")

        # API und Ollama Status prüfen
        health = api_request('GET', '/api/health')

        if health.get('api_status') == 'healthy' and 'error' not in health:
            st.success("API verbunden")

            if health.get('ollama_available'):
                st.success("Ollama verfügbar")

                # Model-Verwaltung
                st.subheader("Model-Verwaltung")
                models_info = api_request('GET', '/api/models')

                if 'error' not in models_info and models_info.get('models'):
                    selected_model = st.selectbox(
                        "Aktives Model:",
                        models_info['models'],
                        index=models_info['models'].index(models_info['current_model'])
                        if models_info['current_model'] in models_info['models'] else 0
                    )

                    if st.button("Model wechseln") and selected_model != models_info['current_model']:
                        with st.spinner("Wechsle Model..."):
                            result = api_request('POST', f'/api/models/{selected_model}')

                            if 'error' not in result:
                                st.success(f"Model zu {selected_model} gewechselt")
                                st.rerun()
                            else:
                                st.error(f"Fehler: {result['error']}")

                else:
                    st.warning("Keine Modelle verfügbar")
                    if 'error' in models_info:
                        st.error(models_info['error'])
                    st.info("Installiere ein Model: `ollama pull llama3`")
            else:
                st.error("Ollama nicht verfügbar")
                st.info("Starte Ollama: `ollama serve`")
        else:
            st.error("API nicht erreichbar")
            if 'error' in health:
                st.error(f"Fehler: {health['error']}")
            st.info("Starte die API: `python api_server.py`")

        st.divider()

        # Dokument-Management
        st.subheader("📄 Dokument-Management")

        # Upload
        uploaded_file = st.file_uploader(
            "Dokument hochladen",
            type=['pdf', 'txt', 'docx'],
            accept_multiple_files=False
        )

        if uploaded_file and st.button("Dokument verarbeiten"):
            with st.spinner("Verarbeite Dokument..."):
                # Datei für Upload vorbereiten
                files = {'file': (uploaded_file.name, uploaded_file.getvalue())}
                result = api_request('POST', '/api/upload', files=files)

                if 'error' not in result:
                    st.success(f"{result.get('message', 'Dokument erfolgreich hochgeladen')}")
                    st.info(f"Chunks erstellt: {result.get('chunks_created', 'N/A')}")
                    st.rerun()
                else:
                    st.error(f"Fehler: {result['error']}")

        # Verfügbare Dokumente
        st.subheader("Verfügbare Dokumente")
        documents_info = api_request('GET', '/api/documents')

        if 'error' not in documents_info and documents_info.get('documents'):
            for doc in documents_info['documents']:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {doc}")
                with col2:
                    if st.button("🗑️", key=f"delete_{doc}"):
                        with st.spinner("Lösche..."):
                            result = api_request('DELETE', f'/api/documents/{doc}')

                            if 'error' not in result:
                                st.success("Dokument gelöscht")
                                st.rerun()
                            else:
                                st.error(f"Fehler: {result['error']}")
        else:
            st.info("Keine Dokumente vorhanden")
            if 'error' in documents_info:
                st.error(f"Fehler beim Laden: {documents_info['error']}")

        st.divider()

        # Hilfe
        st.subheader("💡 Hilfe")
        st.markdown("""
        **Verwendung:**
        - Normale Fragen: "Was ist KI?"
        - Dokumentensuche: "#dokument Frage"
        - Bot-Fähigkeiten: "Was kannst du?"

        **Formate:** PDF, Word, TXT
        """)

    # Chat-Interface
    col1, col2 = st.columns([3, 1])

    with col1:
        st.header("💬 Chat")

        # Chat-Verlauf initialisieren
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        # Willkommensnachricht
        if not st.session_state.chat_messages:
            st.markdown("""
            <div class="chat-message assistant-message">
                <strong>Assistent:</strong> Hallo! Ich bin dein KI-Assistent. 
                Stelle Fragen oder lade Dokumente hoch, um zu beginnen!
            </div>
            """, unsafe_allow_html=True)

        # Chat-Verlauf anzeigen
        for msg in st.session_state.chat_messages:
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>Du:</strong> {msg["content"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                sources_html = ""
                if msg.get("sources"):
                    sources_html = f'<div class="source-info">📄 Quellen: {", ".join(msg["sources"])}</div>'

                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <strong>Assistent:</strong> {msg["content"]}
                    {sources_html}
                </div>
                """, unsafe_allow_html=True)

        # Chat-Input
        user_input = st.chat_input("Stelle eine Frage...")

        if user_input and health.get('ollama_available'):
            # Benutzer-Nachricht hinzufügen
            st.session_state.chat_messages.append({
                "role": "user",
                "content": user_input
            })

            with st.spinner("KI antwortet..."):
                # Chat-Nachricht an API senden
                chat_result = api_request('POST', '/api/chat', json={'message': user_input})

                if 'error' not in chat_result:
                    # Antwort hinzufügen
                    assistant_msg = {
                        "role": "assistant",
                        "content": chat_result.get("response", "Keine Antwort erhalten"),
                        "sources": chat_result.get("sources", [])
                    }
                    st.session_state.chat_messages.append(assistant_msg)

                    # Tools-Info anzeigen (Debug)
                    if chat_result.get("tools_used"):
                        st.caption(f"Tools: {', '.join(chat_result['tools_used'])}")
                else:
                    # Fehler-Nachricht hinzufügen
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": f"Fehler: {chat_result['error']}",
                        "sources": []
                    })

            st.rerun()

        elif user_input:
            st.error("⚠Ollama ist nicht verfügbar. Starte zuerst Ollama!")

    with col2:
        st.header("Status")

        # Statistiken anzeigen
        if health.get('api_status') == 'healthy' and 'error' not in health:
            st.metric("Dokumente", health.get('document_count', 0))
            st.metric("Nachrichten", len(st.session_state.get('chat_messages', [])))

            if health.get('current_model'):
                model_display = health['current_model'].split(':')[0]
                st.metric("Model", model_display)

        # Chat zurücksetzen
        if st.button("Chat löschen"):
            st.session_state.chat_messages = []
            st.rerun()

        # Beispiel-Fragen
        st.subheader("Beispiele")
        examples = [
            "Was kannst du?",
            "Welche Dokumente sind verfügbar?",
            "Erkläre mir Künstliche Intelligenz",
            "#dokument Was steht drin?"
        ]

        for example in examples:
            if st.button(example, key=f"ex_{example}", use_container_width=True):
                # Beispiel als Eingabe setzen
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": example
                })

                with st.spinner("KI antwortet..."):
                    chat_result = api_request('POST', '/api/chat', json={'message': example})

                    if 'error' not in chat_result:
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": chat_result.get("response", "Keine Antwort"),
                            "sources": chat_result.get("sources", [])
                        })
                    else:
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": f" Fehler: {chat_result['error']}",
                            "sources": []
                        })

                st.rerun()


if __name__ == "__main__":
    main()