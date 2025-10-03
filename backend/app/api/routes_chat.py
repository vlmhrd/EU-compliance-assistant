# app/api/routes_chat.py (Updated with LangSmith Tracing)
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional, List
import uuid
import time

from app.models.request_models import ChatRequest
from app.models.response_models import (
    ChatResponse, ChatHistoryRequest, ChatHistoryResponse, 
    SessionInfo, SearchResponse
)
from app.core.orchestrator import chat_pipeline, search_documents
from app.services.auth_service import get_current_user
from app.services.memory_service import memory_service
from app.services.langsmith_service import langsmith_service
from app.core.error_handler import ValidationError, KnowledgeBaseError
from app.core.logging_config import LoggingConfig
from loguru import logger

from fastapi.responses import StreamingResponse
import json

router = APIRouter()
import os

@router.get("/debug/langsmith")
@langsmith_service.trace(
    name="debug_langsmith_config",
    run_type="tool",
    metadata={"endpoint": "/debug/langsmith"}
)
async def debug_langsmith(
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Debug LangSmith configuration"""
    from app.config import settings
    
    return {
        "langsmith_service": {
            "enabled": langsmith_service.enabled,
            "client_exists": langsmith_service.client is not None,
        },
        "settings": {
            "langsmith_enabled": settings.LANGCHAIN_TRACING_V2,
            "api_key_set": bool(settings.LANGCHAIN_API_KEY),
            "api_key_length": len(settings.LANGCHAIN_API_KEY) if settings.LANGCHAIN_API_KEY else 0,
            "project": settings.LANGCHAIN_PROJECT,
            "endpoint": settings.LANGCHAIN_ENDPOINT,
        },
        "env_vars": {
            "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2"),
            "LANGCHAIN_API_KEY_SET": bool(os.getenv("LANGCHAIN_API_KEY")),
            "LANGCHAIN_PROJECT": os.getenv("LANGCHAIN_PROJECT"),
            "LANGCHAIN_ENDPOINT": os.getenv("LANGCHAIN_ENDPOINT"),
        },
        "instructions": {
            "1": "Ensure LANGCHAIN_TRACING_V2=true in your .env file",
            "2": "Ensure LANGCHAIN_API_KEY is set with your key from https://smith.langchain.com",
            "3": "Restart your FastAPI application after .env changes",
            "4": "Make a request to /v1/chat",
            "5": "Check traces at https://smith.langchain.com/projects"
        }
    }

@router.post("/chat")
@langsmith_service.trace(
    name="chat_endpoint",
    run_type="chain",
    metadata={"endpoint": "/chat", "streaming_support": True}
)
async def chat_with_streaming(
    request: ChatRequest, 
    fastapi_request: Request,
    session_id: Optional[str] = Query(None, description="Optional session ID for conversation continuity"),
    stream: bool = Query(False, description="Enable streaming response"),
    current_user: str = Depends(get_current_user)
):
    """Enhanced chat endpoint with optional streaming support"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        if not request.query or len(request.query.strip()) == 0:
            raise ValidationError("Query cannot be empty")
        
        if len(request.query) > 10000:
            raise ValidationError("Query is too long (maximum 10000 characters)")
        
        if not request.user_id:
            request.user_id = current_user
        
        # Generate session ID if not provided
        if not session_id:
            session_id = f"{current_user}_{str(uuid.uuid4())}"
            logger.bind(request_id=request_id, user_id=current_user).info(
                f"Generated new session ID: {session_id}"
            )
        else:
            logger.bind(request_id=request_id, user_id=current_user).info(
                f"Using existing session ID: {session_id}"
            )
        
        logger.bind(request_id=request_id, user_id=current_user, session_id=session_id).info(
            f"Chat request received | User: {request.user_id} | Query length: {len(request.query)} | Streaming: {stream}"
        )
        
        if stream:
            # Return streaming response
            return StreamingResponse(
                generate_streaming_response(request, request_id, current_user, session_id),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )
        else:
            # Return regular response
            from app.core.orchestrator import chat_pipeline
            
            result = await chat_pipeline(
                request=request,
                request_id=request_id,
                user_id=current_user,
                session_id=session_id
            )
            
            return result
        
    except ValidationError as e:
        logger.bind(request_id=request_id, user_id=current_user).warning(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@langsmith_service.trace(
    name="generate_streaming_response",
    run_type="chain",
    metadata={"response_type": "sse"}
)
async def generate_streaming_response(
    request: ChatRequest,
    request_id: str,
    user_id: str,
    session_id: str
):
    """Generate Server-Sent Events for streaming chat response"""
    
    try:
        from app.core.orchestrator import chat_pipeline_streaming
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            "Starting streaming response generation"
        )
        
        async for chunk_data in chat_pipeline_streaming(
            request=request,
            request_id=request_id,
            user_id=user_id,
            session_id=session_id
        ):
            # Format as Server-Sent Events
            sse_data = f"data: {json.dumps(chunk_data)}\n\n"
            
            logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                f"Yielding SSE chunk: {chunk_data.get('type', 'unknown')}"
            )
            
            yield sse_data
            
            # Break on completion or error
            if chunk_data.get("type") in ["complete", "error"]:
                logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
                    f"Streaming completed with type: {chunk_data.get('type')}"
                )
                break
    
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
            f"Error in streaming response: {str(e)}"
        )
        
        # Send error as SSE
        error_data = {
            "type": "error",
            "content": f"Streaming error: {str(e)}",
            "session_id": session_id
        }
        yield f"data: {json.dumps(error_data)}\n\n"


