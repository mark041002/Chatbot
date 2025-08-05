import streamlit as st
import os
from document_processor import DokumentProcessor
from vektor_store import VektorStore
from chat_handler import ChatHandlerADK

# Seitenkonfiguration
st.set_page_config(
    page_title="Lokaler KI-Chatbot (ADK)",
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
    color: #1565c0 !important;
}
.user-message strong {
    color: #0d47a1 !important;
}
.assistant-message {
    background-color: #f1f8e9;
    border-left: 4px solid #4caf50;
    color: #2e7d32 !important;
}
.assistant-message strong {
    color: #1b5e20 !important;
}
.source-info {
    font-size: 0.8rem;
    color: #616161 !important;
    font-style: italic;
    margin-top: 0.5rem;
}

/* Dark mode support */
[data-theme="dark"] .user-message {
    background-color: #1e3a8a;
    color: #bfdbfe !important;
}
[data-theme="dark"] .assistant-message {
    background-color: #166534;
    color: #bbf7d0 !important;
}
[data-theme="dark"] .source-info {
    color: #9ca3af !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def komponenten_initialisieren():
    """
    Initialisiert alle benötigten Komponenten
    """
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("data/vektor_db", exist_ok=True)

    processor = DokumentProcessor()
    vektor_store = VektorStore()
    chat_handler = ChatHandlerADK(vektor_store)  # ADK Version

    return processor, vektor_store, chat_handler


def datei_hochladen_und_verarbeiten(uploaded_file, processor, vektor_store):
    """
    Verarbeitet hochgeladene Dateien
    """
    if uploaded_file is not None:
        # Datei speichern
        datei_pfad = os.path.join("data/uploads", uploaded_file.name)
        with open(datei_pfad, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            # Dokument verarbeiten
            with st.spinner(f"Verarbeite {uploaded_file.name}..."):
                verarbeitete_daten = processor.dokument_verarbeiten(datei_pfad)

                # Zu Vektordatenbank hinzufügen
                vektor_store.dokument_hinzufuegen(
                    verarbeitete_daten['dokument_name'],
                    verarbeitete_daten['chunks']
                )

                st.success(f"Dokument '{uploaded_file.name}' erfolgreich verarbeitet!")
                st.info(f"Chunks erstellt: {verarbeitete_daten['chunk_anzahl']}")

        except Exception as e:
            st.error(f"Fehler beim Verarbeiten: {str(e)}")


def main():
    """
    Hauptfunktion der Streamlit-App
    """
    st.title("🤖 Lokaler KI-Chatbot")

    # Komponenten initialisieren
    processor, vektor_store, chat_handler = komponenten_initialisieren()

    # Sidebar für Dokument-Management
    with st.sidebar:
        st.header("📄 Dokumenten-Management")

        # Ollama-Status prüfen
        if chat_handler.ollama_verfuegbar():
            st.success("✅ Ollama verbunden")
            verfuegbare_modelle = chat_handler.verfuegbare_modelle_auflisten()
            if verfuegbare_modelle:
                # Zeige verfügbare Modelle mit vollständigen Namen
                ausgewaehltes_model = st.selectbox(
                    "Model auswählen:",
                    verfuegbare_modelle,
                    index=0
                )

                # Model-Test Button
                col1, col2 = st.columns([2, 1])
                with col1:
                    if st.button("🧪 Model testen"):
                        with st.spinner("Teste Model..."):
                            if chat_handler.model_testen(ausgewaehltes_model):
                                st.success(f"✅ Model funktioniert!")
                            else:
                                st.error(f"❌ Model funktioniert nicht!")

                # Model setzen (mit vollständigem Namen inklusive Tag)
                chat_handler.model_wechseln(ausgewaehltes_model)  # ADK Methode

                # Debug-Info
                st.caption(f"Verwendetes Model: `{chat_handler.model}`")

            else:
                st.warning("⚠️ Keine Modelle gefunden!")
                st.markdown("""
                **Installiere ein Model:**
                ```bash
                ollama pull qwen3:8b
                ollama pull llama3
                ollama pull mistral
                ```
                """)
        else:
            st.error("❌ Ollama nicht erreichbar")
            st.info("Stelle sicher, dass Ollama läuft:")
            st.code("ollama serve")

        st.divider()

        # Datei-Upload
        st.subheader("Dokument hochladen")
        uploaded_file = st.file_uploader(
            "Wähle eine Datei",
            type=['pdf', 'txt', 'docx'],
            accept_multiple_files=False
        )

        if st.button("Dokument verarbeiten") and uploaded_file:
            datei_hochladen_und_verarbeiten(uploaded_file, processor, vektor_store)
            st.rerun()

        st.divider()

        # Verfügbare Dokumente anzeigen
        st.subheader("Verfügbare Dokumente")
        verfuegbare_docs = vektor_store.verfuegbare_dokumente_auflisten()

        if verfuegbare_docs:
            for doc in verfuegbare_docs:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {doc}")
                with col2:
                    if st.button("🗑️", key=f"delete_{doc}"):
                        vektor_store.dokument_entfernen(doc)
                        st.success(f"'{doc}' entfernt")
                        st.rerun()
        else:
            st.info("Keine Dokumente vorhanden")

        st.divider()

        # Hilfe-Sektion
        st.subheader("💡 Hilfe")
        st.markdown("""
        **Bot-Fähigkeiten:**
        - 🗣️ Normale Unterhaltungen führen
        - 📚 Allgemeine Fragen beantworten  
        - 📄 Dokumente durchsuchen und analysieren
        - 🔍 Intelligente Dokumentensuche

        **Verwendung:**
        - Normale Frage: "Was ist Künstliche Intelligenz?"
        - Dokumentensuche: "#vertrag Was sind die Kündigungsfristen?"
        - Fähigkeiten: "Was kannst du?"
        - Dokumente: "Welche Dokumente sind verfügbar?"

        **Dokumenttypen:** PDF, Word (.docx), Text (.txt)
        """)

    # Chat-Interface
    col1, col2 = st.columns([3, 1])

    with col1:
        st.header("💬 Chat")

        # Chat-Verlauf initialisieren
        if "nachrichten" not in st.session_state:
            st.session_state.nachrichten = []

        # Willkommensnachricht falls Chat leer
        if not st.session_state.nachrichten:
            st.markdown(f"""
            <div class="chat-message assistant-message">
                <strong>🤖 Assistent:</strong> Hallo! Ich bin dein KI-Assistent. Ich kann normale Unterhaltungen führen und deine Dokumente durchsuchen. Frag einfach "Was kannst du?" um mehr zu erfahren!
            </div>
            """, unsafe_allow_html=True)

        # Chat-Verlauf anzeigen
        for nachricht in st.session_state.nachrichten:
            if nachricht["rolle"] == "user":
                st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>Du:</strong> {nachricht["inhalt"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                quellen_html = ""
                if nachricht.get("quellen"):
                    quellen_html = f'<div class="source-info">📄 Quellen: {nachricht["quellen"]}</div>'

                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <strong>🤖 Assistent:</strong> {nachricht["inhalt"]}
                    {quellen_html}
                </div>
                """, unsafe_allow_html=True)

        # Chat-Input
        benutzer_eingabe = st.chat_input("Stelle eine Frage oder lade ein Dokument hoch...")

        if benutzer_eingabe and chat_handler.ollama_verfuegbar():
            # Benutzer-Nachricht zu Verlauf hinzufügen
            st.session_state.nachrichten.append({
                "rolle": "user",
                "inhalt": benutzer_eingabe
            })

            with st.spinner("Bot antwortet..."):
                # ADK Agent verarbeiten lassen
                result = chat_handler.antwort_generieren(benutzer_eingabe)

                if result["success"]:
                    antwort = result["antwort"]
                    quellen = result["quellen"]
                    verwendete_tools = result["verwendete_tools"]

                    # Tool-Info anzeigen (Debug)
                    if verwendete_tools:
                        st.caption(f"🔧 Tools verwendet: {', '.join(verwendete_tools)}")
                else:
                    antwort = result["antwort"]
                    quellen = []

                # Quellen formatieren
                quellen_text = ", ".join(quellen) if quellen else ""

                # Assistent-Antwort zu Verlauf hinzufügen
                st.session_state.nachrichten.append({
                    "rolle": "assistant",
                    "inhalt": antwort,
                    "quellen": quellen_text
                })

            st.rerun()

    with col2:
        st.header("📊 Statistiken")

        anzahl_dokumente = len(verfuegbare_docs)
        st.metric("Dokumente", anzahl_dokumente)

        anzahl_nachrichten = len(st.session_state.get("nachrichten", []))
        st.metric("Chat-Nachrichten", anzahl_nachrichten)

        # Model-Info
        if chat_handler.ollama_verfuegbar():
            aktives_model = chat_handler.model
            st.metric("Aktives Model", aktives_model.split(":")[0] if ":" in aktives_model else aktives_model)
        else:
            st.metric("Ollama Status", "❌ Offline")

        st.divider()

        # Chat zurücksetzen
        if st.button("🗑️ Chat löschen"):
            st.session_state.nachrichten = []
            st.rerun()

        # Beispiel-Fragen
        st.subheader("🎯 Beispiel-Fragen")
        beispiele = [
            "Was kannst du?",
            "Welche Dokumente sind verfügbar?",
            "Erkläre mir KI",
            "#dokument Was steht drin?"
        ]

        for beispiel in beispiele:
            if st.button(beispiel, key=f"beispiel_{beispiel}", use_container_width=True):
                st.session_state.temp_input = beispiel
                st.rerun()

        # Temporären Input verarbeiten
        if hasattr(st.session_state, 'temp_input'):
            benutzer_eingabe = st.session_state.temp_input
            del st.session_state.temp_input

            if chat_handler.ollama_verfuegbar():
                # Benutzer-Nachricht zu Verlauf hinzufügen
                st.session_state.nachrichten.append({
                    "rolle": "user",
                    "inhalt": benutzer_eingabe
                })

                with st.spinner("Bot antwortet..."):
                    result = chat_handler.antwort_generieren(benutzer_eingabe)

                    if result["success"]:
                        antwort = result["antwort"]
                        quellen = result["quellen"]
                    else:
                        antwort = result["antwort"]
                        quellen = []

                    # Quellen formatieren
                    quellen_text = ", ".join(quellen) if quellen else ""

                    # Assistent-Antwort zu Verlauf hinzufügen
                    st.session_state.nachrichten.append({
                        "rolle": "assistant",
                        "inhalt": antwort,
                        "quellen": quellen_text
                    })

                st.rerun()


if __name__ == "__main__":
    main()