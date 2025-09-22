// API Basis-URL
const API_BASE = '';

// DOM-Elemente
const statusEl = document.getElementById('status');
const modelSelect = document.getElementById('modelSelect');
const testModelBtn = document.getElementById('testModelBtn');
const fileUpload = document.getElementById('fileUpload');
const uploadBtn = document.getElementById('uploadBtn');
const documentList = document.getElementById('documentList');
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearChatBtn = document.getElementById('clearChatBtn');
const loading = document.getElementById('loading');
const notification = document.getElementById('notification');

// Anwendungszustand
let isInitialized = false;
let currentModel = '';

/**
 * Initialisiert die Anwendung
 * Prüft API-Gesundheit, lädt Modelle und Dokumente
 */
async function initialize() {
    try {
        await checkHealth();
        await loadModels();
        await loadDocuments();
        enableInterface();
        isInitialized = true;
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
        statusEl.innerHTML = '<div class="status-dot"></div><span>✅ Ollama verbunden</span>';
        currentModel = data.current_model || '';
    } else {
        statusEl.className = 'status offline';
        statusEl.innerHTML = '<div class="status-dot"></div><span>❌ Ollama nicht verfügbar</span>';
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
    }, 3000);
}

/**
 * Testet das aktuell ausgewählte Model
 */
async function testModel() {
    const model = modelSelect.value;
    if (!model) return;

    testModelBtn.disabled = true;
    testModelBtn.textContent = '🧪 Teste...';

    try {
        const response = await fetch(`${API_BASE}/api/models/${model}`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification('✅ Model funktioniert!', 'success');
            currentModel = model;
        } else {
            const error = await response.json();
            showNotification(error.detail || '❌ Model-Test fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('❌ Fehler beim Testen des Models', 'error');
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
        showNotification('⚠️ Bitte wähle eine Datei aus', 'error');
        return;
    }

    uploadBtn.disabled = true;
    uploadBtn.textContent = '📤 Lade hoch...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            showNotification(`✅ ${data.message}`, 'success');
            await loadDocuments();
            fileUpload.value = '';
        } else {
            const error = await response.json();
            showNotification(error.detail || '❌ Upload fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('❌ Fehler beim Hochladen', 'error');
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
    if (!confirm(`Dokument "${docName}" wirklich löschen?`)) return;

    try {
        const response = await fetch(`${API_BASE}/api/documents/${docName}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification('✅ Dokument gelöscht', 'success');
            await loadDocuments();
        } else {
            const error = await response.json();
            showNotification(error.detail || '❌ Löschen fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('❌ Fehler beim Löschen', 'error');
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
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            addMessage(data.response, 'assistant', data.sources);
        } else {
            addMessage(data.detail || '❌ Fehler bei der Chat-Anfrage', 'assistant');
        }
    } catch (error) {
        addMessage('❌ Verbindungsfehler zur API', 'assistant');
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
        </div>
    `;
}

// Event-Listener
testModelBtn.addEventListener('click', testModel);
uploadBtn.addEventListener('click', uploadDocument);
sendBtn.addEventListener('click', sendMessage);
clearChatBtn.addEventListener('click', clearChat);

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
                showNotification(`✅ Model zu ${selectedModel} gewechselt`, 'success');
            } else {
                const error = await response.json();
                showNotification(error.detail || '❌ Model-Wechsel fehlgeschlagen', 'error');
                // Auswahl zurücksetzen
                modelSelect.value = currentModel;
            }
        } catch (error) {
            showNotification('❌ Fehler beim Wechseln des Models', 'error');
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
        uploadBtn.textContent = '📤 Hochladen';
    }
});

// Anwendung initialisieren wenn Seite geladen ist
document.addEventListener('DOMContentLoaded', initialize);