@router.get("/test-streaming")
@langsmith_service.trace(
    name="test_streaming_endpoint",
    run_type="chain",
    metadata={"endpoint": "/test-streaming", "test": True}
)
async def test_streaming_endpoint(
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Test streaming functionality"""
    
    async def test_stream():
        """Simple test stream"""
        for i in range(5):
            test_data = {
                "type": "chunk" if i < 4 else "complete",
                "content": f"Test chunk {i+1}/5: Hello from streaming! ",
                "session_id": "test-session",
                "timestamp": time.time()
            }
            
            yield f"data: {json.dumps(test_data)}\n\n"
            
            # Small delay to simulate processing
            import asyncio
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        test_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.get("/test-sessions")
@langsmith_service.trace(
    name="test_session_management",
    run_type="chain",
    metadata={"endpoint": "/test-sessions", "test": True}
)
async def test_session_management(
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Test endpoint for session management functionality"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        logger.bind(request_id=request_id, user_id=current_user).info(
            "Session management test started"
        )
        
        # Test 1: Create a new session
        session_id = str(uuid.uuid4())
        test_results = {}
        
        logger.info(f"Testing session management with session_id: {session_id}")
        
        # Test 2: First message
        request1 = ChatRequest(
            query="What is GDPR?",
            user_id=current_user
        )
        
        response1 = await chat_pipeline(
            request=request1,
            request_id=f"{request_id}_1", 
            user_id=current_user,
            session_id=session_id
        )
        
        test_results["first_message"] = {
            "response_preview": response1.answer[:100] + "...",
            "session_id_returned": response1.session_id,
            "citations_count": len(response1.citations)
        }
        
        # Test 3: Check session state
        session_info = memory_service.get_session_info(session_id)
        test_results["session_after_first"] = session_info
        
        # Test 4: Second message (should have context)
        request2 = ChatRequest(
            query="Can you tell me more about the data subject rights?",
            user_id=current_user
        )
        
        response2 = await chat_pipeline(
            request=request2,
            request_id=f"{request_id}_2",
            user_id=current_user,
            session_id=session_id  # Same session
        )
        
        test_results["second_message"] = {
            "response_preview": response2.answer[:100] + "...",
            "session_id_returned": response2.session_id,
            "citations_count": len(response2.citations)
        }
        
        # Test 5: Check session state again
        session_info = memory_service.get_session_info(session_id)
        test_results["session_after_second"] = session_info
        
        # Test 6: Get chat history
        chat_history = memory_service.get_chat_history(session_id)
        test_results["chat_history"] = {
            "message_count": len(chat_history),
            "messages": []
        }
        
        for i, msg in enumerate(chat_history):
            if hasattr(msg, 'type'):
                test_results["chat_history"]["messages"].append({
                    "index": i,
                    "type": msg.type,
                    "content_preview": msg.content[:50] + "..."
                })
        
        # Test 7: Test with a new session (no context)
        new_session_id = str(uuid.uuid4())
        
        request3 = ChatRequest(
            query="What rights are you referring to?",  # This should not make sense without context
            user_id=current_user
        )
        
        response3 = await chat_pipeline(
            request=request3,
            request_id=f"{request_id}_3",
            user_id=current_user,
            session_id=new_session_id  # New session
        )
        
        test_results["new_session_test"] = {
            "response_preview": response3.answer[:100] + "...",
            "session_id": new_session_id,
            "should_lack_context": True
        }
        
        # Test 8: List all active sessions
        active_sessions = memory_service.list_active_sessions()
        test_results["active_sessions"] = active_sessions
        
        # Test 9: Session comparison
        test_results["comparison"] = {
            "original_session_messages": len(memory_service.get_chat_history(session_id)),
            "new_session_messages": len(memory_service.get_chat_history(new_session_id)),
            "total_active_sessions": len(active_sessions),
            "test_successful": len(memory_service.get_chat_history(session_id)) >= 4  # Should have 4+ messages
        }
        
        logger.bind(request_id=request_id, user_id=current_user).info(
            f"Session test completed successfully. Original session has {test_results['comparison']['original_session_messages']} messages"
        )
        
        return {
            "status": "success",
            "message": "Session management test completed",
            "test_results": test_results,
            "summary": {
                "sessions_created": 2,
                "messages_sent": 3,
                "session_continuity_working": test_results["comparison"]["test_successful"],
                "active_sessions_count": test_results["comparison"]["total_active_sessions"]
            }
        }
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Session test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Session test failed: {str(e)}")


@router.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
@langsmith_service.trace(
    name="get_chat_history_endpoint",
    run_type="retriever",
    metadata={"endpoint": "/chat/history", "resource": "session_history"}
)
async def get_chat_history(
    session_id: str,
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Get chat history for a specific session"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        logger.bind(request_id=request_id, user_id=current_user, session_id=session_id).info(
            "Chat history requested"
        )
        
        # Get chat session to verify user ownership
        if session_id not in memory_service.sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = memory_service.sessions[session_id]
        
        # Verify user owns this session
        if session.user_id != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        chat_history = memory_service.get_chat_history(session_id)
        
        # Convert messages to serializable format
        messages = []
        for msg in chat_history:
            messages.append({
                "type": msg.type,
                "content": msg.content,
                "timestamp": getattr(msg, 'timestamp', None)
            })
        
        return ChatHistoryResponse(
            session_id=session_id,
            messages=messages,
            total_messages=len(messages)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Error getting chat history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/chat/session/{session_id}")
@langsmith_service.trace(
    name="clear_chat_session_endpoint",
    run_type="tool",
    metadata={"endpoint": "/chat/session", "method": "DELETE"}
)
async def clear_chat_session(
    session_id: str,
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Clear a specific chat session"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        logger.bind(request_id=request_id, user_id=current_user, session_id=session_id).info(
            "Chat session clear requested"
        )
        
        # Verify session exists and user owns it
        if session_id not in memory_service.sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = memory_service.sessions[session_id]
        if session.user_id != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        memory_service.clear_session(session_id)
        
        return {"message": f"Session {session_id} cleared successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Error clearing session: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/chat/sessions", response_model=List[SessionInfo])
@langsmith_service.trace(
    name="get_user_sessions_endpoint",
    run_type="retriever",
    metadata={"endpoint": "/chat/sessions", "resource": "user_sessions"}
)
async def get_user_sessions(
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Get all active sessions for the current user"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        logger.bind(request_id=request_id, user_id=current_user).info(
            "User sessions requested"
        )
        
        user_sessions = []
        for session_id, session in memory_service.sessions.items():
            if session.user_id == current_user:
                message_count = len(session.memory.chat_memory.messages) if hasattr(session.memory, 'chat_memory') else 0
                
                user_sessions.append(SessionInfo(
                    session_id=session_id,
                    user_id=session.user_id,
                    created_at=session.created_at,
                    last_activity=session.last_activity,
                    message_count=message_count,
                    metadata=session.metadata
                ))
        
        return user_sessions
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Error getting user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/search", response_model=SearchResponse)
@langsmith_service.trace(
    name="search_documents_endpoint",
    run_type="retriever",
    metadata={"endpoint": "/search", "resource": "knowledge_base"}
)
async def search_legal_documents(
    query: str,
    max_results: int = 10,
    session_id: Optional[str] = None,
    fastapi_request: Request = None,
    current_user: str = Depends(get_current_user)
):
    """Enhanced search endpoint with session support"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4())) if fastapi_request else str(uuid.uuid4())
    
    try:
        if not query or len(query.strip()) == 0:
            raise ValidationError("Search query cannot be empty")
        
        if max_results < 1 or max_results > 50:
            raise ValidationError("max_results must be between 1 and 50")
        
        logger.bind(request_id=request_id, user_id=current_user, session_id=session_id).info(
            f"Document search request | Query: {query[:50]}... | Max results: {max_results}"
        )
        
        documents = await search_documents(
            query=query,
            max_results=max_results,
            request_id=request_id,
            user_id=current_user
        )
        
        return SearchResponse(
            query=query,
            total_results=len(documents),
            max_results=max_results,
            documents=documents,
            session_id=session_id
        )
        
    except ValidationError as e:
        logger.bind(request_id=request_id, user_id=current_user).warning(f"Search validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except KnowledgeBaseError as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Search knowledge base error: {str(e)}")
        raise HTTPException(status_code=503, detail="Knowledge base temporarily unavailable")
    
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"Unexpected error in search endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/kb/health")
@langsmith_service.trace(
    name="kb_health_check_endpoint",
    run_type="tool",
    metadata={"endpoint": "/kb/health", "check_type": "health"}
)
async def knowledge_base_health(
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Knowledge base health check endpoint"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        from app.services.bedrock_kb import BedrockKB

        kb = BedrockKB()
        health_status = kb.health_check()
        
        logger.bind(request_id=request_id, user_id=current_user).info(
            f"KB health check requested | Status: {health_status['status']}"
        )
        
        return health_status
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=current_user).error(f"KB health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "kb_id": None,
            "timestamp": None
        }


@router.get("/stats")
@langsmith_service.trace(
    name="get_stats_endpoint",
    run_type="tool",
    metadata={"endpoint": "/stats", "resource": "system_stats"}
)
async def get_chat_stats(
    fastapi_request: Request,
    current_user: str = Depends(get_current_user)
):
    """Chat statistics endpoint"""
    request_id = getattr(fastapi_request.state, 'request_id', str(uuid.uuid4()))
    
    logger.bind(request_id=request_id, user_id=current_user).info("Chat stats requested")
    
    # Get user's session count and total messages
    user_sessions = [s for s in memory_service.sessions.values() if s.user_id == current_user]
    total_messages = sum(len(s.memory.chat_memory.messages) for s in user_sessions if hasattr(s.memory, 'chat_memory'))
    
    return {
        "user": current_user,
        "active_sessions": len(user_sessions),
        "total_messages": total_messages,
        "global_sessions": len(memory_service.sessions),
        "available_endpoints": [
            "/v1/chat",
            "/v1/search", 
            "/v1/kb/health",
            "/v1/stats",
            "/v1/chat/history/{session_id}",
            "/v1/chat/session/{session_id}",
            "/v1/chat/sessions",
            "/v1/test-sessions",
            "/v1/test-streaming"
        ]
    }