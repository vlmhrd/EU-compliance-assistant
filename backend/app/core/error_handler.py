# app/core/error_handler.py
import uuid
import time
import traceback
from typing import Union
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger
from app.core.logging_config import LoggingConfig

class ErrorHandler:
    @staticmethod
    async def http_exception_handler(request: Request, exc: Union[HTTPException, StarletteHTTPException]):
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        user_id = getattr(request.state, 'user_id', 'anonymous')
        
        LoggingConfig.log_error(
            request_id=request_id,
            user_id=user_id,
            error=exc,
            context={
                "url": str(request.url),
                "method": request.method,
                "status_code": exc.status_code
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": exc.detail,
                    "type": "http_exception",
                    "status_code": exc.status_code,
                    "request_id": request_id
                }
            }
        )

    @staticmethod
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        user_id = getattr(request.state, 'user_id', 'anonymous')
        
        LoggingConfig.log_error(
            request_id=request_id,
            user_id=user_id,
            error=exc,
            context={
                "url": str(request.url),
                "method": request.method,
                "validation_errors": exc.errors()
            }
        )
        
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "Validation error",
                    "type": "validation_error",
                    "details": exc.errors(),
                    "request_id": request_id
                }
            }
        )

    @staticmethod
    async def general_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
        user_id = getattr(request.state, 'user_id', 'anonymous')
        
        logger.bind(request_id=request_id, user_id=user_id).error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Internal server error",
                    "type": "internal_error",
                    "request_id": request_id
                }
            }
        )

class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        request.state.request_id = request_id
        
        user_id = "anonymous"
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                from app.services.auth_service import verify_jwt_token
                token = auth_header.split(" ")[1]
                user_id = verify_jwt_token(token)
                request.state.user_id = user_id
        except Exception:
            pass  
        
        query_params = dict(request.query_params) if request.query_params else None
        LoggingConfig.log_request_start(
            request_id=request_id,
            user_id=user_id,
            endpoint=request.url.path,
            method=request.method,
            query=str(query_params) if query_params else None
        )

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time
                status_code = message["status"]
                
                # Log request completion
                LoggingConfig.log_request_end(
                    request_id=request_id,
                    user_id=user_id,
                    endpoint=request.url.path,
                    method=request.method,
                    duration=duration,
                    status_code=status_code
                )
            
            await send(message)

        await self.app(scope, receive, send_wrapper)

class KnowledgeBaseError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class ValidationError(Exception):
    pass

class RateLimitError(Exception):
    pass