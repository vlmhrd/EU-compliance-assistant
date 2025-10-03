# app/core/logging_config.py
import os
import sys
from pathlib import Path
from loguru import logger
from typing import Dict, Any, List

# Import settings to use configuration
from app.config import settings

def format_record(record):
    extra = record["extra"]
    
    if "request_id" not in extra:
        extra["request_id"] = "N/A"
    if "user_id" not in extra:
        extra["user_id"] = "system"
    
    return True  
class LoggingConfig:
    def __init__(self):
        self.setup_logging()
    
    def setup_logging(self):
        logger.remove()
        
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        log_level = getattr(settings, 'LOG_LEVEL', 'INFO').upper()
        retention_days = getattr(settings, 'LOG_RETENTION_DAYS', 30)
        
        if settings.APP_ENV != "production":
            logger.add(
                sys.stdout,
                level=log_level,
                format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                colorize=True,
                backtrace=True,
                diagnose=True,
                filter=format_record
            )
        else:
            logger.add(
                sys.stdout,
                level="WARNING",  # Only warnings and errors in prod console
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra[request_id]} | {extra[user_id]} | {message}",
                backtrace=False,
                diagnose=False,
                filter=format_record
            )
        
        logger.add(
            "logs/unified_log",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra[request_id]} | {extra[user_id]} | {message}",
            rotation="100 MB",
            retention=f"{retention_days} days",
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Thread-safe logging
            serialize=False,
            filter=format_record
        )
        
        logger.add(
            "logs/errors.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {extra[request_id]} | {extra[user_id]} | {message}",
            rotation="50 MB",
            retention=f"{retention_days * 2} days",  # Keep errors longer
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True,
            filter=format_record
        )
        
        logger.add(
            "logs/performance.log",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {extra[endpoint]} | {extra[method]} | {extra[duration]} | {extra[status_code]} | {extra[user_id]} | {message}",
            filter=lambda record: format_record(record) and "performance" in record["extra"],
            rotation="50 MB",
            retention="7 days"
        )
        
        if settings.DEBUG:
            logger.add(
                "logs/debug.log",
                level="DEBUG",
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {extra[request_id]} | {message}",
                rotation="25 MB",
                retention="3 days",
                filter=format_record
            )

    @staticmethod
    def get_logger(name: str = None):
        if name:
            return logger.bind(name=name, request_id="system", user_id="system")
        return logger.bind(request_id="system", user_id="system")

    @staticmethod
    def log_request_start(request_id: str, user_id: str, endpoint: str, method: str, query: str = None):
        logger.bind(request_id=request_id, user_id=user_id).info(
            f"Request started - {method} {endpoint}" + (f" | Query: {query[:100]}..." if query and len(query) > 100 else f" | Query: {query}" if query else "")
        )

    @staticmethod
    def log_request_end(request_id: str, user_id: str, endpoint: str, method: str, duration: float, status_code: int):
        logger.bind(
            request_id=request_id, 
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            duration=f"{duration:.3f}s",
            status_code=status_code,
            performance=True
        ).info(f"Request completed in {duration:.3f}s")

    @staticmethod
    def log_error(request_id: str, user_id: str, error: Exception, context: Dict[str, Any] = None):
        context_str = f" | Context: {context}" if context else ""
        logger.bind(request_id=request_id, user_id=user_id).error(
            f"Error occurred: {type(error).__name__}: {str(error)}{context_str}"
        )

    @staticmethod
    def log_kb_query(request_id: str, user_id: str, query: str, num_results: int, duration: float):
        logger.bind(request_id=request_id, user_id=user_id).info(
            f"KB Query completed | Results: {num_results} | Duration: {duration:.3f}s | Query: {query[:100]}..."
        )

    @staticmethod
    def log_auth_attempt(username: str, success: bool, ip_address: str = None):
        status = "SUCCESS" if success else "FAILED"
        ip_info = f" | IP: {ip_address}" if ip_address else ""
        logger.bind(request_id="auth", user_id=username).info(
            f"Auth attempt {status} for user: {username}{ip_info}"
        )

    @staticmethod
    def log_config_loaded():
        logger.bind(request_id="startup", user_id="system").info(
            f"Configuration loaded | ENV: {settings.APP_ENV} | DEBUG: {settings.DEBUG} | LOG_LEVEL: {settings.LOG_LEVEL}"
        )

    @staticmethod
    def log_guardrails_init(guardrail_id: str, version: str, enabled: bool, error: str = None):
        if enabled:
            logger.bind(request_id="startup", user_id="system").info(
                f"Bedrock Guardrails initialized | ID: {guardrail_id} | Version: {version}"
            )
        elif error:
            logger.bind(request_id="startup", user_id="system").warning(
                f"Bedrock Guardrails failed to initialize: {error}"
            )
        else:
            logger.bind(request_id="startup", user_id="system").info(
                "Using basic guardrails only (no Bedrock Guardrail ID configured)"
            )

    @staticmethod
    def log_guardrails_processing(
        request_id: str, 
        user_id: str, 
        bedrock_enabled: bool, 
        blocked: bool, 
        duration: float,
        categories_blocked: List[str] = None,
        error: str = None
    ):
        if error:
            logger.bind(request_id=request_id, user_id=user_id).error(
                f"Guardrails processing failed: {error}"
            )
        elif blocked:
            blocked_cats = f" | Categories: {', '.join(categories_blocked)}" if categories_blocked else ""
            logger.bind(request_id=request_id, user_id=user_id).warning(
                f"Content BLOCKED by guardrails | Bedrock: {bedrock_enabled} | Duration: {duration:.3f}s{blocked_cats}"
            )
        else:
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Guardrails passed | Bedrock: {bedrock_enabled} | Duration: {duration:.3f}s"
            )

logging_config = LoggingConfig()
app_logger = LoggingConfig.get_logger("legal-ai-assistant")

LoggingConfig.log_config_loaded()