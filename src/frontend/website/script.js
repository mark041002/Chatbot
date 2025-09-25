// Basis-URL für API-Anfragen
const API_BASE = 'http://127.0.0.1:8000';

// Hilfsfunktion, um ein Element anhand der ID zu holen
const $ = id => document.getElementById(id);

// Alle wichtigen DOM-Elemente werden gesammelt
const elements = {
    status: $('status'), modelSelect: $('modelSelect'), testModelBtn: $('testModelBtn'),
    fileUpload: $('fileUpload'), uploadBtn: $('uploadBtn'), documentList: $('documentList'),
    chatMessages: $('chatMessages'), messageInput: $('messageInput'), sendBtn: $('sendBtn'),
    loading: $('loading'), notification: $('notification'), toggleHistoryBtn: $('toggleHistoryBtn'),
    chatHistoryContainer: $('chatHistoryContainer'), newChatBtn: $('newChatBtn'),
    chatSessionsList: $('chatSessionsList'), chatTitle: $('chatTitle'),
    chatSessionInfo: $('chatSessionInfo'), temperatureSlider: $('temperatureSlider'),
    temperatureValue: $('temperatureValue'),
    toolSearchBtn: $('toolSearchBtn')
};

// Status der Anwendung
let state = {
    currentModel: '',                // Aktuell ausgewähltes Modell
    currentSessionId: null,          // Aktuelle Chat-Session-ID
    chatHistoryExpanded: true,       // Status: Chat-Historie sichtbar?
    temperature: 0.7,                // Temperatur für KI-Modell
    toolSearchActive: false          // Status für Tool-Button (nicht benutzt)
};

// API-Methoden für Backend-Kommunikation
const api = {
    // GET-Anfrage ausführen
    async get(endpoint) { return (await fetch(`${API_BASE}${endpoint}`)).json(); },

    // POST-Anfrage ausführen
    async post(endpoint, data = {}) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return { response, data: await response.json() };
    },

    // DELETE-Anfrage ausführen
    async delete(endpoint) { return (await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' })).json(); },

    // Datei-Upload durchführen
    async upload(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });
        return { response, data: await response.json() };
    }
};

// UI-Hilfsfunktionen
const ui = {
    // Zeigt eine Benachrichtigung an
    notify: (message, type = 'success') => {
        elements.notification.textContent = message;
        elements.notification.className = `notification ${type} show`;
        setTimeout(() => elements.notification.classList.remove('show'), 5000);
    }
};

// Temperatur-Slider: Aktualisiert Temperaturwert im State und UI
elements.temperatureSlider.addEventListener('input', (e) => {
    const value = parseInt(e.target.value);
    state.temperature = value / 100;
    elements.temperatureValue.textContent = state.temperature.toFixed(1);
});

// Initialisierung der Anwendung beim Laden
async function initialize() {
    try {
        // Wichtige Daten laden
        await Promise.all([checkHealth(), loadModels(), loadDocuments(), loadChatHistory()]);
        // UI aktivieren
        Object.values(elements).forEach(el => { if (el?.disabled !== undefined) el.disabled = false; });
        ui.notify('Anwendung erfolgreich initialisiert');
    } catch (error) {
        ui.notify('Fehler beim Initialisieren der Anwendung', 'error');
    }
}

// Prüft, ob Backend/Ollama erreichbar ist
async function checkHealth() {
    const data = await api.get('/api/health');
    const statusClass = data.ollama_available ? 'online' : 'offline';
    const statusText = data.ollama_available ? 'Ollama verbunden' : 'Ollama nicht verfügbar';

    // Status anzeigen
    elements.status.className = `status ${statusClass}`;
    elements.status.innerHTML = `
        <div class="status-dot"></div>
        <span>${statusText}</span>
    `;

    // Wenn Ollama nicht verfügbar, Fehler werfen
    if (!data.ollama_available) throw new Error('Ollama nicht verfügbar');
    state.currentModel = data.current_model || '';
}

// Lädt verfügbare KI-Modelle und befüllt Auswahl
async function loadModels() {
    const data = await api.get('/api/models');
    elements.modelSelect.innerHTML = data.models.length > 0
        ? data.models.map(model => `<option value="${model}" ${model === data.current_model ? 'selected' : ''}>${model}</option>`).join('')
        : '<option>Keine Modelle verfügbar</option>';
}

