from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import os

from app.core.logging_config import logging_config, app_logger
from app.core.error_handler import (
    ErrorHandler, 
    KnowledgeBaseError,
    AuthenticationError,
    ValidationError,
    RateLimitError
)
from app.api import routes_chat, routes_auth, routes_safety
from app.services.bedrock_kb import EnhancedBedrockKB
from app.core.middleware import setup_middlewares


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("🚀 Legal AI Assistant starting up...")
    
    try:
        from app.core.guardrails import get_guardrails
        guardrails = get_guardrails()
        guardrails_health = guardrails.health_check()
        
        if guardrails_health["status"] == "healthy":
            app_logger.info(f"✅ Bedrock Guardrails active - ID: {guardrails_health['guardrail_id']}")
        elif guardrails_health["status"] == "disabled":
            app_logger.info(f"ℹ️ Using basic guardrails only (no Bedrock Guardrail configured)")
        else:
            app_logger.warning(f"⚠️ Bedrock Guardrails unhealthy: {guardrails_health.get('error', 'Unknown error')}")
    except Exception as e:
        app_logger.warning(f"⚠️ Could not initialize guardrails: {str(e)}")
    
    try:
        kb = EnhancedBedrockKB()
        health_status = kb.health_check()
        
        if health_status["status"] == "healthy":
            if health_status.get("mock", False):
                app_logger.warning(f" Using Mock Knowledge Base for development")
                app_logger.info(f" Configure BEDROCK_KNOWLEDGE_BASE_ID in .env to use real AWS Bedrock KB")
            else:
                app_logger.info(f" Knowledge Base connection successful - KB ID: {health_status['kb_id']}")
        else:
            if "ResourceNotFoundException" in str(health_status.get("error", "")):
                app_logger.warning(f" Knowledge Base not found, but application will continue with mock responses")
                app_logger.info(f" To fix: Check KB ID '{health_status.get('kb_id')}' exists in region '{health_status.get('region', 'us-east-1')}'")
            else:
                app_logger.warning(f" Knowledge Base health check failed: {health_status.get('error', 'Unknown error')}")
                
    except Exception as e:
        app_logger.warning(f" Could not initialize Knowledge Base: {str(e)}")
        app_logger.info(f" Application will continue with mock responses for development")
    
    app_logger.info(" Application startup completed")
    
    yield
    
    # Shutdown
    app_logger.info(" Legal AI Assistant shutting down...")


app = FastAPI(
    title="Legal AI Assistant",
    version="0.4",
    description="Enhanced Legal AI Assistant with comprehensive logging and improved RAG functionality",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8000",  
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time", "X-API-Version"]
)

app_logger.info("CORS middleware configured for cross-origin requests")

setup_middlewares(app, {
    "api_version": "0.4",
    "max_request_size": 10 * 1024 * 1024,  # 10MB
    "enable_rate_limiting": True,
    "rate_limit_rpm": 100,
    "enable_security_headers": True,
    "skip_cors": True  
})

app.add_exception_handler(StarletteHTTPException, ErrorHandler.http_exception_handler)
app.add_exception_handler(RequestValidationError, ErrorHandler.validation_exception_handler)
app.add_exception_handler(Exception, ErrorHandler.general_exception_handler)

@app.exception_handler(KnowledgeBaseError)
async def knowledge_base_exception_handler(request: Request, exc: KnowledgeBaseError):
    return await ErrorHandler.http_exception_handler(request, StarletteHTTPException(status_code=503, detail=str(exc)))

@app.exception_handler(AuthenticationError)
async def auth_exception_handler(request: Request, exc: AuthenticationError):
    return await ErrorHandler.http_exception_handler(request, StarletteHTTPException(status_code=401, detail=str(exc)))

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return await ErrorHandler.http_exception_handler(request, StarletteHTTPException(status_code=400, detail=str(exc)))

@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(request: Request, exc: RateLimitError):
    return await ErrorHandler.http_exception_handler(request, StarletteHTTPException(status_code=429, detail=str(exc)))

app.include_router(routes_auth.router)
app.include_router(routes_chat.router, prefix="/v1", tags=["chat"])
app.include_router(routes_safety.router, prefix="/v1", tags=["safety"])

@app.get("/health", tags=["Health"])
async def health_check():
    try:
        kb = EnhancedBedrockKB()
        kb_status = kb.health_check()
        
        overall_status = "healthy"
        if kb_status["status"] == "unhealthy":
            overall_status = "degraded"
        elif kb_status.get("mock", False):
            overall_status = "development"
        
        return {
            "status": overall_status,
            "version": "0.4",
            "components": {
                "knowledge_base": kb_status,
                "authentication": {"status": "healthy"},
                "api": {"status": "healthy"},
                "cors": {
                    "status": "enabled",
                    "allowed_origins": [
                        "http://localhost:3000",
                        "http://127.0.0.1:3000",
                        "http://localhost:8080",
                        "http://127.0.0.1:8080"
                    ]
                }
            },
            "timestamp": kb_status["timestamp"],
            "message": "Using mock KB for development" if kb_status.get("mock") else None
        }
    except Exception as e:
        app_logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": "0.4",
            "timestamp": None,
            "cors": {"status": "enabled"}
        }

@app.get("/cors-test", tags=["Debug"])
async def cors_test():
    return {
        "message": "CORS is working!",
        "cors_enabled": True,
        "server": "FastAPI Legal AI Assistant",
        "version": "0.4"
    }

# Root endpoint
@app.get("/api", tags=["Root"])
async def api_root():
    """API root endpoint with basic information"""
    return {
        "message": "Legal AI Assistant API",
        "version": "0.4",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "cors_test": "/cors-test",
        "endpoints": {
            "chat": "/v1/chat",
            "search": "/v1/search", 
            "login": "/auth/login",
            "profile": "/auth/me"
        },
        "cors": {
            "enabled": True,
            "note": "Cross-origin requests from localhost:3000 are allowed"
        }
    }

# Mount static files for frontend
# Create these directories if they don't exist
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Create directories if they don't exist
os.makedirs(static_dir, exist_ok=True)
os.makedirs(frontend_dir, exist_ok=True)

# Mount static files
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app_logger.info(f"Static files mounted from: {static_dir}")

# Mount frontend files (this should be last to catch all remaining routes)
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    app_logger.info(f"Frontend files mounted from: {frontend_dir}")
else:
    @app.get("/")
    async def root():
        return {
            "message": "Legal AI Assistant",
            "version": "0.4",
            "status": "running",
            "api_docs": "/docs",
            "health": "/health",
            "cors_test": "/cors-test",
            "note": "Frontend files not found. API endpoints are available.",
            "cors": {
                "enabled": True,
                "frontend_urls": [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000"
                ]
            }
        }