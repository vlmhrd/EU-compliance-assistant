# compl.ai - EU Compliance AI Assistant

A professional AI-powered application that provides instant guidance on EU regulations, GDPR compliance, CSRD reporting, and other regulatory requirements. Built with FastAPI backend and vanilla JavaScript frontend, featuring real-time streaming responses and comprehensive observability through LangSmith.

## 🎯 What Does This Application Do?

**compl.ai** is an intelligent compliance assistant that helps businesses and professionals navigate complex EU regulations through natural language conversations. The system combines:

- **AI-Powered Responses**: Uses Amazon Bedrock's Nova Pro model for accurate, context-aware answers
- **Knowledge Base Integration**: Retrieves and cites relevant regulatory documents from AWS Bedrock Knowledge Base
- **Session Management**: Maintains conversation context across multiple interactions
- **Real-time Streaming**: Provides responsive, token-by-token streaming responses
- **Observability**: Full request tracing through LangSmith for monitoring and debugging
- **Prompt engineering**: The application uses a centralized prompt management system integrated with LangSmith Hub for version control and A/B testing.

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

#### 2. **Prompt Engineering**

**Architecture:**
```
User Query
  ↓
Check if KB lookup needed (keywords: gdpr, article, requirement, etc.)
  ↓
[If needed] → Retrieve relevant documents from Bedrock KB
  ↓
Pull prompt from LangSmith Hub (client.pull_prompt())
  ↓
Inject KB documents into {context} placeholder
  ↓
Send complete prompt to Bedrock Nova Pro
  ↓
Return response with citations
```

#### 3. **Knowledge Base (RAG)**
- AWS Bedrock Knowledge Base integration for document retrieval
- Vector search with configurable result counts
- Citation tracking with source documents
- Mock KB mode for development without AWS resources

#### 4. **Memory Management**
- LangChain-based conversation memory
- Buffer window memory (configurable history length)
- Session persistence with automatic cleanup
- Multi-user session isolation

#### 5. **Session Management**
- Unique session IDs for conversation continuity
- Session metadata tracking (user, timestamps, message counts)
- Automatic session expiration (2 hours idle)
- Session limit enforcement (1000 max sessions)

#### 6. **Observability with LangSmith**
- Complete request tracing from endpoint to LLM
- Traces for memory operations (session creation, message storage)
- KB retrieval and parsing traces
- Hierarchical trace visualization showing parent-child relationships
- Performance metrics and timing information

#### 7. **Security & Authentication**
- JWT-based authentication
- Token expiration handling
- User authorization for session access
- Environment-based configuration

#### 8. **API Endpoints**
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

  - **Option A** - Python HTTP server:
    ```bash
    python -m http.server 8080
    ```
  - **Option B** - Node.js http-server:
    ```bash
    npx http-server -p 8080
    ```
  - **Option C** - VS Code Live Server extension

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

## 🛡️ Guardrails

The application includes AWS Bedrock Guardrails for content safety and policy compliance.

### Configuration

Add to your `.env` file:

```bash
BEDROCK_GUARDRAIL_ID=your_guardrail_id_here
BEDROCK_GUARDRAIL_VERSION=DRAFT  # or specific version number
```

### How It Works

1. **Content Filtering**: All LLM responses pass through guardrails before being sent to users
2. **Policy Enforcement**: Blocks content that violates configured policies
3. **Graceful Handling**: Returns appropriate messages when content is blocked
4. **Optional**: If no guardrail ID is configured, responses are returned as-is

### Guardrail Features

```python
# Automatically applied in orchestrator.py and streaming.py
from app.core.guardrails import apply_guardrails

safe_response = apply_guardrails(
  answer=llm_response,
  user_input=user_query,
  request_id=request_id,
  user_id=user_id
)
```

### Health Check

```bash
# Check guardrail status
curl http://localhost:8000/v1/guardrails/health \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### What Gets Filtered

Based on your guardrail configuration in AWS Bedrock:
- Harmful content
- PII (Personally Identifiable Information)
- Profanity and offensive language
- Off-topic responses
- Custom denied topics

## 🚨 Error Handling

Comprehensive error handling throughout the application with proper logging and user feedback.

### Error Types

#### 1. **HTTP Exceptions** (400-599)

```python
# Custom error classes
class ValidationError(Exception): pass
class AuthenticationError(Exception): pass
class KnowledgeBaseError(Exception): pass
class RateLimitError(Exception): pass
```

#### 2. **Request Validation Errors**

Automatic validation using Pydantic models with detailed error messages:

```json
{
  "error": {
  "message": "Validation error",
  "type": "validation_error",
  "details": [...],
  "request_id": "abc-123"
  }
}
```

#### 3. **LLM/Bedrock Errors**
- Model invocation failures
- Timeout errors
- Rate limiting
- Invalid model parameters

#### 4. **Knowledge Base Errors**
- KB not found
- Retrieval failures
- Parsing errors

### Error Response Format

All errors return consistent JSON format:

```json
{
  "error": {
  "message": "Human-readable error message",
  "type": "error_type",
  "status_code": 500,
  "request_id": "unique-request-id"
  }
}
```

### Request Logging

Every request is tracked with:
- Unique `request_id`
- User identification
- Start/end timestamps
- Duration
- Status code
- Query parameters

Example log output:

```
2025-01-15 10:30:45 | INFO | request_id=abc123 user_id=admin | 
  Request started: POST /v1/chat