// Lädt die Dokumentenliste und zeigt sie an
async function loadDocuments() {
    const data = await api.get('/api/documents');
    elements.documentList.innerHTML = data.documents.length > 0
        ? data.documents.map(doc => `
            <li class="document-item">
                <div class="document-icon">📄</div>
                <div class="document-info">
                    <div class="document-name">${doc}</div>
                    <div class="document-meta">Dokument</div>
                </div>
                <div class="document-actions">
                    <button class="btn btn-danger btn-tiny" onclick="deleteDocument('${doc}')" title="Löschen">🗑️</button>
                </div>
            </li>
        `).join('')
        : '<li style="color: var(--gray-600); font-style: italic; padding: 20px; text-align: center;">Keine Dokumente vorhanden</li>';
}

// Lädt Chat-Historie (alle gespeicherten Sessions)
async function loadChatHistory() {
    try {
        const sessions = await api.get('/api/chat/sessions');
        elements.chatSessionsList.innerHTML = sessions.length > 0
            ? sessions.map(session => `
                <div class="chat-session-item">
                    <div class="session-content" onclick="loadChatSession('${session.session_id}')">
                        <div class="session-title">${session.title}</div>
                        <div class="session-meta">${session.message_count} Nachrichten • ${formatDate(session.updated_at)}</div>
                    </div>
                    <button class="btn btn-danger btn-tiny" onclick="deleteChatSession('${session.session_id}')">🗑️</button>
                </div>
            `).join('')
            : '<div class="no-sessions">Keine gespeicherten Chats</div>';
    } catch (error) {
        elements.chatSessionsList.innerHTML = '<div class="no-sessions">Fehler beim Laden</div>';
    }
}

// Lädt eine einzelne Chat-Session und zeigt die Nachrichten an
async function loadChatSession(sessionId) {
    try {
        const session = await api.get(`/api/chat/sessions/${sessionId}`);
        elements.chatMessages.innerHTML = '';
        session.messages.forEach(msg => addMessage(msg.content, msg.role, msg.sources || []));
        state.currentSessionId = sessionId;
        updateChatHeader(session.title);
        ui.notify('Chat-Session geladen');
    } catch (error) {
        ui.notify('Fehler beim Laden der Chat-Session', 'error');
    }
}

// Erstellt einen neuen Chat (setzt Session zurück)
function createNewChat() {
    state.currentSessionId = null;
    clearChat();
    updateChatHeader();
    ui.notify('Neuer Chat bereit');
}

// Löscht eine Chat-Session
async function deleteChatSession(sessionId) {
    const isCurrentSession = sessionId === state.currentSessionId;
    try {
        await api.delete(`/api/chat/sessions/${sessionId}`);
        if (isCurrentSession) {
            state.currentSessionId = null;
            clearChat();
            updateChatHeader();
        }
        await loadChatHistory();
        ui.notify('Chat-Session gelöscht');
    } catch (error) {
        ui.notify('Fehler beim Löschen der Chat-Session', 'error');
    }
}

// Aktualisiert den Chat-Titel im Header
function updateChatHeader(title = null) {
    elements.chatTitle.textContent = title ? `💬 ${title}` : '💬 Neuer Chat';
    elements.chatSessionInfo.style.display = title ? 'block' : 'none';
    if (title) elements.chatSessionInfo.textContent = 'Gespeicherte Session';
}

