// API Basis-URL
const API_BASE = 'http://127.0.0.1:8000';

// DOM-Elemente
const statusEl = document.getElementById('status');
const modelSelect = document.getElementById('modelSelect');
const testModelBtn = document.getElementById('testModelBtn');
const fileUpload = document.getElementById('fileUpload');
const uploadBtn = document.getElementById('uploadBtn');
const ocrStatus = document.getElementById('ocrStatus');
const documentList = document.getElementById('documentList');
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const loading = document.getElementById('loading');
const notification = document.getElementById('notification');

// Chat-Verlauf Elemente
const toggleHistoryBtn = document.getElementById('toggleHistoryBtn');
const chatHistoryContainer = document.getElementById('chatHistoryContainer');
const newChatBtn = document.getElementById('newChatBtn');
const chatSessionsList = document.getElementById('chatSessionsList');
const chatTitle = document.getElementById('chatTitle');
const chatSessionInfo = document.getElementById('chatSessionInfo');
const saveChatBtn = document.getElementById('saveChatBtn');

// Modal Elemente
const confirmModal = document.getElementById('confirmModal');
const modalTitle = document.getElementById('modalTitle');
const modalMessage = document.getElementById('modalMessage');
const modalCancelBtn = document.getElementById('modalCancelBtn');
const modalConfirmBtn = document.getElementById('modalConfirmBtn');

// Anwendungszustand
let isInitialized = false;
let currentModel = '';
let currentSessionId = null;
let chatHistoryExpanded = true;
let pendingModalAction = null;

/**
 * Initialisiert die Anwendung
 * Prüft API-Gesundheit, lädt Modelle, Dokumente und Chat-Verlauf
 */
async function initialize() {
    try {
        await checkHealth();
        await loadModels();
        await loadDocuments();
        await loadChatHistory();
        enableInterface();
        isInitialized = true;

        showNotification('Anwendung erfolgreich initialisiert', 'success');
    } catch (error) {
        console.error('Initialisierung fehlgeschlagen:', error);
        showNotification('Fehler beim Initialisieren der Anwendung', 'error');
    }
}

/**
 * Prüft die API-Gesundheit und Ollama-Verfügbarkeit
 */
async function checkHealth() {
    const response = await fetch(`${API_BASE}/api/health`);
    const data = await response.json();

    if (data.ollama_available) {
        statusEl.className = 'status online';
        statusEl.innerHTML = '<div class="status-dot"></div><span>Ollama verbunden</span>';
        currentModel = data.current_model || '';

        // OCR-Status anzeigen
        if (data.features && data.features.ocr_support) {
            ocrStatus.style.display = 'block';
        }
    } else {
        statusEl.className = 'status offline';
        statusEl.innerHTML = '<div class="status-dot"></div><span>Ollama nicht verfügbar</span>';
        throw new Error('Ollama nicht verfügbar');
    }
}

/**
 * Lädt verfügbare Modelle von der API
 */
async function loadModels() {
    const response = await fetch(`${API_BASE}/api/models`);
    const data = await response.json();

    modelSelect.innerHTML = '';

    if (data.models.length > 0) {
        data.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === data.current_model) {
                option.selected = true;
            }
            modelSelect.appendChild(option);
        });
    } else {
        const option = document.createElement('option');
        option.textContent = 'Keine Modelle verfügbar';
        modelSelect.appendChild(option);
    }
}

/**
 * Lädt hochgeladene Dokumente von der API
 */
