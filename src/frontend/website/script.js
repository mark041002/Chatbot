const API_BASE = 'http://127.0.0.1:8000';

// DOM Elements - alle auf einmal holen
const elements = {
    status: document.getElementById('status'),
    modelSelect: document.getElementById('modelSelect'),
    testModelBtn: document.getElementById('testModelBtn'),
    fileUpload: document.getElementById('fileUpload'),
    uploadBtn: document.getElementById('uploadBtn'),
    documentList: document.getElementById('documentList'),
    chatMessages: document.getElementById('chatMessages'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    loading: document.getElementById('loading'),
    notification: document.getElementById('notification'),
    toggleHistoryBtn: document.getElementById('toggleHistoryBtn'),
    chatHistoryContainer: document.getElementById('chatHistoryContainer'),
    newChatBtn: document.getElementById('newChatBtn'),
    chatSessionsList: document.getElementById('chatSessionsList'),
    chatTitle: document.getElementById('chatTitle'),
    chatSessionInfo: document.getElementById('chatSessionInfo'),
    confirmModal: document.getElementById('confirmModal'),
    modalTitle: document.getElementById('modalTitle'),
    modalMessage: document.getElementById('modalMessage'),
    modalCancelBtn: document.getElementById('modalCancelBtn'),
    modalConfirmBtn: document.getElementById('modalConfirmBtn')
};

// State
let state = {
    currentModel: '',
    currentSessionId: null,
    chatHistoryExpanded: true,
    pendingModalAction: null
};

// Utility Functions
const api = {
    async get(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`);
        return response.json();
    },
    async post(endpoint, data = {}) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return { response, data: await response.json() };
    },
    async delete(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`, { method: 'DELETE' });
        return response.json();
    },
    async upload(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });
        return { response, data: await response.json() };
    }
};

const ui = {
    show: (element) => element.style.display = 'block',
    hide: (element) => element.style.display = 'none',
    toggle: (element) => element.style.display = element.style.display === 'none' ? 'block' : 'none',
    setHtml: (element, html) => element.innerHTML = html,
    addClass: (element, className) => element.classList.add(className),
    removeClass: (element, className) => element.classList.remove(className),
    notify: (message, type = 'success') => {
        elements.notification.textContent = message;
        elements.notification.className = `notification ${type} show`;
        setTimeout(() => elements.notification.classList.remove('show'), 5000);
    },
    setButtonState: (button, disabled, text) => {
        button.disabled = disabled;
        if (text) button.textContent = text;
    },
    createListItem: (content, className = '') => {
        const li = document.createElement('li');
        if (className) li.className = className;
        li.innerHTML = content;
        return li;
    }
};

// Core Functions
async function initialize() {
    try {
        await Promise.all([checkHealth(), loadModels(), loadDocuments(), loadChatHistory()]);
        Object.values(elements).forEach(el => { if (el?.disabled !== undefined) el.disabled = false; });
        ui.notify('Anwendung erfolgreich initialisiert');
    } catch (error) {
        console.error('Initialisierung fehlgeschlagen:', error);
        ui.notify('Fehler beim Initialisieren der Anwendung', 'error');
    }
}

async function checkHealth() {
    const data = await api.get('/api/health');
    const statusClass = data.ollama_available ? 'online' : 'offline';
    const statusText = data.ollama_available ? 'Ollama verbunden' : 'Ollama nicht verfügbar';

    elements.status.className = `status ${statusClass}`;
    ui.setHtml(elements.status, `
        <div class="status-dot"></div>
        <span>${statusText}</span>
        ${data.ollama_available ? `<small style="color: var(--gray-600); margin-left: 10px;">
            ${data.uploaded_files_count} Dateien (${data.uploaded_files_size_mb} MB)
        </small>` : ''}
    `);

    if (!data.ollama_available) throw new Error('Ollama nicht verfügbar');
    state.currentModel = data.current_model || '';
}

