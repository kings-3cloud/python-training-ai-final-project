// script.js — handles chat form submission, PDF upload, message rendering, session reset, and mode switching.

const messageInput   = document.getElementById('messageInput');
const sendBtn        = document.getElementById('sendBtn');
const chatMessages   = document.getElementById('chatMessages');
const resetBtn       = document.getElementById('resetBtn');
const uploadBtn      = document.getElementById('uploadBtn');
const pdfInput       = document.getElementById('pdfInput');
const modeOnlineBtn  = document.getElementById('modeOnlineBtn');
const modeOfflineBtn = document.getElementById('modeOfflineBtn');

// ── Event listeners ──────────────────────────────────────────────────────────

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
resetBtn.addEventListener('click', resetSession);

// Mode toggle buttons
[modeOnlineBtn, modeOfflineBtn].forEach(btn => {
    btn.addEventListener('click', () => switchMode(btn.dataset.mode));
});

// Sync toggle state with server on load
fetch('/mode')
    .then(r => r.json())
    .then(data => applyModeUI(data.mode))
    .catch(() => {});

// Upload button opens the hidden file picker
uploadBtn.addEventListener('click', () => pdfInput.click());
pdfInput.addEventListener('change', () => {
    if (pdfInput.files.length > 0) uploadPdf(pdfInput.files[0]);
});

// Space-bar activation for button accessibility
[sendBtn, resetBtn, uploadBtn].forEach(btn => {
    btn.addEventListener('keydown', (e) => {
        if (e.key === ' ' || e.key === 'Spacebar') {
            e.preventDefault();
            btn.click();
        }
    });
});

// ── Core functions ───────────────────────────────────────────────────────────

function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // Remove welcome message on first send
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    addMessage(message, 'user');
    messageInput.value = '';
    setInputDisabled(true);

    const typingIndicator = addTypingIndicator();

    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    })
        .then(r => r.json())
        .then(data => {
            typingIndicator.remove();
            if (data.error) {
                addMessage(`Error: ${data.error}`, 'agent');
            } else if (data.response_html) {
                addMessage(data.response_html, 'agent', { isHtml: true });
            } else {
                addMessage(data.response, 'agent');
            }
            setInputDisabled(false);
            messageInput.focus();
        })
        .catch(err => {
            typingIndicator.remove();
            addMessage(`Error: ${err.message}`, 'agent');
            setInputDisabled(false);
            messageInput.focus();
        });
}

function switchMode(newMode) {
    setInputDisabled(true);
    fetch('/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
    })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                addMessage(`Could not switch mode: ${data.error}`, 'agent');
            } else {
                applyModeUI(data.mode);
                if (data.changed) {
                    const label = data.mode === 'online' ? '☁️ Online (Foundry)' : '💻 Offline (local model)';
                    addMessage(`Switched to ${label} mode. Conversation history has been reset.`, 'agent');
                    // Reset history on the server too
                    fetch('/reset', { method: 'POST' }).catch(() => {});
                }
            }
            setInputDisabled(false);
            messageInput.focus();
        })
        .catch(err => {
            addMessage(`Error switching mode: ${err.message}`, 'agent');
            setInputDisabled(false);
        });
}

function applyModeUI(mode) {
    const isOnline = mode === 'online';
    modeOnlineBtn.classList.toggle('active', isOnline);
    modeOfflineBtn.classList.toggle('active', !isOnline);
    modeOnlineBtn.setAttribute('aria-pressed', String(isOnline));
    modeOfflineBtn.setAttribute('aria-pressed', String(!isOnline));
}

function uploadPdf(file) {
    const welcome = document.querySelector('.welcome-message');
    if (welcome) welcome.remove();

    // Show the filename as a user message
    addMessage(`📎 ${file.name}`, 'user');
    setInputDisabled(true);

    const typingIndicator = addTypingIndicator();
    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            typingIndicator.remove();
            if (data.error) {
                addMessage(`Error: ${data.error}`, 'agent');
                setInputDisabled(false);
                messageInput.focus();
                return;
            }
            // Feed the extracted content into the agent conversation
            const truncationNote = data.truncated
                ? ' (truncated to 4 000 characters)'
                : '';
            const agentMessage =
                `I've uploaded "${data.filename}"${truncationNote}. ` +
                `Here is its content:\n\n${data.content}\n\n` +
                `What would you like to do with this? I can generate a quiz, summarise it, or help you study it.`;

            return fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: agentMessage })
            })
                .then(r => r.json())
                .then(chatData => {
                    if (chatData.error) {
                        addMessage(`Error: ${chatData.error}`, 'agent');
                    } else if (chatData.response_html) {
                        addMessage(chatData.response_html, 'agent', { isHtml: true });
                    } else {
                        addMessage(chatData.response, 'agent');
                    }
                    setInputDisabled(false);
                    messageInput.focus();
                });
        })
        .catch(err => {
            typingIndicator.remove();
            addMessage(`Error: ${err.message}`, 'agent');
            setInputDisabled(false);
            messageInput.focus();
        })
        .finally(() => {
            // Reset file input so the same file can be re-uploaded if needed
            pdfInput.value = '';
        });
}

function resetSession() {
    fetch('/reset', { method: 'POST' })
        .then(() => {
            chatMessages.innerHTML = '';
            const welcome = document.createElement('div');
            welcome.className = 'welcome-message';
            welcome.setAttribute('role', 'status');
            welcome.textContent = 'Session reset. Ask me to fetch a URL, generate a quiz, or review your progress!';
            chatMessages.appendChild(welcome);
            messageInput.focus();
        })
        .catch(err => console.error('Reset failed:', err));
}

// ── UI helpers ───────────────────────────────────────────────────────────────

function addMessage(text, sender, options = {}) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.setAttribute('role', 'article');
    messageDiv.setAttribute('aria-label', `${sender === 'user' ? 'User' : 'Agent'} message`);

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = sender === 'user' ? '🧑' : '📚';

    const content = document.createElement('div');
    content.className = 'message-content';

    if (options.isHtml) {
        // Server has already sanitised the HTML via bleach; trust it.
        content.innerHTML = text;
    } else {
        content.textContent = text;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
}

function addTypingIndicator() {
    const wrapper = document.createElement('div');
    wrapper.className = 'message agent';
    wrapper.setAttribute('aria-label', 'Agent is typing');
    wrapper.setAttribute('aria-live', 'polite');

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = '📚';

    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';

    wrapper.appendChild(avatar);
    wrapper.appendChild(indicator);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return wrapper;
}

function setInputDisabled(disabled) {
    messageInput.disabled = disabled;
    sendBtn.disabled = disabled;
    uploadBtn.disabled = disabled;
}