async function loadDocuments() {
    const response = await fetch(`${API_BASE}/api/documents`);
    const data = await response.json();

    documentList.innerHTML = '';

    if (data.documents.length > 0) {
        data.documents.forEach(doc => {
            const li = document.createElement('li');
            li.className = 'document-item';
            li.innerHTML = `
                <span class="document-name">📄 ${doc}</span>
                <button class="btn btn-danger btn-small" onclick="deleteDocument('${doc}')">🗑️</button>
            `;
            documentList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.style.cssText = 'color: var(--gray-600); font-size: 14px; font-style: italic;';
        li.textContent = 'Keine Dokumente vorhanden';
        documentList.appendChild(li);
    }
}

/**
 * Lädt Chat-Verlauf von der API
 */
async function loadChatHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/chat/sessions`);

        if (!response.ok) {
            // Fallback wenn Chat-History nicht verfügbar
            chatSessionsList.innerHTML = '<div class="no-sessions">Chat-Verlauf nicht verfügbar</div>';
            return;
        }

        const sessions = await response.json();

        chatSessionsList.innerHTML = '';

        if (sessions.length > 0) {
            sessions.forEach(session => {
                const sessionEl = document.createElement('div');
                sessionEl.className = 'chat-session-item';
                sessionEl.innerHTML = `
                    <div class="session-content" onclick="loadChatSession('${session.session_id}')">
                        <div class="session-title">${session.title}</div>
                        <div class="session-meta">
                            ${session.message_count} Nachrichten • 
                            ${formatDate(session.updated_at)}
                        </div>
                    </div>
                    <button class="btn btn-danger btn-tiny" onclick="deleteChatSession('${session.session_id}')" title="Löschen">
                        🗑️
                    </button>
                `;
                chatSessionsList.appendChild(sessionEl);
            });
        } else {
            chatSessionsList.innerHTML = '<div class="no-sessions">Keine gespeicherten Chats</div>';
        }
    } catch (error) {
        console.error('Fehler beim Laden des Chat-Verlaufs:', error);
        chatSessionsList.innerHTML = '<div class="no-sessions">Fehler beim Laden</div>';
    }
}

/**
 * Lädt eine spezifische Chat-Session
 */
async function loadChatSession(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`);

        if (!response.ok) {
            showNotification('Fehler beim Laden der Chat-Session', 'error');
            return;
        }

        const session = await response.json();

        // Chat leeren
        chatMessages.innerHTML = '';

        // Nachrichten laden
        session.messages.forEach(message => {
            addMessage(message.content, message.role, message.sources || []);
        });

        // Session-Info aktualisieren
        currentSessionId = sessionId;
        updateChatHeader(session.title);

        showNotification('Chat-Session geladen', 'success');

    } catch (error) {
        console.error('Fehler beim Laden der Session:', error);
        showNotification('Fehler beim Laden der Chat-Session', 'error');
    }
}

/**
 * Erstellt eine neue Chat-Session
 */
async function createNewChatSession() {
    try {
        const response = await fetch(`${API_BASE}/api/chat/sessions`, {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();
            currentSessionId = data.session_id;
            clearChat();
            updateChatHeader();
            await loadChatHistory();
            showNotification('Neue Chat-Session erstellt', 'success');
        } else {
            // Fallback: Session wird beim ersten Chat erstellt
            currentSessionId = null;
            clearChat();
            updateChatHeader();
        }
    } catch (error) {
        console.error('Fehler beim Erstellen einer neuen Session:', error);
        // Fallback: Lokaler Neustart
        currentSessionId = null;
        clearChat();
        updateChatHeader();
    }
}

/**
 * Löscht eine Chat-Session
 */
async function deleteChatSession(sessionId) {
    const isCurrentSession = sessionId === currentSessionId;
    const message = isCurrentSession
        ? 'Diese Chat-Session ist aktuell aktiv. Wirklich löschen?'
        : 'Chat-Session wirklich löschen?';

    const confirmed = await showConfirmModal('Chat löschen', message);

    if (!confirmed) return;

    try {
        const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            if (isCurrentSession) {
                currentSessionId = null;
                clearChat();
                updateChatHeader();
            }
            await loadChatHistory();
            showNotification('Chat-Session gelöscht', 'success');
        } else {
            const error = await response.json();
            showNotification(error.detail || 'Löschen fehlgeschlagen', 'error');
        }
    } catch (error) {
        console.error('Fehler beim Löschen:', error);
        showNotification('Fehler beim Löschen der Chat-Session', 'error');
    }
}

/**
 * Aktualisiert den Chat-Header
 */