// Sendet eine Nachricht an die API und zeigt Antwort an
async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    elements.messageInput.value = '';
    elements.loading.classList.add('show');
    elements.sendBtn.disabled = true;

    try {
        // Request-Daten zusammenstellen
        const requestBody = {
            message,
            temperature: state.temperature,
        };
        if (state.currentSessionId) {
            requestBody.session_id = state.currentSessionId;
        }

        // Nachricht an Backend schicken
        const { response, data } = await api.post('/api/chat', requestBody);

        if (response.ok && data.success) {
            // KI-Antwort anzeigen
            addMessage(data.response, 'assistant', data.sources);

            // Session-ID ggf. übernehmen und Historie neu laden
            if (data.session_id) {
                const isNewSession = !state.currentSessionId;
                state.currentSessionId = data.session_id;

                if (isNewSession) {
                    await loadChatHistory();
                    ui.notify('Session automatisch erstellt und gespeichert');
                }
            }
        } else {
            addMessage(data.detail || 'Fehler bei der Chat-Anfrage', 'assistant');
        }
    } catch (error) {
        addMessage('Verbindungsfehler zur API', 'assistant');
    } finally {
        elements.loading.classList.remove('show');
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

// Fügt eine Nachricht ins Chat-Fenster ein
function addMessage(content, sender, sources = []) {
    const emptyState = elements.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    // Quellen ggf. anzeigen
    const sourcesHtml = sources.length > 0 ? `<div class="message-sources">📄 Quellen: ${sources.join(', ')}</div>` : '';
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    // Markdown für KI-Antworten rendern (falls 'marked' Bibliothek verfügbar)
    const processedContent = sender === 'assistant' && window.marked ? marked.parse(content) : content;

    messageDiv.innerHTML = `<div class="message-content">${processedContent}</div>${sourcesHtml}`;

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// Löscht alle Nachrichten (setzt Chat zurück)
function clearChat() {
    elements.chatMessages.innerHTML = `
        <div class="empty-state">
            <h3>Willkommen beim lokalen KI-Chatbot</h3>
            <p>Stelle eine Frage oder lade ein Dokument hoch, um zu beginnen.</p>
        </div>
    `;
}

// Dokument hochladen
async function uploadDocument() {
    const file = elements.fileUpload.files[0];
    if (!file) return ui.notify('Bitte wähle eine Datei aus', 'error');

    elements.uploadBtn.disabled = true;
    elements.uploadBtn.textContent = 'Lade hoch...';

    try {
        const { response, data } = await api.upload(file);
        if (response.ok) {
            let message = data.message;
            if (data.ocr_used) message += ` (OCR verwendet: ${data.processing_info})`;
            ui.notify(message);
            await Promise.all([loadDocuments(), checkHealth()]);
            elements.fileUpload.value = '';
        } else {
            ui.notify(data.detail || 'Upload fehlgeschlagen', 'error');
        }
    } catch (error) {
        ui.notify('Fehler beim Hochladen', 'error');
    } finally {
        elements.uploadBtn.disabled = false;
        elements.uploadBtn.textContent = 'Hochladen';
    }
}

// Dokument löschen
async function deleteDocument(docName) {
    try {
        await api.delete(`/api/documents/${docName}`);
        ui.notify('Dokument gelöscht');
        await Promise.all([loadDocuments(), checkHealth()]);
    } catch (error) {
        ui.notify('Fehler beim Löschen', 'error');
    }
}

// Testet das ausgewählte Modell auf Funktion
async function testModel() {
    const model = elements.modelSelect.value;
    if (!model) return;

    elements.testModelBtn.disabled = true;
    elements.testModelBtn.textContent = 'Teste...';

    try {
        const { response } = await api.post(`/api/models/${model}`);
        if (response.ok) {
            ui.notify('Model funktioniert!');
            state.currentModel = model;
        } else {
            ui.notify('Model-Test fehlgeschlagen', 'error');
        }
    } catch (error) {
        ui.notify('Fehler beim Testen des Models', 'error');
    } finally {
        elements.testModelBtn.disabled = false;
        elements.testModelBtn.textContent = 'Model testen';
    }
}

// Formatiert ein Datum für Anzeige (z.B. "vor 2 Std")
function formatDate(dateString) {
    const date = new Date(dateString);
    const diffMs = new Date() - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Gerade eben';
    if (diffMins < 60) return `vor ${diffMins} Min`;
    if (diffHours < 24) return `vor ${diffHours} Std`;
    if (diffDays < 7) return `vor ${diffDays} Tag${diffDays > 1 ? 'en' : ''}`;
    return date.toLocaleDateString('de-DE');
}

// Blendet die Chat-Historie ein/aus
function toggleChatHistory() {
    state.chatHistoryExpanded = !state.chatHistoryExpanded;
    elements.chatHistoryContainer.style.display = state.chatHistoryExpanded ? 'block' : 'none';
    elements.toggleHistoryBtn.querySelector('.toggle-icon').textContent = state.chatHistoryExpanded ? '▼' : '▶';
}

// Event-Listener für UI-Elemente
elements.testModelBtn.addEventListener('click', testModel);
elements.uploadBtn.addEventListener('click', uploadDocument);
elements.sendBtn.addEventListener('click', sendMessage);
elements.newChatBtn.addEventListener('click', createNewChat);
elements.toggleHistoryBtn.addEventListener('click', toggleChatHistory);
elements.messageInput.addEventListener('keypress', (e) => e.key === 'Enter' && !elements.sendBtn.disabled && sendMessage());

// Modellwechsel: sendet neuen Modellnamen ans Backend
elements.modelSelect.addEventListener('change', async () => {
    const selectedModel = elements.modelSelect.value;
    if (selectedModel && selectedModel !== state.currentModel) {
        try {
            const { response } = await api.post(`/api/models/${selectedModel}`);
            if (response.ok) {
                state.currentModel = selectedModel;
                ui.notify(`Model zu ${selectedModel} gewechselt`);
            } else {
                ui.notify('Model-Wechsel fehlgeschlagen', 'error');
                elements.modelSelect.value = state.currentModel;
            }
        } catch (error) {
            ui.notify('Fehler beim Wechseln des Models', 'error');
            elements.modelSelect.value = state.currentModel;
        }
    }
});

// Initialisierung beim Laden der Seite
document.addEventListener('DOMContentLoaded', initialize);