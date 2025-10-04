# app/core/orchestrator.py

import time
import json
import uuid
from typing import Optional, List, AsyncGenerator
from loguru import logger

from app.models.request_models import ChatRequest
from app.models.response_models import ChatResponse, Citation
from app.services.bedrock_kb import BedrockKB
from app.services.bedrock_client import get_bedrock_client
from app.services.memory_service import memory_service
from app.services.streaming import streaming_service
from app.services.langsmith_service import langsmith_service
from app.services.prompt_service import prompt_service
from app.core.guardrails import apply_guardrails
from app.core.tools import lookup_statute
from app.core.error_handler import ValidationError
from app.config import settings


def _get_model_id_or_inference_profile():
    region = getattr(settings, 'AWS_REGION', 'us-east-1')
    custom_model = getattr(settings, 'BEDROCK_GENERATION_MODEL', None)
    
    if custom_model and custom_model.startswith(('us.', 'eu.', 'apac.', 'arn:aws:bedrock')):
        return custom_model
    
    if region.startswith('eu-'):
        return "eu.amazon.nova-pro-v1:0"
    elif region.startswith('ap-'):
        return "apac.amazon.nova-pro-v1:0"
    elif region.startswith('us-'):
        return "us.amazon.nova-pro-v1:0"
    else:
        return "eu.amazon.nova-pro-v1:0"


@langsmith_service.trace(
    name="chat_pipeline_streaming",
    run_type="chain",
    metadata={"service": "complai", "streaming": True}
)
async def chat_pipeline_streaming(
    request: ChatRequest, 
    request_id: str = None, 
    user_id: str = None,
    session_id: str = None
) -> AsyncGenerator[dict, None]:
    
    try:
        if not request.query or not request.query.strip():
            yield {"type": "error", "content": "Query cannot be empty", "session_id": session_id}
            return
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        chat_session = memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            memory_type="buffer_window",
            window_size=10
        )
        
        memory_variables = memory_service.get_memory_variables(session_id)
        chat_history = memory_variables.get("chat_history", [])
        
        # Check if we need KB context
        kb_context = ""
        if _should_use_kb(request.query):
            kb_context = await _get_kb_context(request.query, request_id, user_id)
        
        full_response = ""
        async for chunk_data in streaming_service.stream_response(
            query=request.query,
            chat_history=chat_history,
            kb_context=kb_context,
            session_id=session_id,
            request_id=request_id,
            user_id=user_id
        ):
            if chunk_data["type"] == "chunk":
                full_response += chunk_data["content"]
                yield chunk_data
            elif chunk_data["type"] == "complete":
                full_response = chunk_data["content"]
                memory_service.add_message(session_id, request.query, full_response)
                yield chunk_data
                break
            elif chunk_data["type"] == "error":
                yield chunk_data
                break
        
    except Exception as e:
        logger.error(f"Streaming pipeline error: {str(e)}")
        yield {
            "type": "error", 
            "content": "I encountered an error processing your request.",
            "session_id": session_id
        }


@langsmith_service.trace(
    name="chat_pipeline",
    run_type="chain",
    metadata={"service": "complai"}
)
async def chat_pipeline(
    request: ChatRequest, 
    request_id: str = None, 
    user_id: str = None,
    session_id: str = None
) -> ChatResponse:
    
    try:
        if not request.query or not request.query.strip():
            raise ValidationError("Query cannot be empty")
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        chat_session = memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            memory_type="buffer_window",
            window_size=10
        )
        
        memory_variables = memory_service.get_memory_variables(session_id)
        chat_history = memory_variables.get("chat_history", [])
        
        # Check if we need KB context
        kb_context = ""
        kb_citations = []
        if _should_use_kb(request.query):
            kb_context, kb_citations = await _get_kb_context_with_citations(
                request.query, request_id, user_id
            )
        
        # Generate response with KB context if available
        answer = await _generate_response(
            request.query,
            chat_history,
            kb_context,
            request_id,
            user_id,
            session_id
        )
        
        memory_service.add_message(session_id, request.query, answer)
        
        return ChatResponse(
            answer=answer,
            citations=kb_citations,
            tool_used="knowledge_base" if kb_context else None,
            session_id=session_id
        )
        
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Chat pipeline error: {str(e)}")
        return ChatResponse(
            answer="I encountered an error processing your request.",
            citations=[],
            tool_used=None,
            session_id=session_id
        )


