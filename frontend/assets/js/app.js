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
                    this.ui.loadChatHistory(currentSession);
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
            const currentSession = this.apiClient.getCurrentSession();
            const response = await this.apiClient.sendMessage(message, null, currentSession);
            
            this.ui.removeLoadingMessage(loadingId);
            this.ui.addMessage('assistant', response.answer, response.citations, response.timestamp, response.session_id);
            
            // Update session info if we got a session ID
            if (response.session_id) {
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

// Global functions for HTML onclick handlers
function openMainChat() {
    document.getElementById('mainChatContainer').classList.remove('hidden');
    if (window.legalAI && !window.legalAI.authManager.isLoggedIn()) {
        window.legalAI.ui.showLogin();
    }
}

function closeMainChat() {
    document.getElementById('mainChatContainer').classList.add('hidden');
    document.getElementById('loginContainer').classList.add('hidden');
}

function sendSampleQuery(query) {
    if (window.legalAI) {
        window.legalAI.sendMessage(query);
    }
}

function startNewSession() {
    if (window.legalAI) {
        window.legalAI.startNewSession();
    }
}

function clearCurrentSession() {
    if (window.legalAI) {
        window.legalAI.clearCurrentSession();
    }
}

// Initialize when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    // Add CSS animations for loading dots
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        .loading-dot {
            animation: bounce 1.4s ease-in-out infinite both;
        }
        
        .loading-dot:nth-child(1) { animation-delay: -0.32s; }
        .loading-dot:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
    `;
    document.head.appendChild(style);
    
    // Initialize the app
    window.legalAI = new LegalAIChat();
});