2025-01-15 10:30:47 | INFO | request_id=abc123 user_id=admin | 
  Request completed: POST /v1/chat | duration=2.1s | status=200
```

### Frontend Error Handling

The frontend gracefully handles:
- **401 Unauthorized**: Auto-logout and redirect to login
- **403 Forbidden**: Permission denied notification
- **500 Server Error**: "Technical difficulties" message
- **Network Errors**: Connection failure notifications
- **Timeout Errors**: Retry suggestions

### Debugging Errors

1. **Check request_id** in error response
2. **Search logs** for that request_id:
  ```bash
  grep "abc123" logs/app.log
  ```
3. **View in LangSmith** for detailed trace of what failed
4. **Check error context** in logged JSON

## 💾 Data Storage in S3

The application includes utilities for storing documents in AWS S3 for the Knowledge Base.

### S3 Configuration

Add to your `.env` file:

```bash
S3_BUCKET_NAME=your-bucket-name
S3_PREFIX=documents/
PDF_FOLDER_PATH=./pdfs
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### PDF Ingestion Script

Use the included `pdf_ingest.py` script to upload documents to S3:

```bash
cd backend
python pdf_ingest.py
```

### How It Works

1. **Document Preparation**
  - Place PDF files in the configured folder (default: `./pdfs`)
  - Script validates file existence and format

2. **Upload Process**
  ```python
  # The script automatically:
  # - Connects to S3 using credentials
  # - Scans for PDF files
  # - Uploads with proper metadata
  # - Tracks success/failure
  ```

3. **Metadata Tracking**
  Each uploaded file includes:
  - Original filename
  - Upload timestamp
  - Content type (application/pdf)

4. **Knowledge Base Sync**
  - After upload, AWS Bedrock KB automatically indexes new documents
  - Sync can take 5-30 minutes depending on document size
  - Monitor sync status in AWS Bedrock console

### Manual Upload Alternative

You can also upload directly via AWS CLI:

```bash
aws s3 cp ./pdfs/document.pdf \
  s3://your-bucket-name/documents/document.pdf \
  --content-type application/pdf
```

### S3 Bucket Structure

```
your-bucket-name/
└── documents/              # Configured by S3_PREFIX
  ├── gdpr-guide.pdf
  ├── csrd-requirements.pdf
  ├── eu-taxonomy.pdf
  └── ...
```

### Best Practices

1. **Organize Documents**
  - Use clear, descriptive filenames
  - Consider subfolders for different regulation types
  - Keep original source documentation

2. **Security**
  - Use IAM roles with minimum required permissions
  - Enable S3 bucket encryption
  - Configure bucket policies appropriately
  - Never commit AWS credentials to Git

3. **Monitoring**
  - Check upload logs for failures
  - Monitor S3 storage costs
  - Track Knowledge Base sync status
  - Set up CloudWatch alerts for upload failures

4. **Document Management**
  - Version control your source documents
  - Keep a backup of uploaded PDFs
  - Document the source of each regulatory document
  - Regularly update outdated documents

### Troubleshooting S3 Upload

**Issue: "No credentials found"**

```bash
# Verify credentials are in .env
grep AWS_ACCESS_KEY_ID .env

# Or set them temporarily
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

**Issue: "Bucket does not exist"**

```bash
# Create bucket
aws s3 mb s3://your-bucket-name --region us-east-1

# Verify bucket exists
aws s3 ls
```

**Issue: "Access Denied"**
- Check IAM permissions for S3 PutObject
- Verify bucket policy allows your IAM user/role
- Ensure bucket name is correct

**Issue: "KB not finding uploaded documents"**
- Wait for Bedrock KB sync (5-30 minutes)
- Check KB data source is pointing to correct S3 prefix
- Verify KB sync completed without errors in AWS console

## 📧 Support

For issues or questions:
- Check LangSmith traces for detailed error information
- Review application logs

---

**Note**: This application uses AWS Bedrock which incurs costs. Monitor your AWS usage and set up billing alerts. LangSmith has free and paid tiers - check their pricing for your usage level.