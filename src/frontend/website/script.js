const API_BASE = 'http://127.0.0.1:8000';

const $ = id => document.getElementById(id);
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

let state = {
    currentModel: '',
    currentSessionId: null,
    chatHistoryExpanded: true,
    temperature: 0.7,
    toolSearchActive: false // NEU: Status für Tool-Button
};

const api = {
    async get(endpoint) { return (await fetch(`${API_BASE}${endpoint}`)).json(); },
    async post(endpoint, data = {}) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        return { response, data: await response.json() };
    },
    async delete(endpoint) { return (await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' })).json(); },
    async upload(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });
        return { response, data: await response.json() };
    }
};

const ui = {
    notify: (message, type = 'success') => {
        elements.notification.textContent = message;
        elements.notification.className = `notification ${type} show`;
        setTimeout(() => elements.notification.classList.remove('show'), 5000);
    }
};

elements.temperatureSlider.addEventListener('input', (e) => {
    const value = parseInt(e.target.value);
    state.temperature = value / 100;
    elements.temperatureValue.textContent = state.temperature.toFixed(1);
});

async function initialize() {
    try {
        await Promise.all([checkHealth(), loadModels(), loadDocuments(), loadChatHistory()]);
        Object.values(elements).forEach(el => { if (el?.disabled !== undefined) el.disabled = false; });
        ui.notify('Anwendung erfolgreich initialisiert');
    } catch (error) {
        ui.notify('Fehler beim Initialisieren der Anwendung', 'error');
    }
}

async function checkHealth() {
    const data = await api.get('/api/health');
    const statusClass = data.ollama_available ? 'online' : 'offline';
    const statusText = data.ollama_available ? 'Ollama verbunden' : 'Ollama nicht verfügbar';

    elements.status.className = `status ${statusClass}`;
    elements.status.innerHTML = `
        <div class="status-dot"></div>
        <span>${statusText}</span>
        ${data.ollama_available ? `<small style="color: var(--gray-600); margin-left: 10px;">
            ${data.uploaded_files_count} Dateien (${data.uploaded_files_size_mb} MB)
        </small>` : ''}
    `;

    if (!data.ollama_available) throw new Error('Ollama nicht verfügbar');
    state.currentModel = data.current_model || '';
}

async function loadModels() {
    const data = await api.get('/api/models');
    elements.modelSelect.innerHTML = data.models.length > 0
        ? data.models.map(model => `<option value="${model}" ${model === data.current_model ? 'selected' : ''}>${model}</option>`).join('')
        : '<option>Keine Modelle verfügbar</option>';
}

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

function createNewChat() {
    state.currentSessionId = null;
    clearChat();
    updateChatHeader();
    ui.notify('Neuer Chat bereit');
}

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

function updateChatHeader(title = null) {
    elements.chatTitle.textContent = title ? `💬 ${title}` : '💬 Neuer Chat';
    elements.chatSessionInfo.style.display = title ? 'block' : 'none';
    if (title) elements.chatSessionInfo.textContent = 'Gespeicherte Session';
}

async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    elements.messageInput.value = '';
    elements.loading.classList.add('show');
    elements.sendBtn.disabled = true;

    try {
        const requestBody = {
            message,
            temperature: state.temperature,
        };
        if (state.currentSessionId) {
            requestBody.session_id = state.currentSessionId;
        }

        const { response, data } = await api.post('/api/chat', requestBody);

        if (response.ok && data.success) {
            addMessage(data.response, 'assistant', data.sources);

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

function addMessage(content, sender, sources = []) {
    const emptyState = elements.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const sourcesHtml = sources.length > 0 ? `<div class="message-sources">📄 Quellen: ${sources.join(', ')}</div>` : '';
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const processedContent = sender === 'assistant' && window.marked ? marked.parse(content) : content;

    messageDiv.innerHTML = `<div class="message-content">${processedContent}</div>${sourcesHtml}`;

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function clearChat() {
    elements.chatMessages.innerHTML = `
        <div class="empty-state">
            <h3>Willkommen beim lokalen KI-Chatbot</h3>
            <p>Stelle eine Frage oder lade ein Dokument hoch, um zu beginnen.</p>
            <p>Benutze den Knopf Links von der Eingabezeile um die Dokumentensuche zu aktivieren/deaktivieren</p>
        </div>
    `;
}

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

async function deleteDocument(docName) {
    try {
        await api.delete(`/api/documents/${docName}`);
        ui.notify('Dokument gelöscht');
        await Promise.all([loadDocuments(), checkHealth()]);
    } catch (error) {
        ui.notify('Fehler beim Löschen', 'error');
    }
}

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

function toggleChatHistory() {
    state.chatHistoryExpanded = !state.chatHistoryExpanded;
    elements.chatHistoryContainer.style.display = state.chatHistoryExpanded ? 'block' : 'none';
    elements.toggleHistoryBtn.querySelector('.toggle-icon').textContent = state.chatHistoryExpanded ? '▼' : '▶';
}

// Event Listeners
elements.testModelBtn.addEventListener('click', testModel);
elements.uploadBtn.addEventListener('click', uploadDocument);
elements.sendBtn.addEventListener('click', sendMessage);
elements.newChatBtn.addEventListener('click', createNewChat);
elements.toggleHistoryBtn.addEventListener('click', toggleChatHistory);
elements.messageInput.addEventListener('keypress', (e) => e.key === 'Enter' && !elements.sendBtn.disabled && sendMessage());

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

document.addEventListener('DOMContentLoaded', initialize);