def _should_use_kb(query: str) -> bool:
    """Simple check if query needs KB lookup"""
    kb_keywords = [
        "article", "section", "regulation", "requirement",
        "gdpr", "compliance", "legal", "specific", "exact"
    ]
    return any(keyword in query.lower() for keyword in kb_keywords)


async def _get_kb_context(query: str, request_id: str, user_id: str) -> str:
    """Get KB documents as context string"""
    try:
        kb = BedrockKB()
        results = kb.retrieve_documents(
            query=query,
            max_results=3,
            request_id=request_id,
            user_id=user_id
        )
        
        if not results:
            return ""
        
        context_parts = []
        for result in results:
            context_parts.append(f"Source: {result.source}\n{result.content[:800]}")
        
        return "\n\n".join(context_parts)
        
    except Exception as e:
        logger.error(f"KB lookup failed: {str(e)}")
        return ""


async def _get_kb_context_with_citations(
    query: str, 
    request_id: str, 
    user_id: str
) -> tuple[str, List[Citation]]:
    """Get KB documents as context string with citations"""
    try:
        kb = BedrockKB()
        results = kb.retrieve_documents(
            query=query,
            max_results=3,
            request_id=request_id,
            user_id=user_id
        )
        
        if not results:
            return "", []
        
        context_parts = []
        citations = []
        
        for result in results:
            context_parts.append(f"Source: {result.source}\n{result.content[:800]}")
            citations.append(
                Citation(
                    source=result.source,
                    snippet=result.content[:500] + "..." if len(result.content) > 500 else result.content
                )
            )
        
        return "\n\n".join(context_parts), citations
        
    except Exception as e:
        logger.error(f"KB lookup failed: {str(e)}")
        return "", []


@langsmith_service.trace(
    name="generate_response",
    run_type="llm",
    metadata={"model": "nova-pro", "provider": "bedrock"}
)
async def _generate_response(
    query: str,
    chat_history: list,
    kb_context: str,
    request_id: str,
    user_id: str,
    session_id: str
) -> str:
    """Generate response with optional KB context"""
    
    try:
        bedrock_client = get_bedrock_client()
        
        # Build messages with KB context injected into prompt
        messages = prompt_service.build_messages_with_history(
            query=query,
            chat_history=chat_history,
            kb_context=kb_context,
            max_history=6
        )
        
        model_id = _get_model_id_or_inference_profile()
        
        body = {
            "schemaVersion": "messages-v1",
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": 700,
                "temperature": 0.3
            }
        }
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract answer
        answer = ""
        if 'output' in response_body and 'message' in response_body['output']:
            message = response_body['output']['message']
            if 'content' in message and message['content']:
                first_content = message['content'][0]
                if 'text' in first_content:
                    answer = first_content['text']
        
        if not answer:
            answer = "I couldn't generate a response. Please try rephrasing your query."
        
        return apply_guardrails(answer)
        
    except Exception as e:
        logger.error(f"LLM generation failed: {str(e)}")
        return "I'm experiencing technical difficulties. Please try again later."


@langsmith_service.trace(
    name="search_documents",
    run_type="retriever",
    metadata={"source": "bedrock_kb"}
)
async def search_documents(
    query: str, 
    max_results: int = 10, 
    request_id: str = None, 
    user_id: str = None
) -> list:
    """Direct document search endpoint"""
    try:
        kb = BedrockKB()
        results = kb.retrieve_documents(
            query=query,
            max_results=max_results,
            request_id=request_id,
            user_id=user_id
        )
        
        documents = []
        for result in results:
            documents.append({
                "content": result.content[:1000] + "..." if len(result.content) > 1000 else result.content,
                "source": result.source,
                "score": result.score,
                "metadata": result.metadata
            })
        
        return documents
        
    except Exception as e:
        logger.error(f"Document search failed: {str(e)}")
        return []