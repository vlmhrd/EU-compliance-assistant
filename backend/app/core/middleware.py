# app/core/middleware.py
import time
import uuid
from typing import Callable, Optional, List
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from loguru import logger
import json
from collections import defaultdict
from datetime import datetime, timedelta


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.request_count = defaultdict(int)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        start_time = time.time()
        
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        real_ip = forwarded_for if forwarded_for else client_ip
        
        logger.bind(
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            client_ip=real_ip,
            user_agent=request.headers.get("User-Agent", "unknown")
        ).info("Request started")
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            logger.bind(
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time=f"{process_time:.3f}s",
                client_ip=real_ip
            ).info("Request completed")
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}s"
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            logger.bind(
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                process_time=f"{process_time:.3f}s",
                client_ip=real_ip,
                error=str(e)
            ).error("Request failed with exception")
            
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = defaultdict(list)
    
    def _clean_old_requests(self, ip: str, now: datetime):
        cutoff = now - timedelta(minutes=1)
        self.request_counts[ip] = [
            req_time for req_time in self.request_counts[ip] 
            if req_time > cutoff
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        real_ip = forwarded_for if forwarded_for else client_ip
        
        now = datetime.now()
        
        self._clean_old_requests(real_ip, now)
        
        if len(self.request_counts[real_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {real_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_minute} requests per minute allowed",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )
        
        self.request_counts[real_ip].append(now)
        
        return await call_next(request)


class HealthCheckMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.cached_health = None
        self.cache_time = None
        self.cache_duration = 30  
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "GET" and request.url.path == "/health":
            now = datetime.now()
            
            if (self.cached_health and self.cache_time and 
                (now - self.cache_time).seconds < self.cache_duration):
                
                logger.debug("Returning cached health check response")
                return JSONResponse(content=self.cached_health)
        
        response = await call_next(request)
        
        if (request.method == "GET" and request.url.path == "/health" and 
            response.status_code == 200 and hasattr(response, 'body')):
            
            try:
                body = getattr(response, 'body', b'')
                if body:
                    self.cached_health = json.loads(body.decode())
                    self.cache_time = datetime.now()
                    logger.debug("Cached health check response")
            except Exception as e:
                logger.warning(f"Failed to cache health check response: {e}")
        
        return response


class RequestSizeMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app: ASGIApp, max_size: int = 10 * 1024 * 1024):  # 10MB default
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("Content-Length")
        
        if content_length:
            try:
                content_length = int(content_length)
                if content_length > self.max_size:
                    logger.warning(f"Request too large: {content_length} bytes (max: {self.max_size})")
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Request entity too large",
                            "detail": f"Maximum request size is {self.max_size} bytes",
                            "received": content_length
                        }
                    )
            except ValueError:
                pass  # Invalid Content-Length header, let FastAPI handle it
        
        return await call_next(request)


class APIVersionMiddleware(BaseHTTPMiddleware):
    
    def __init__(self, app: ASGIApp, version: str = "0.4"):
        super().__init__(app)
        self.version = version
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-API-Version"] = self.version
        return response


def setup_middlewares(app, config: Optional[dict] = None):
    if config is None:
        config = {}
    
    allowed_origins = config.get("cors_origins", [
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS middleware enabled for origins: {allowed_origins}")
    
    app.add_middleware(
        APIVersionMiddleware,
        version=config.get("api_version", "0.4")
    )
    
    app.add_middleware(
        RequestSizeMiddleware,
        max_size=config.get("max_request_size", 10 * 1024 * 1024)
    )
    
    app.add_middleware(HealthCheckMiddleware)
    
    if config.get("enable_rate_limiting", True):
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=config.get("rate_limit_rpm", 100)
        )
    
    if config.get("enable_security_headers", True):
        app.add_middleware(SecurityHeadersMiddleware)
    
    app.add_middleware(RequestLoggingMiddleware)
    
    logger.info("All middlewares registered successfully")


def setup_cors_only(app, origins: Optional[List[str]] = None):
    if origins is None:
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080", 
            "http://127.0.0.1:8080"
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS-only middleware enabled for origins: {origins}")


__all__ = [
    "RequestLoggingMiddleware",
    "SecurityHeadersMiddleware", 
    "RateLimitMiddleware",
    "HealthCheckMiddleware",
    "RequestSizeMiddleware",
    "APIVersionMiddleware",
    "setup_middlewares",
    "setup_cors_only"
]