function updateChatHeader(title = null) {
    if (title) {
        chatTitle.textContent = `💬 ${title}`;
        chatSessionInfo.textContent = 'Gespeicherte Session';
        chatSessionInfo.style.display = 'block';
    } else {
        chatTitle.textContent = '💬 Chat';
        chatSessionInfo.style.display = 'none';
    }
}

/**
 * Aktiviert die Benutzeroberfläche nach erfolgreicher Initialisierung
 */
function enableInterface() {
    modelSelect.disabled = false;
    testModelBtn.disabled = false;
    fileUpload.disabled = false;
    uploadBtn.disabled = false;
    messageInput.disabled = false;
    sendBtn.disabled = false;
}

/**
 * Zeigt eine Benachrichtigung an
 * @param {string} message - Die anzuzeigende Nachricht
 * @param {string} type - Der Typ der Benachrichtigung ('success' oder 'error')
 */
function showNotification(message, type = 'success') {
    notification.textContent = message;
    notification.className = `notification ${type} show`;

    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}

/**
 * Zeigt ein Bestätigungs-Modal
 */
function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        confirmModal.style.display = 'flex';

        pendingModalAction = resolve;
    });
}

/**
 * Schließt das Bestätigungs-Modal
 */
function closeConfirmModal(confirmed = false) {
    confirmModal.style.display = 'none';
    if (pendingModalAction) {
        pendingModalAction(confirmed);
        pendingModalAction = null;
    }
}

/**
 * Formatiert ein Datum für die Anzeige
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Gerade eben';
    if (diffMins < 60) return `vor ${diffMins} Min`;
    if (diffHours < 24) return `vor ${diffHours} Std`;
    if (diffDays < 7) return `vor ${diffDays} Tag${diffDays > 1 ? 'en' : ''}`;

    return date.toLocaleDateString('de-DE');
}

/**
 * Testet das aktuell ausgewählte Model
 */
