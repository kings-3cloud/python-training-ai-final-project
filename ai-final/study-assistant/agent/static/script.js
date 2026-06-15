// script.js — handles chat form submission, message rendering, and session reset.

const messageInput = document.getElementById('messageInput');
const sendBtn      = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const resetBtn     = document.getElementById('resetBtn');

// ── Event listeners ──────────────────────────────────────────────────────────

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
resetBtn.addEventListener('click', resetSession);

// Space-bar activation for button accessibility
[sendBtn, resetBtn].forEach(btn => {
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
}
