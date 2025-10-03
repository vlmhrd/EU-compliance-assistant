const CONFIG = {
    API_BASE: 'http://localhost:8000',
    ENDPOINTS: {
        LOGIN: '/auth/login',      
        ME: '/auth/me',           
        CHAT: '/v1/chat',
        SEARCH: '/v1/search',
        CHAT_HISTORY: '/v1/chat/history',      // Add this
        CLEAR_SESSION: '/v1/chat/session',     // Add this
        USER_SESSIONS: '/v1/chat/sessions'     // Add this
    },
    STORAGE_KEYS: {
        AUTH_TOKEN: 'legal_ai_token',
        USER_DATA: 'legal_ai_user',
        CURRENT_SESSION: 'current_session_id'  // Add this
    },
    UI: {
        MAX_MESSAGE_LENGTH: 10000,
        TEXTAREA_MAX_HEIGHT: 120,
        AUTO_SCROLL_THRESHOLD: 100
    }
};