async function testModel() {
    const model = modelSelect.value;
    if (!model) return;

    testModelBtn.disabled = true;
    testModelBtn.textContent = 'Teste...';

    try {
        const response = await fetch(`${API_BASE}/api/models/${model}`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification('Model funktioniert!', 'success');
            currentModel = model;
        } else {
            const error = await response.json();
            showNotification(error.detail || 'Model-Test fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('Fehler beim Testen des Models', 'error');
    } finally {
        testModelBtn.disabled = false;
        testModelBtn.textContent = 'Model testen';
    }
}

/**
 * Lädt ein Dokument hoch
 */
async function uploadDocument() {
    const file = fileUpload.files[0];
    if (!file) {
        showNotification('Bitte wähle eine Datei aus', 'error');
        return;
    }

    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Lade hoch...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            let message = data.message;

            // OCR-Info hinzufügen falls verwendet
            if (data.ocr_used) {
                message += ` (OCR verwendet: ${data.processing_info})`;
            }

            showNotification(message, 'success');
            await loadDocuments();
            fileUpload.value = '';
        } else {
            const error = await response.json();
            showNotification(error.detail || 'Upload fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('Fehler beim Hochladen', 'error');
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Hochladen';
    }
}

/**
 * Löscht ein Dokument
 * @param {string} docName - Name des zu löschenden Dokuments
 */
async function deleteDocument(docName) {
    const confirmed = await showConfirmModal('Dokument löschen', `Dokument "${docName}" wirklich löschen?`);

    if (!confirmed) return;

    try {
        const response = await fetch(`${API_BASE}/api/documents/${docName}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification('Dokument gelöscht', 'success');
            await loadDocuments();
        } else {
            const error = await response.json();
            showNotification(error.detail || 'Löschen fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('Fehler beim Löschen', 'error');
    }
}

/**
 * Sendet eine Chat-Nachricht an die API
 */
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // Benutzer-Nachricht zum Chat hinzufügen
    addMessage(message, 'user');
    messageInput.value = '';

    // Lade-Indikator anzeigen
    loading.classList.add('show');
    sendBtn.disabled = true;

    try {
        const requestBody = { message };
        if (currentSessionId) {
            requestBody.session_id = currentSessionId;
        }

        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            addMessage(data.response, 'assistant', data.sources);

            // Session-ID aktualisieren
            if (data.session_id && data.session_id !== currentSessionId) {
                currentSessionId = data.session_id;
                await loadChatHistory(); // Chat-Verlauf aktualisieren
            }
        } else {
            addMessage(data.detail || 'Fehler bei der Chat-Anfrage', 'assistant');
        }
    } catch (error) {
        addMessage('Verbindungsfehler zur API', 'assistant');
    } finally {
        loading.classList.remove('show');
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

/**
 * Fügt eine Nachricht zum Chat hinzu
 * @param {string} content - Nachrichteninhalt
 * @param {string} sender - 'user' oder 'assistant'
 * @param {Array} sources - Optional: Array von Quellenangaben
 */
function addMessage(content, sender, sources = []) {
    // Leeren Zustand entfernen falls vorhanden
    const emptyState = chatMessages.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `<div class="message-sources">📄 Quellen: ${sources.join(', ')}</div>`;
    }

    messageDiv.innerHTML = `
        <div class="message-content">${content}</div>
        ${sourcesHtml}
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Löscht alle Chat-Nachrichten
 */
function clearChat() {
    chatMessages.innerHTML = `
        <div class="empty-state">
            <h3>Willkommen beim lokalen KI-Chatbot</h3>
            <p>Stelle eine Frage oder lade ein Dokument hoch, um zu beginnen.</p>
            <p class="features-hint">
                <span class="feature-icon">💾</span> Deine letzten 5 Chats werden automatisch gespeichert<br>
                <span class="feature-icon">📄</span> OCR erkennt Text in eingescannten PDFs automatisch
            </p>
        </div>
    `;
}

/**
 * Wechselt die Sichtbarkeit des Chat-Verlaufs
 */
function toggleChatHistory() {
    chatHistoryExpanded = !chatHistoryExpanded;

    if (chatHistoryExpanded) {
        chatHistoryContainer.style.display = 'block';
        toggleHistoryBtn.querySelector('.toggle-icon').textContent = '▼';
    } else {
        chatHistoryContainer.style.display = 'none';
        toggleHistoryBtn.querySelector('.toggle-icon').textContent = '▶';
    }
}

// Event-Listener
testModelBtn.addEventListener('click', testModel);
uploadBtn.addEventListener('click', uploadDocument);
sendBtn.addEventListener('click', sendMessage);
newChatBtn.addEventListener('click', createNewChatSession);
toggleHistoryBtn.addEventListener('click', toggleChatHistory);

// Modal Event-Listener
modalCancelBtn.addEventListener('click', () => closeConfirmModal(false));
modalConfirmBtn.addEventListener('click', () => closeConfirmModal(true));

// Modal außerhalb klicken schließt es
confirmModal.addEventListener('click', (e) => {
    if (e.target === confirmModal) {
        closeConfirmModal(false);
    }
});

// Model-Auswahl Änderung
modelSelect.addEventListener('change', async () => {
    const selectedModel = modelSelect.value;
    if (selectedModel && selectedModel !== currentModel) {
        try {
            const response = await fetch(`${API_BASE}/api/models/${selectedModel}`, {
                method: 'POST'
            });

            if (response.ok) {
                currentModel = selectedModel;
                showNotification(`Model zu ${selectedModel} gewechselt`, 'success');
            } else {
                const error = await response.json();
                showNotification(error.detail || 'Model-Wechsel fehlgeschlagen', 'error');
                // Auswahl zurücksetzen
                modelSelect.value = currentModel;
            }
        } catch (error) {
            showNotification('Fehler beim Wechseln des Models', 'error');
            modelSelect.value = currentModel;
        }
    }
});

// Enter-Taste zum Senden von Nachrichten
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !sendBtn.disabled) {
        sendMessage();
    }
});

// Datei-Upload Änderung
fileUpload.addEventListener('change', () => {
    if (fileUpload.files[0]) {
        uploadBtn.textContent = 'Hochladen';
    }
});

// Anwendung initialisieren wenn Seite geladen ist
document.addEventListener('DOMContentLoaded', initialize);