class AuthManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.currentUser = null;
        this.isAuthenticated = false;
        this.onAuthChange = [];
    }

    addAuthChangeListener(callback) {
        this.onAuthChange.push(callback);
    }

    removeAuthChangeListener(callback) {
        this.onAuthChange = this.onAuthChange.filter(cb => cb !== callback);
    }

    notifyAuthChange(isAuthenticated, user = null) {
        this.isAuthenticated = isAuthenticated;
        this.currentUser = user;
        this.onAuthChange.forEach(callback => callback(isAuthenticated, user));
    }

    async login(username, password) {
        try {
            const result = await this.api.login(username, password);
            this.api.setToken(result.access_token);
            
            // Get user info
            const user = await this.api.getCurrentUser();
            
            // Store user data
            localStorage.setItem(CONFIG.STORAGE_KEYS.USER_DATA, JSON.stringify(user));
            
            this.notifyAuthChange(true, user);
            return { success: true, user };
        } catch (error) {
            console.error('Login failed:', error);
            return { success: false, error: error.message };
        }
    }

    async checkAuthentication() {
        const token = localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
        
        if (!token) {
            this.notifyAuthChange(false);
            return false;
        }

        try {
            const user = await this.api.getCurrentUser();
            this.notifyAuthChange(true, user);
            return true;
        } catch (error) {
            if (error.isAuthError()) {
                this.logout();
            }
            return false;
        }
    }

    logout() {
        this.api.setToken(null);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.USER_DATA);
        this.notifyAuthChange(false);
    }

    getCurrentUser() {
        return this.currentUser;
    }

    isLoggedIn() {
        return this.isAuthenticated;
    }
}
