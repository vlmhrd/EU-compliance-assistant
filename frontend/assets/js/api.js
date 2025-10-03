// Updated APIClient class with session management
class APIClient {
    constructor() {
        this.baseURL = CONFIG.API_BASE;
        this.token = localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
        this.currentSessionId = localStorage.getItem(CONFIG.STORAGE_KEYS.CURRENT_SESSION) || null;
    }

    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN, token);
        } else {
            localStorage.removeItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
        }
    }

    // Session management methods
    getCurrentSession() {
        return this.currentSessionId;
    }

    setCurrentSession(sessionId) {
        this.currentSessionId = sessionId;
        if (sessionId) {
            localStorage.setItem(CONFIG.STORAGE_KEYS.CURRENT_SESSION, sessionId);
        } else {
            localStorage.removeItem(CONFIG.STORAGE_KEYS.CURRENT_SESSION);
        }
    }

    getAuthHeaders() {
        return {
            'Content-Type': 'application/json',
            ...(this.token && { 'Authorization': `Bearer ${this.token}` })
        };
    }

    async makeRequest(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.getAuthHeaders(),
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new APIError(response.status, data.detail || 'Request failed', data);
            }

            return { data, status: response.status };
        } catch (error) {
            if (error instanceof APIError) throw error;
            throw new APIError(0, 'Network error', { originalError: error.message });
        }
    }

    async login(username, password) {
        const response = await this.makeRequest(CONFIG.ENDPOINTS.LOGIN, {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        return response.data;
    }

    async getCurrentUser() {
        const response = await this.makeRequest(CONFIG.ENDPOINTS.ME);
        return response.data;
    }

    async sendMessage(message, sessionId = null) {
        // Use provided sessionId or current session
        const useSessionId = sessionId || this.currentSessionId;
        
        // Build URL with session_id parameter if we have one
        const endpoint = useSessionId 
            ? `${CONFIG.ENDPOINTS.CHAT}?session_id=${encodeURIComponent(useSessionId)}`
            : CONFIG.ENDPOINTS.CHAT;
        
        console.log('Sending message with session:', useSessionId);
        
        const response = await this.makeRequest(endpoint, {
            method: 'POST',
            body: JSON.stringify({
                user_id: 'user',
                query: message
            })
        });
        
        // Store session_id from response for future requests
        if (response.data.session_id) {
            this.setCurrentSession(response.data.session_id);
            console.log('Updated session ID:', response.data.session_id);
        }
        
        return response.data;
    }

    async clearSession(sessionId) {
        const response = await this.makeRequest(`${CONFIG.ENDPOINTS.CLEAR_SESSION}/${sessionId}`, {
            method: 'DELETE'
        });
        return response.data;
    }

    async getChatHistory(sessionId) {
        const response = await this.makeRequest(`${CONFIG.ENDPOINTS.CHAT_HISTORY}/${sessionId}`);
        return response.data;
    }

    async getUserSessions() {
        const response = await this.makeRequest(CONFIG.ENDPOINTS.USER_SESSIONS);
        return response.data;
    }
}

// Updated UIManager class with session info display
class UIManager {
    constructor() {
        this.elements = {};
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
        this.elements.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        this.elements.messageInput.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
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
        const loginNavButton = document.getElementById('loginNavButton');
        const logoutNavButton = document.getElementById('logoutNavButton');
        const chatNavButton = document.getElementById('chatNavButton');
        const sidebarLogoutButton = document.getElementById('sidebarLogoutButton');
        
        if (isConnected) {
            statusElement.className = 'flex items-center space-x-2 text-green-400';
            statusElement.innerHTML = `
                <div class="w-2 h-2 bg-current rounded-full"></div>
                <span>Connected${username ? ' as ' + username : ''}</span>
            `;
            
            // Update navigation buttons
            if (loginNavButton) loginNavButton.classList.add('hidden');
            if (logoutNavButton) logoutNavButton.classList.remove('hidden');
            if (chatNavButton) chatNavButton.classList.remove('hidden');
            if (sidebarLogoutButton) sidebarLogoutButton.classList.remove('hidden');
            
            // Enable chat input
            this.elements.messageInput.disabled = false;
            this.elements.messageInput.placeholder = 'Ask your EU compliance question here... (Press Ctrl+Enter to send)';
            this.elements.sendButton.disabled = false;
        } else {
            statusElement.className = 'flex items-center space-x-2 text-red-400';
            statusElement.innerHTML = `
                <div class="w-2 h-2 bg-current rounded-full"></div>
                <span>Not connected</span>
            `;
            
            // Update navigation buttons
            if (loginNavButton) loginNavButton.classList.remove('hidden');
            if (logoutNavButton) logoutNavButton.classList.add('hidden');
            if (chatNavButton) chatNavButton.classList.add('hidden');
            if (sidebarLogoutButton) sidebarLogoutButton.classList.add('hidden');
            
            // Disable chat input
            this.elements.messageInput.disabled = true;
            this.elements.messageInput.placeholder = 'Please log in first...';
            this.elements.sendButton.disabled = true;
        }
    }

    updateSessionInfo(sessionId, messageCount = 0) {
        // Add session info display to the chat header
        const chatHeader = document.querySelector('#mainChatContainer .p-6.border-b.border-gray-600');
        if (chatHeader) {
            let sessionInfo = chatHeader.querySelector('.session-info');
            if (!sessionInfo) {
                sessionInfo = document.createElement('div');
                sessionInfo.className = 'session-info text-xs text-gray-400 mt-1';
                chatHeader.appendChild(sessionInfo);
            }
            
            if (sessionId && sessionId !== 'new') {
                sessionInfo.textContent = `Session: ${sessionId.substring(0, 8)}... | Messages: ${messageCount}`;
            } else {
                sessionInfo.textContent = 'New conversation';
            }
        }
    }

    addWelcomeMessage() {
        this.elements.chatMessages.innerHTML = `
            <div class="flex justify-start">
                <div class="bg-gray-700 text-white px-6 py-4 rounded-2xl rounded-bl-md max-w-2xl border border-gray-600 shadow-sm">
                    <p class="mb-2">Hello! I'm your compl.ai Assistant. I specialize in EU regulations, GDPR compliance, CSRD reporting, and regulatory requirements.</p>
                    <p class="mb-2">I can help you navigate complex compliance questions with detailed guidance backed by regulatory sources.</p>
                    <p class="font-medium">How can I assist you with EU compliance today?</p>
                </div>
            </div>
        `;
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

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
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

        // Add session info for assistant messages
        let sessionInfo = '';
        if (sender === 'assistant' && sessionId) {
            sessionInfo = `<div class="text-xs text-gray-400 mt-2">Session: ${sessionId.substring(0, 8)}...</div>`;
        }

        messageDiv.innerHTML = `
            <div class="${bubbleClass}">
                <div class="text-sm">${this.formatMessageContent(content)}</div>
                ${citationsHTML}
                ${sessionInfo}
            </div>
        `;

        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        
        // Update session info in header
        if (sessionId) {
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

    async loadChatHistory(sessionId) {
        // This would load chat history from the server
        // For now, just update session info
        this.updateSessionInfo(sessionId);
        this.showNotification(`Loaded session ${sessionId.substring(0, 8)}...`, 'info');
    }
}

// Updated LegalAIChat class
class LegalAIChat {
    constructor() {
        this.apiClient = new APIClient();
        this.authManager = new AuthManager(this.apiClient);
        this.ui = new UIManager();
        
        this.initialize();
    }

    initialize() {
        this.setupEventListeners();
        this.setupAuthListeners();
        this.checkInitialAuth();
    }

    setupEventListeners() {
        // Chat form submission
        this.ui.elements.chatForm.addEventListener('submit', (e) => this.handleSendMessage(e));
        
        // Login form submission
        this.ui.elements.loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        
        // Add logout functionality (Ctrl+Shift+L)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'L') {
                this.handleLogout();
            }
        });
    }

    setupAuthListeners() {
        this.authManager.addAuthChangeListener((isAuthenticated, user) => {
            if (isAuthenticated) {
                this.ui.hideLogin();
                this.ui.updateAuthStatus(true, user?.username);
                this.ui.focusMessageInput();
                
                // Load existing session if available
                const currentSession = this.apiClient.getCurrentSession();
                if (currentSession) {
                    this.ui.updateSessionInfo(currentSession);
                    console.log('Restored session:', currentSession);
                } else {
                    // Start with welcome message for new sessions
                    this.ui.addWelcomeMessage();
                    this.ui.updateSessionInfo('new', 0);
                }
            } else {
                this.ui.showLogin();
                this.ui.updateAuthStatus(false);
            }
        });
    }

    async checkInitialAuth() {
        const isAuthenticated = await this.authManager.checkAuthentication();
        
        if (isAuthenticated) {
            this.ui.showNotification('Welcome back!', 'success');
        }
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const username = this.ui.elements.usernameInput.value.trim();
        const password = this.ui.elements.passwordInput.value;
        
        if (!username || !password) {
            this.ui.showLoginError('Please enter both username and password');
            return;
        }

        try {
            const result = await this.authManager.login(username, password);
            
            if (result.success) {
                this.ui.showNotification(`Welcome, ${result.user.username}!`, 'success');
            } else {
                this.ui.showLoginError(result.error);
            }
        } catch (error) {
            console.error('Login error:', error);
            this.ui.showLoginError('An unexpected error occurred');
        }
    }

    handleLogout() {
        this.authManager.logout();
        this.apiClient.setCurrentSession(null); // Clear current session
        this.ui.updateSessionInfo(null, 0);
        this.ui.showNotification('Logged out successfully', 'info');
    }

    async handleSendMessage(e) {
        e.preventDefault();
        
        if (!this.authManager.isLoggedIn()) {
            this.ui.showLogin();
            return;
        }

        const message = this.ui.elements.messageInput.value.trim();
        if (!message) return;

        if (message.length > CONFIG.UI.MAX_MESSAGE_LENGTH) {
            this.ui.showNotification(`Message too long (max ${CONFIG.UI.MAX_MESSAGE_LENGTH} characters)`, 'warning');
            return;
        }

        // Clear input and disable send button
        this.ui.clearMessageInput();
        this.ui.setSendButtonState(false);

        // Add user message
        this.ui.addMessage('user', message);

        // Add loading indicator
        const loadingId = this.ui.addLoadingMessage();

        try {
            // Send message with current session (if any)
            const response = await this.apiClient.sendMessage(message);
            
            this.ui.removeLoadingMessage(loadingId);
            this.ui.addMessage('assistant', response.answer, response.citations, response.timestamp, response.session_id);
            
            // Show session info
            if (response.session_id) {
                console.log('Message sent in session:', response.session_id);
                this.ui.updateSessionInfo(response.session_id);
            }
            
        } catch (error) {
            this.ui.removeLoadingMessage(loadingId);
            
            if (error.isAuthError()) {
                this.authManager.logout();
                this.ui.addMessage('assistant', 'Your session has expired. Please log in again.');
            } else if (error.isServerError()) {
                this.ui.addMessage('assistant', 'I\'m experiencing technical difficulties. Please try again later.');
            } else {
                this.ui.addMessage('assistant', `I apologize, but I encountered an error: ${error.message}`);
            }
            
            console.error('Send message error:', error);
        } finally {
            this.ui.setSendButtonState(true);
            this.ui.focusMessageInput();
        }
    }

    // Session management methods
    async startNewSession() {
        try {
            // Clear current session
            this.apiClient.setCurrentSession(null);
            
            // Clear chat messages
            this.ui.elements.chatMessages.innerHTML = '';
            
            // Add welcome message
            this.ui.addWelcomeMessage();
            
            // Update UI
            this.ui.updateSessionInfo('new', 0);
            this.ui.showNotification('New chat session started', 'success');
            this.ui.focusMessageInput();
            
        } catch (error) {
            console.error('Error starting new session:', error);
            this.ui.showNotification('Failed to start new session', 'error');
        }
    }

    async clearCurrentSession() {
        const currentSession = this.apiClient.getCurrentSession();
        if (!currentSession || currentSession === 'new') {
            // If no session or already new, just clear the chat
            this.startNewSession();
            return;
        }

        try {
            // Clear session on server
            await this.apiClient.clearSession(currentSession);
            
            // Start fresh session
            this.startNewSession();
            this.ui.showNotification('Chat session cleared', 'success');
            
        } catch (error) {
            console.error('Error clearing session:', error);
            // Still clear locally even if server call fails
            this.startNewSession();
            this.ui.showNotification('Session cleared locally (server error)', 'warning');
        }
    }

    async loadSessionHistory(sessionId) {
        try {
            await this.ui.loadChatHistory(sessionId);
            this.apiClient.setCurrentSession(sessionId);
        } catch (error) {
            console.error('Error loading session history:', error);
            this.ui.showNotification('Failed to load session history', 'error');
        }
    }

    // Public methods for external access
    sendMessage(message) {
        if (this.authManager.isLoggedIn()) {
            this.ui.elements.messageInput.value = message;
            this.ui.elements.chatForm.dispatchEvent(new Event('submit'));
        } else {
            this.ui.showLogin();
        }
    }

    clearChat() {
        this.startNewSession();
    }

    getCurrentSessionInfo() {
        return {
            sessionId: this.apiClient.getCurrentSession(),
            isAuthenticated: this.authManager.isLoggedIn(),
            user: this.authManager.getCurrentUser()
        };
    }
}