async function loadModels() {
    const data = await api.get('/api/models');
    const options = data.models.length > 0
        ? data.models.map(model => `<option value="${model}" ${model === data.current_model ? 'selected' : ''}>${model}</option>`).join('')
        : '<option>Keine Modelle verfügbar</option>';
    ui.setHtml(elements.modelSelect, options);
}

async function loadDocuments() {
    const data = await api.get('/api/documents');
    const items = data.documents.length > 0
        ? data.documents.map(doc => ui.createListItem(`
            <span class="document-name">📄 ${doc}</span>
            <button class="btn btn-danger btn-small" onclick="deleteDocument('${doc}')">🗑️</button>
        `, 'document-item'))
        : [ui.createListItem('Keine Dokumente vorhanden', '', 'color: var(--gray-600); font-size: 14px; font-style: italic;')];

    elements.documentList.innerHTML = '';
    items.forEach(item => elements.documentList.appendChild(item));
}

async function loadChatHistory() {
    try {
        const sessions = await api.get('/api/chat/sessions');
        const items = sessions.length > 0
            ? sessions.map(session => `
                <div class="chat-session-item">
                    <div class="session-content" onclick="loadChatSession('${session.session_id}')">
                        <div class="session-title">${session.title}</div>
                        <div class="session-meta">${session.message_count} Nachrichten • ${formatDate(session.updated_at)}</div>
                    </div>
                    <button class="btn btn-danger btn-tiny" onclick="deleteChatSession('${session.session_id}')" title="Löschen">🗑️</button>
                </div>
            `).join('')
            : '<div class="no-sessions">Keine gespeicherten Chats</div>';

        ui.setHtml(elements.chatSessionsList, items);
    } catch (error) {
        ui.setHtml(elements.chatSessionsList, '<div class="no-sessions">Fehler beim Laden</div>');
    }
}

// Chat Functions
async function loadChatSession(sessionId) {
    try {
        const session = await api.get(`/api/chat/sessions/${sessionId}`);
        ui.setHtml(elements.chatMessages, '');
        session.messages.forEach(msg => addMessage(msg.content, msg.role, msg.sources || []));
        state.currentSessionId = sessionId;
        updateChatHeader(session.title);
        ui.notify('Chat-Session geladen');
    } catch (error) {
        ui.notify('Fehler beim Laden der Chat-Session', 'error');
    }
}

async function createNewChatSession() {
    try {
        const { response, data } = await api.post('/api/chat/sessions');
        if (response.ok) {
            state.currentSessionId = data.session_id;
            await loadChatHistory();
            ui.notify('Neue Chat-Session erstellt');
        }
        clearChat();
        updateChatHeader();
    } catch (error) {
        state.currentSessionId = null;
        clearChat();
        updateChatHeader();
    }
}

async function deleteChatSession(sessionId) {
    const isCurrentSession = sessionId === state.currentSessionId;
    const confirmed = await showConfirmModal('Chat löschen',
        isCurrentSession ? 'Diese Chat-Session ist aktuell aktiv. Wirklich löschen?' : 'Chat-Session wirklich löschen?');

    if (!confirmed) return;

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
    elements.chatTitle.textContent = title ? `💬 ${title}` : '💬 Chat';
    elements.chatSessionInfo.style.display = title ? 'block' : 'none';
    if (title) elements.chatSessionInfo.textContent = 'Gespeicherte Session';
}

async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message) return;

    addMessage(message, 'user');
    elements.messageInput.value = '';
    ui.addClass(elements.loading, 'show');
    ui.setButtonState(elements.sendBtn, true);

    try {
        const requestBody = { message };
        if (state.currentSessionId) requestBody.session_id = state.currentSessionId;

        const { response, data } = await api.post('/api/chat', requestBody);

        if (response.ok && data.success) {
            addMessage(data.response, 'assistant', data.sources);
            if (data.session_id && data.session_id !== state.currentSessionId) {
                state.currentSessionId = data.session_id;
                await loadChatHistory();
            }
        } else {
            addMessage(data.detail || 'Fehler bei der Chat-Anfrage', 'assistant');
        }
    } catch (error) {
        addMessage('Verbindungsfehler zur API', 'assistant');
    } finally {
        ui.removeClass(elements.loading, 'show');
        ui.setButtonState(elements.sendBtn, false);
        elements.messageInput.focus();
    }
}

