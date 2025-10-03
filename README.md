# compl.ai - EU Compliance AI Assistant

A professional AI-powered application that provides instant guidance on EU regulations, GDPR compliance, CSRD reporting, and other regulatory requirements. Built with FastAPI backend and vanilla JavaScript frontend, featuring real-time streaming responses and comprehensive observability through LangSmith.

## 🎯 What Does This Application Do?

**compl.ai** is an intelligent compliance assistant that helps businesses and professionals navigate complex EU regulations through natural language conversations. The system combines:

- **AI-Powered Responses**: Uses Amazon Bedrock's Nova Pro model for accurate, context-aware answers
- **Knowledge Base Integration**: Retrieves and cites relevant regulatory documents from AWS Bedrock Knowledge Base
- **Session Management**: Maintains conversation context across multiple interactions
- **Real-time Streaming**: Provides responsive, token-by-token streaming responses
- **Observability**: Full request tracing through LangSmith for monitoring and debugging

## 🏗️ Architecture Overview

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│                 │      │                  │      │                 │
│  Frontend       │─────▶│  FastAPI Backend │─────▶│  AWS Bedrock    │
│  (Vanilla JS)   │◀─────│  (Python)        │◀─────│  (Nova Pro)     │
│                 │      │                  │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                 │
                                 │
                         ┌───────┴────────┐
                         │                │
                         │   LangSmith    │
                         │   (Tracing)    │
                         │                │
                         └────────────────┘
```

## ✨ Key Features

### Backend Features

#### 1. **LLM Integration**
- Amazon Bedrock Nova Pro with regional inference profiles
- Streaming and non-streaming response modes
- Temperature and token control for response quality
- Automatic model selection based on AWS region

#### 2. **Knowledge Base (RAG)**
- AWS Bedrock Knowledge Base integration for document retrieval
- Vector search with configurable result counts
- Citation tracking with source documents
- Mock KB mode for development without AWS resources

#### 3. **Memory Management**
- LangChain-based conversation memory
- Buffer window memory (configurable history length)
- Session persistence with automatic cleanup
- Multi-user session isolation

#### 4. **Session Management**
- Unique session IDs for conversation continuity
- Session metadata tracking (user, timestamps, message counts)
- Automatic session expiration (2 hours idle)
- Session limit enforcement (1000 max sessions)

#### 5. **Observability with LangSmith**
- Complete request tracing from endpoint to LLM
- Traces for memory operations (session creation, message storage)
- KB retrieval and parsing traces
- Hierarchical trace visualization showing parent-child relationships
- Performance metrics and timing information

#### 6. **Security & Authentication**
- JWT-based authentication
- Token expiration handling
- User authorization for session access
- Environment-based configuration

#### 7. **API Endpoints**
- `POST /auth/login` - User authentication
- `GET /auth/me` - Current user information
- `POST /v1/chat` - Chat with optional streaming
- `POST /v1/search` - Direct knowledge base search
- `GET /v1/chat/history/{session_id}` - Retrieve chat history
- `DELETE /v1/chat/session/{session_id}` - Clear session
- `GET /v1/chat/sessions` - List user sessions
- `GET /v1/kb/health` - Knowledge base health check
- `GET /v1/stats` - System statistics

### Frontend Features

#### 1. **Modern UI/UX**
- Dark theme with warm accent colors (peach/orange palette)
- Glass morphism effects and smooth animations
- Responsive design (mobile, tablet, desktop)
- Tailwind CSS for styling
- Poppins font for professional appearance

#### 2. **Chat Interface**
- Real-time streaming message display
- Token-by-token response rendering
- Message formatting (markdown, lists, headers)
- Citation display with source documents
- Session continuity indicators

#### 3. **Authentication Flow**
- Modal-based login
- Persistent session with localStorage
- Auto-reconnect on page reload
- Graceful token expiration handling
- Visual connection status indicators

#### 4. **User Experience**
- Auto-resizing textarea
- Keyboard shortcuts (Ctrl+Enter to send)
- Loading states and animations
- Error notifications
- Sample query suggestions organized by topic:
  - GDPR Compliance
  - CSRD Reporting
  - EU Taxonomy
  - Digital Services Act

#### 5. **State Management**
- APIClient class for backend communication
- AuthManager for authentication state
- UIManager for interface updates
- Proper error handling and user feedback

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- AWS Account with Bedrock access
- LangSmith account (optional, for tracing)
- Node.js (only for development tools, not required for running)

### Backend Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd llm_app_1/backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file in the backend directory:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Bedrock Configuration
BEDROCK_KNOWLEDGE_BASE_ID=your_kb_id_or_leave_empty_for_mock
BEDROCK_GENERATION_MODEL=us.amazon.nova-pro-v1:0

# Authentication
SECRET_KEY=your_secret_key_here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# LangSmith Configuration (lowercase 'true'!)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=llm_app_1
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Application
DEBUG=false
LOG_LEVEL=INFO
```

5. **Run the application**
```bash
cd app
python main.py
```

The backend will start on `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**
```bash
cd frontend
```

2. **Configure API endpoint**

Edit `index.html` and update the API base URL if needed:

```javascript
const CONFIG = {
    API_BASE: 'http://localhost:8000',  // Change if backend runs elsewhere
    // ... other config
};
```

3. **Serve the frontend**

Option A - Python HTTP server:
```bash
python -m http.server 8080
```

Option B - Node.js http-server:
```bash
npx http-server -p 8080
```

Option C - VS Code Live Server extension

4. **Access the application**

Open your browser to `http://localhost:8080`

## 📊 LangSmith Tracing

The application provides comprehensive tracing through LangSmith:

