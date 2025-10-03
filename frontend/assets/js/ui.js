class UIManager {
    constructor() {
        this.elements = {};
        this.currentSessionId = null;
        this.initializeElements();
        this.setupEventListeners();
    }

    initializeElements() {
        this.elements = {
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendButton: document.getElementById('sendButton'),
            chatForm: document.getElementById('chatForm'),
            loginContainer: document.getElementById('loginContainer'),
            loginForm: document.getElementById('loginForm'),
            authStatus: document.getElementById('authStatus'),
            loginError: document.getElementById('loginError'),
            usernameInput: document.getElementById('username'),
            passwordInput: document.getElementById('password')
        };
    }

    setupEventListeners() {
        // Auto-resize textarea
        this.elements.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        
        // Keyboard shortcuts
        this.elements.messageInput.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
        
        // Form submissions are handled by the main app
    }

    autoResizeTextarea() {
        const textarea = this.elements.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, CONFIG.UI.TEXTAREA_MAX_HEIGHT) + 'px';
    }

    handleKeyboardShortcuts(e) {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            this.elements.chatForm.dispatchEvent(new Event('submit'));
        }
    }

    showLogin() {
        this.elements.loginContainer.classList.remove('hidden');
        this.elements.usernameInput.focus();
    }

    hideLogin() {
        this.elements.loginContainer.classList.add('hidden');
        this.hideLoginError();
        this.clearLoginForm();
    }

    showLoginError(message) {
        this.elements.loginError.textContent = message;
        this.elements.loginError.classList.remove('hidden');
    }

    hideLoginError() {
        this.elements.loginError.classList.add('hidden');
    }

    clearLoginForm() {
        this.elements.usernameInput.value = '';
        this.elements.passwordInput.value = '';
    }

    updateAuthStatus(isConnected, username = null) {
        const statusElement = this.elements.authStatus;
        
        if (isConnected) {
            statusElement.className = 'flex items-center space-x-2 text-green-400';
            statusElement.innerHTML = `
                <div class="w-2 h-2 bg-current rounded-full"></div>
                <span>Connected${username ? ' as ' + username : ''}</span>
            `;
            this.elements.messageInput.disabled = false;
            this.elements.messageInput.placeholder = 'Ask your EU compliance question here... (Press Ctrl+Enter to send)';
            this.elements.sendButton.disabled = false;
        } else {
            statusElement.className = 'flex items-center space-x-2 text-red-400';
            statusElement.innerHTML = `
                <div class="w-2 h-2 bg-current rounded-full"></div>
                <span>Not connected</span>
            `;
            this.elements.messageInput.disabled = true;
            this.elements.messageInput.placeholder = 'Please log in first...';
            this.elements.sendButton.disabled = true;
        }
    }

    // Session management UI methods
    updateSessionInfo(sessionId, messageCount = 0) {
        this.currentSessionId = sessionId;
        
        // Create session info display if it doesn't exist
        let sessionInfo = document.getElementById('sessionInfo');
        if (!sessionInfo) {
            sessionInfo = document.createElement('div');
            sessionInfo.id = 'sessionInfo';
            sessionInfo.className = 'text-xs text-gray-400 p-2 border-b border-gray-600';
            
            // Insert after the chat header
            const chatHeader = document.querySelector('.p-6.border-b.border-gray-600');
            if (chatHeader && chatHeader.parentNode) {
                chatHeader.parentNode.insertBefore(sessionInfo, chatHeader.nextSibling);
            }
        }
        
        const shortSessionId = sessionId === 'new' ? 'New' : sessionId ? sessionId.substring(0, 8) + '...' : 'New';
        sessionInfo.innerHTML = `
            <div class="flex items-center justify-between">
                <span>Session: <span class="text-peach-100">${shortSessionId}</span> | Messages: <span class="text-peach-100">${messageCount}</span></span>
                <div class="flex space-x-2">
                    <button onclick="startNewSession()" class="text-xs text-peach-100 hover:underline px-2 py-1 rounded bg-gray-700 hover:bg-gray-600">New Chat</button>
                    <button onclick="clearCurrentSession()" class="text-xs text-red-400 hover:underline px-2 py-1 rounded bg-gray-700 hover:bg-gray-600">Clear</button>
                </div>
            </div>
        `;
    }

    async loadChatHistory(sessionId) {
        try {
            const historyData = await window.legalAI.apiClient.getChatHistory(sessionId);
            
            // Clear current messages
            this.elements.chatMessages.innerHTML = '';
            
            // Add welcome message if no history
            if (historyData.messages.length === 0) {
                this.addWelcomeMessage();
            } else {
                // Load historical messages
                for (const msg of historyData.messages) {
                    this.addMessage(
                        msg.type === 'human' ? 'user' : 'assistant',
                        msg.content,
                        null,
                        msg.timestamp
                    );
                }
            }
            
            this.updateSessionInfo(sessionId, historyData.total_messages);
            this.showNotification('Chat history loaded', 'success');
            
        } catch (error) {
            console.error('Error loading chat history:', error);
            this.showNotification('Failed to load chat history', 'error');
            this.addWelcomeMessage();
        }
    }

    addWelcomeMessage() {
        this.addMessage('assistant', 
            'Hello! I\'m your COMPLAI Assistant. I specialize in EU regulations, GDPR compliance, CSRD reporting, and regulatory requirements.\n\nI can help you navigate complex compliance questions with detailed guidance backed by regulatory sources.\n\nHow can I assist you with EU compliance today?'
        );
    }

    clearMessageInput() {
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';
    }

    setSendButtonState(enabled, text = null) {
        this.elements.sendButton.disabled = !enabled;
        this.elements.sendButton.textContent = text || (enabled ? 'Send' : 'Sending...');
    }

    focusMessageInput() {
        this.elements.messageInput.focus();
    }

    scrollToBottom(smooth = true) {
        const behavior = smooth ? 'smooth' : 'auto';
        this.elements.chatMessages.scrollTo({
            top: this.elements.chatMessages.scrollHeight,
            behavior: behavior
        });
    }

    addMessage(sender, content, citations = null, timestamp = null, sessionId = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `flex justify-${sender === 'user' ? 'end' : 'start'}`;

        const bubbleClass = sender === 'user' 
            ? 'bg-peach-100 text-dark-900 px-6 py-4 rounded-2xl rounded-br-md max-w-2xl font-medium'
            : 'bg-gray-700 text-white px-6 py-4 rounded-2xl rounded-bl-md max-w-2xl border border-gray-600 shadow-sm';

        let citationsHTML = '';
        if (citations && citations.length > 0) {
            citationsHTML = `
                <div class="mt-4 pt-4 border-t border-gray-600">
                    <div class="text-xs font-medium text-gray-400 mb-2">Sources:</div>
                    ${citations.map(citation => `
                        <div class="bg-gray-600 rounded-lg p-3 mb-2">
                            <div class="text-xs font-medium text-peach-100 break-all">${this.sanitizeHTML(citation.source)}</div>
                            <div class="text-xs text-gray-300 mt-1">${this.sanitizeHTML(citation.snippet)}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        const disclaimerHTML = sender === 'assistant' ? 
            '<div class="text-xs text-gray-400 mt-3 pt-3 border-t border-gray-600"><strong>Compliance Disclaimer:</strong> This information is for educational purposes only and does not constitute legal or compliance advice.</div>' : '';

        messageDiv.innerHTML = `
            <div class="${bubbleClass}">
                <div class="text-sm">${this.formatMessageContent(content)}</div>
                ${citationsHTML}
                ${disclaimerHTML}
            </div>
        `;

        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Update session info if provided
        if (sessionId && sessionId !== this.currentSessionId) {
            this.updateSessionInfo(sessionId);
        }
        
        return messageDiv;
    }

    formatMessageContent(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code class="bg-gray-600 px-1 py-0.5 rounded text-xs">$1</code>')
            .replace(/\n\n/g, '</p><p class="mb-2">')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p class="mb-2">')
            .replace(/$/, '</p>')
            .replace(/<p class="mb-2"><\/p>$/, '');
    }

    addLoadingMessage() {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'flex justify-start';
        loadingDiv.id = 'loading-' + Date.now();

        loadingDiv.innerHTML = `
            <div class="bg-gray-700 text-white px-6 py-4 rounded-2xl rounded-bl-md border border-gray-600 shadow-sm flex items-center space-x-3">
                <span class="text-sm">Thinking...</span>
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-peach-100 rounded-full loading-dot"></div>
                    <div class="w-2 h-2 bg-peach-100 rounded-full loading-dot"></div>
                    <div class="w-2 h-2 bg-peach-100 rounded-full loading-dot"></div>
                </div>
            </div>
        `;

        this.elements.chatMessages.appendChild(loadingDiv);
        this.scrollToBottom();
        return loadingDiv.id;
    }

    removeLoadingMessage(loadingId) {
        const loadingElement = document.getElementById(loadingId);
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    sanitizeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = 'fixed top-4 right-4 p-4 rounded-lg text-white font-medium z-[60] shadow-lg';
        notification.style.animation = 'slideIn 0.3s ease-out';
        
        const colors = {
            info: 'bg-blue-600',
            success: 'bg-green-600',
            warning: 'bg-yellow-600',
            error: 'bg-red-600'
        };
        notification.classList.add(colors[type] || colors.info);
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
}