function addMessage(content, sender, sources = []) {
    const emptyState = elements.chatMessages.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const sourcesHtml = sources.length > 0 ? `<div class="message-sources">📄 Quellen: ${sources.join(', ')}</div>` : '';
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.innerHTML = `<div class="message-content">${content}</div>${sourcesHtml}`;

    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function clearChat() {
    ui.setHtml(elements.chatMessages, `
        <div class="empty-state">
            <h3>Willkommen beim lokalen KI-Chatbot</h3>
            <p>Stelle eine Frage oder lade ein Dokument hoch, um zu beginnen.</p>
        </div>
    `);
}

// Document Functions
async function uploadDocument() {
    const file = elements.fileUpload.files[0];
    if (!file) return ui.notify('Bitte wähle eine Datei aus', 'error');

    ui.setButtonState(elements.uploadBtn, true, 'Lade hoch...');

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
        ui.setButtonState(elements.uploadBtn, false, 'Hochladen');
    }
}

async function deleteDocument(docName) {
    const confirmed = await showConfirmModal('Dokument löschen',
        `Dokument "${docName}" komplett löschen? (Aus Datenbank UND Upload-Ordner)`);
    if (!confirmed) return;

    try {
        await api.delete(`/api/documents/${docName}`);
        ui.notify('Dokument komplett gelöscht');
        await Promise.all([loadDocuments(), checkHealth()]);
    } catch (error) {
        ui.notify('Fehler beim Löschen', 'error');
    }
}

// Model Functions
async function testModel() {
    const model = elements.modelSelect.value;
    if (!model) return;

    ui.setButtonState(elements.testModelBtn, true, 'Teste...');

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
        ui.setButtonState(elements.testModelBtn, false, 'Model testen');
    }
}

// Utility Functions
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

function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        elements.modalTitle.textContent = title;
        elements.modalMessage.textContent = message;
        ui.show(elements.confirmModal);
        state.pendingModalAction = resolve;
    });
}

function closeConfirmModal(confirmed = false) {
    ui.hide(elements.confirmModal);
    if (state.pendingModalAction) {
        state.pendingModalAction(confirmed);
        state.pendingModalAction = null;
    }
}

function toggleChatHistory() {
    state.chatHistoryExpanded = !state.chatHistoryExpanded;
    elements.chatHistoryContainer.style.display = state.chatHistoryExpanded ? 'block' : 'none';
    elements.toggleHistoryBtn.querySelector('.toggle-icon').textContent = state.chatHistoryExpanded ? '▼' : '▶';
}

// Event Listeners
const eventHandlers = {
    'testModelBtn': ['click', testModel],
    'uploadBtn': ['click', uploadDocument],
    'sendBtn': ['click', sendMessage],
    'newChatBtn': ['click', createNewChatSession],
    'toggleHistoryBtn': ['click', toggleChatHistory],
    'modalCancelBtn': ['click', () => closeConfirmModal(false)],
    'modalConfirmBtn': ['click', () => closeConfirmModal(true)],
    'messageInput': ['keypress', (e) => e.key === 'Enter' && !elements.sendBtn.disabled && sendMessage()],
    'modelSelect': ['change', async () => {
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
    }],
    'confirmModal': ['click', (e) => e.target === elements.confirmModal && closeConfirmModal(false)]
};

// Initialize everything
Object.entries(eventHandlers).forEach(([elementId, [event, handler]]) => {
    elements[elementId]?.addEventListener(event, handler);
});

document.addEventListener('DOMContentLoaded', initialize);