### Trace Hierarchy
```
chat_endpoint (API route)
└── chat_pipeline (orchestrator)
    ├── memory_get_or_create_session
    │   └── memory_create_memory
    ├── memory_get_variables
    ├── generate_llm_response
    │   ├── bedrock_stream_response (streaming)
    │   └── kb_retrieve_documents (if KB lookup needed)
    │       ├── kb_parse_retrieval_results
    │       └── kb_parse_generation_result
    ├── enhance_with_kb_lookup (if applicable)
    └── memory_add_message
```

### Viewing Traces

1. Go to https://smith.langchain.com
2. Select your project (default: `llm_app_1`)
3. View traces in real-time as requests are processed
4. Inspect timing, inputs, outputs for each component

### Troubleshooting LangSmith

If traces aren't appearing:

1. **Verify environment variable is lowercase:**
   ```bash
   LANGCHAIN_TRACING_V2=true  # NOT "True" or "TRUE"
   ```

2. **Check API key permissions:**
   - Must be a "Personal" key with write permissions
   - Created in the correct workspace

3. **Clear browser cache** if you recently changed keys

4. **Check logs** for initialization messages:
   ```
   LangSmith monitoring enabled | Project: llm_app_1
   ```

## 🔧 Configuration

### Backend Configuration (`app/config.py`)

Key settings you may want to adjust:

```python
# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

# Memory window size (number of message pairs to remember)
window_size = 10

# Session timeout (seconds)
session_timeout = 7200  # 2 hours

# Max sessions in memory
max_sessions = 1000

# LLM settings (in streaming.py / orchestrator.py)
maxTokens: 1000
temperature: 0.3
```

### Frontend Configuration (`index.html`)

```javascript
const CONFIG = {
    API_BASE: 'http://localhost:8000',
    UI: {
        MAX_MESSAGE_LENGTH: 5000,
        TEXTAREA_MAX_HEIGHT: 120,
        AUTO_SCROLL_THRESHOLD: 100
    }
};
```

## 📁 Project Structure

```
llm_app_1/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_auth.py        # Authentication endpoints
│   │   │   └── routes_chat.py        # Chat endpoints (with LangSmith tracing)
│   │   ├── core/
│   │   │   ├── orchestrator.py       # Main request orchestration (traced)
│   │   │   ├── guardrails.py         # Response safety checks
│   │   │   ├── tools.py              # Additional tools
│   │   │   └── error_handler.py      # Error handling
│   │   ├── services/
│   │   │   ├── bedrock_client.py     # AWS Bedrock client
│   │   │   ├── bedrock_kb.py         # Knowledge base service (traced)
│   │   │   ├── memory_service.py     # Conversation memory (traced)
│   │   │   ├── streaming.py          # Streaming responses (traced)
│   │   │   ├── langsmith_service.py  # LangSmith integration
│   │   │   └── auth_service.py       # Authentication
│   │   ├── models/
│   │   │   ├── request_models.py     # Request schemas
│   │   │   └── response_models.py    # Response schemas
│   │   ├── config.py                 # Configuration
│   │   └── main.py                   # FastAPI application
│   ├── .env                          # Environment variables
│   └── requirements.txt              # Python dependencies
└── frontend/
    └── index.html                    # Single-page application
```

## 🧪 Testing

### Test Authentication
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Test Chat (Non-streaming)
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "What is GDPR?", "user_id": "test"}'
```

### Test Chat (Streaming)
```bash
curl -X POST "http://localhost:8000/v1/chat?stream=true" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "What is GDPR?", "user_id": "test"}'
```

### Test Session Management
Use the `/v1/test-sessions` endpoint to verify session continuity:
```bash
curl http://localhost:8000/v1/test-sessions \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🔍 Monitoring & Debugging

### Application Logs
- Uses `loguru` for structured logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request tracking with `request_id` and `user_id`
- Session tracking with `session_id`

### LangSmith Dashboard
- Real-time trace visualization
- Performance metrics per operation
- Input/output inspection
- Error tracking and debugging

### Health Checks
```bash
# Check KB health
curl http://localhost:8000/v1/kb/health \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check system stats
curl http://localhost:8000/v1/stats \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🚨 Common Issues

### Issue: Traces not appearing in LangSmith
**Solution:** Ensure `LANGCHAIN_TRACING_V2=true` (lowercase), valid API key, and restart the app

### Issue: "Session not found" errors
**Solution:** Session expired (2hr timeout) or was cleared. Start a new conversation.

### Issue: Mock KB responses instead of real data
**Solution:** Configure `BEDROCK_KNOWLEDGE_BASE_ID` with your actual KB ID

### Issue: 403 Forbidden from AWS
**Solution:** Check AWS credentials, region, and Bedrock model access permissions

### Issue: Frontend can't connect to backend
**Solution:** Verify CORS settings and API_BASE URL in frontend config

## 📝 Development Notes

### Adding New Endpoints
1. Create route in `routes_chat.py` or create new route file
2. Add `@langsmith_service.trace()` decorator for tracing
3. Update frontend `CONFIG.ENDPOINTS` if needed

### Modifying LLM Behavior
- Edit system prompts in `orchestrator.py` and `streaming.py`
- Adjust temperature/maxTokens in the request body
- Modify KB lookup triggers in `_should_use_kb_lookup()`

### Adding New Memory Types
- Extend `_create_memory()` in `memory_service.py`
- Use LangChain memory classes
- Add tracing decorators for observability

## 📄 License

[Add your license information]

## 👥 Contributing

[Add contribution guidelines]

## 📧 Support

For issues or questions:
- Check LangSmith traces for detailed error information
- Review application logs

---

**Note**: This application uses AWS Bedrock which incurs costs. Monitor your AWS usage and set up billing alerts. LangSmith has free and paid tiers - check their pricing for your usage level.