from typing import Optional, Dict, Any, Callable
from functools import wraps
from contextlib import contextmanager, asynccontextmanager
from loguru import logger
from app.config import settings

try:
    from langsmith import Client
    from langsmith.run_helpers import traceable, trace
    import langsmith
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    logger.warning("LangSmith not installed. Install with: pip install langsmith")


class LangSmithService:
    
    def __init__(self):
        self.enabled = False
        self.client = None
        
        if LANGSMITH_AVAILABLE:
            try:
                tracing_enabled = settings.LANGCHAIN_TRACING_V2
                api_key = settings.LANGCHAIN_API_KEY
                project = settings.LANGCHAIN_PROJECT
                
                logger.debug(f"LangSmith config check - Tracing: {tracing_enabled}, API key exists: {bool(api_key)}")
                
                if tracing_enabled and api_key:
                    self.client = Client(api_key=api_key)
                    self.enabled = True
                    logger.info(f"LangSmith monitoring enabled | Project: {project}")
                    
                    try:
                        self.client.list_projects(limit=1)
                        logger.info(f"LangSmith connection verified")
                    except Exception as e:
                        logger.error(f"LangSmith connection test failed: {e}")
                        
                else:
                    if not tracing_enabled:
                        logger.info(f"LangSmith monitoring disabled (LANGCHAIN_TRACING_V2={tracing_enabled})")
                    elif not api_key:
                        logger.info("LangSmith monitoring disabled (LANGCHAIN_API_KEY not set)")
            except Exception as e:
                logger.error(f"Failed to initialize LangSmith: {e}")
                self.enabled = False
        else:
            logger.warning("LangSmith not available (langsmith package not installed)")
    
    def trace(self, 
              name: str = None,
              run_type: str = "chain",
              metadata: Optional[Dict[str, Any]] = None):

        def decorator(func: Callable) -> Callable:
            if not self.enabled:
                logger.debug(f"Tracing disabled, skipping trace for {func.__name__}")
                return func
            
            trace_name = name or func.__name__
            
            traced_func = traceable(
                run_type=run_type,
                name=trace_name,
                metadata=metadata or {},
                project_name=settings.LANGCHAIN_PROJECT
            )(func)
            
            logger.debug(f"Applied LangSmith trace to {trace_name}")
            return traced_func
        
        return decorator
    
    @asynccontextmanager
    async def trace_context(self, name: str, run_type: str = "chain", **kwargs):
        if not self.enabled:
            yield None
            return
            
        try:
            with trace(
                name=name,
                run_type=run_type,
                project_name=settings.LANGCHAIN_PROJECT,
                **kwargs
            ) as run:
                logger.debug(f"Started trace context: {name}")
                yield run
                logger.debug(f"Completed trace context: {name}")
        except Exception as e:
            logger.error(f"Error in trace context {name}: {e}")
            yield None
    
    def log_feedback(self, 
                     run_id: str, 
                     score: float, 
                     feedback_key: str = "user_rating",
                     comment: Optional[str] = None):
        if not self.enabled or not self.client:
            logger.debug("LangSmith feedback not logged (disabled)")
            return
        
        try:
            self.client.create_feedback(
                run_id=run_id,
                key=feedback_key,
                score=score,
                comment=comment
            )
            logger.info(f"Logged feedback for run {run_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")


langsmith_service = LangSmithService()