# app/core/orchestrator.py

import time
import json
import uuid
import re
from typing import Optional, List, AsyncGenerator
from loguru import logger

from app.models.request_models import ChatRequest
from app.models.response_models import ChatResponse, Citation
from app.services.bedrock_kb import BedrockKB, GenerationResult, KnowledgeBaseError
from app.services.bedrock_client import get_bedrock_client
from app.services.memory_service import memory_service
from app.services.streaming import streaming_service
from app.services.langsmith_service import langsmith_service
from app.core.guardrails import apply_guardrails
from app.core.tools import lookup_statute
from app.core.error_handler import ValidationError
from app.core.logging_config import LoggingConfig
from app.config import settings


def _get_model_id_or_inference_profile():
    
    region = getattr(settings, 'AWS_REGION', 'us-east-1')
    custom_model = getattr(settings, 'BEDROCK_GENERATION_MODEL', None)
    
    logger.info(f"Region detected: {region}, Custom model setting: {custom_model}")
    
    if custom_model:
        if custom_model.startswith(('us.', 'eu.', 'apac.', 'arn:aws:bedrock')):
            logger.info(f"Using custom inference profile: {custom_model}")
            return custom_model
        else:
            logger.warning(f"Custom model {custom_model} is not an inference profile, using regional profile instead")
    
    if region.startswith('eu-'):
        profile = "eu.amazon.nova-pro-v1:0"
    elif region.startswith('ap-'):
        profile = "apac.amazon.nova-pro-v1:0"
    elif region.startswith('us-'):
        profile = "us.amazon.nova-pro-v1:0"
    else:
        profile = "eu.amazon.nova-pro-v1:0"
    
    logger.info(f"Using Nova Pro inference profile: {profile}")
    return profile


@langsmith_service.trace(
    name="chat_pipeline_streaming",
    run_type="chain",
    metadata={"service": "complai", "streaming": True, "version": "1.0"}
)
async def chat_pipeline_streaming(
    request: ChatRequest, 
    request_id: str = None, 
    user_id: str = None,
    session_id: str = None
) -> AsyncGenerator[dict, None]:
    start_time = time.time()
    
    try:
        if not request.query or not request.query.strip():
            yield {"type": "error", "content": "Query cannot be empty", "session_id": session_id}
            return
        
        if len(request.query) > 10000:
            yield {"type": "error", "content": "Query too long (max 10000 characters)", "session_id": session_id}
            return
        
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Generated new session ID for streaming: {session_id}"
            )
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Starting streaming pipeline | User: {request.user_id}"
        )
        
        chat_session = memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            memory_type="buffer_window",
            window_size=10,
            metadata={"jurisdiction": getattr(request, 'jurisdiction', None)}
        )
        
        memory_variables = memory_service.get_memory_variables(session_id)
        chat_history = memory_variables.get("chat_history", [])
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Retrieved chat history with {len(chat_history)} messages"
        )
        
        full_response = ""
        async for chunk_data in streaming_service.stream_response(
            query=request.query,
            chat_history=chat_history,
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
                
                citations, enhanced_response = await streaming_service.enhance_with_kb_lookup(
                    query=request.query,
                    initial_response=full_response,
                    request_id=request_id,
                    user_id=user_id
                )
                
                if enhanced_response != full_response:
                    logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
                        f"Response enhanced with {len(citations)} citations"
                    )
                    memory_service.add_message(session_id, request.query, enhanced_response, replace_last=True)
                    
                    yield {
                        "type": "complete",
                        "content": enhanced_response,
                        "citations": [citation.dict() for citation in citations],
                        "session_id": session_id
                    }
                else:
                    yield chunk_data
                break
            elif chunk_data["type"] == "error":
                yield chunk_data
                break
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Streaming pipeline completed | Response length: {len(full_response)} | Duration: {time.time() - start_time:.2f}s"
        )
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
            f"Unexpected error in streaming pipeline: {str(e)}"
        )
        yield {
            "type": "error", 
            "content": "I apologize, but I encountered an unexpected error while processing your request.",
            "session_id": session_id
        }


@langsmith_service.trace(
    name="chat_pipeline",
    run_type="chain",
    metadata={"service": "complai", "streaming": False, "version": "1.0"}
)
async def chat_pipeline(
    request: ChatRequest, 
    request_id: str = None, 
    user_id: str = None,
    session_id: str = None
) -> ChatResponse:
    start_time = time.time()
    
    try:
        if not request.query or not request.query.strip():
            raise ValidationError("Query cannot be empty")
        
        if len(request.query) > 10000:
            raise ValidationError("Query too long (max 10000 characters)")
        
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Generated new session ID: {session_id}"
            )
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Starting LLM-first pipeline | User: {request.user_id}"
        )
        
        chat_session = memory_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            memory_type="buffer_window",
            window_size=10,
            metadata={"jurisdiction": getattr(request, 'jurisdiction', None)}
        )
        
        memory_variables = memory_service.get_memory_variables(session_id)
        chat_history = memory_variables.get("chat_history", [])
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Retrieved chat history with {len(chat_history)} messages"
        )
        
        llm_result = await _generate_llm_response_with_tools(
            request, request_id, user_id, session_id, chat_history
        )
        
        memory_service.add_message(session_id, request.query, llm_result.answer)
        llm_result.session_id = session_id
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Added message pair to session memory"
        )
        
        return llm_result
        
    except ValidationError as e:
        logger.bind(request_id=request_id, user_id=user_id).warning(f"Validation error: {str(e)}")
        raise e
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id).error(f"Unexpected error in chat pipeline: {str(e)}")
        return ChatResponse(
            answer="I apologize, but I encountered an unexpected error while processing your request. Please try again later.",
            citations=[],
            tool_used=None,
            session_id=session_id
        )


@langsmith_service.trace(
    name="generate_llm_response",
    run_type="llm",
    metadata={"model": "nova-pro", "provider": "bedrock"}
)
async def _generate_llm_response_with_tools(
    request: ChatRequest, 
    request_id: str, 
    user_id: str,
    session_id: str,
    chat_history: list
) -> ChatResponse:
    
    try:
        bedrock_client = get_bedrock_client()
        
        system_prompt = _get_tool_aware_system_prompt()
        messages = _build_tool_aware_messages(request.query, chat_history, system_prompt)
        model_id = _get_model_id_or_inference_profile()
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Using model/inference profile: {model_id}"
        )
        
        body = {
            "schemaVersion": "messages-v1",
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": 700,
                "temperature": 0.3
            }
        }
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Making tool-aware LLM call | Model: {model_id} | History length: {len(chat_history)}"
        )
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response['body'].read())
        
        answer = ""
        if 'output' in response_body and 'message' in response_body['output']:
            message = response_body['output']['message']
            if 'content' in message and message['content']:
                first_content = message['content'][0]
                if 'text' in first_content:
                    answer = first_content['text']
        
        if not answer:
            if 'content' in response_body and response_body['content']:
                if isinstance(response_body['content'], list) and response_body['content']:
                    first_item = response_body['content'][0]
                    if isinstance(first_item, dict) and 'text' in first_item:
                        answer = first_item['text']
                    elif isinstance(first_item, str):
                        answer = first_item
            elif 'message' in response_body and 'content' in response_body['message']:
                answer = response_body['message']['content']
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"Extracted answer: {answer[:100]}..." if answer else "No answer extracted"
        )
        
        if not answer:
            answer = "I apologize, but I couldn't generate a proper response to your question. Please try rephrasing your query."
        
        kb_citations = []
        tool_used = None
        
        if _should_use_kb_lookup(answer, request.query):
            logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
                "LLM indicated need for KB lookup - retrieving documents"
            )
            
            kb_citations, enhanced_answer = await _perform_kb_lookup_and_enhance(
                request.query, answer, request_id, user_id
            )
            
            if enhanced_answer:
                answer = enhanced_answer
                tool_used = "knowledge_base_lookup"
        
        if "statute" in request.query.lower() or "section" in request.query.lower():
            try:
                if not tool_used:
                    tool_used = "lookup_statute"
                statute_info = lookup_statute.run(request.query)
                if statute_info and statute_info != "Statute not found":
                    answer += f"\n\n**Additional Statute Information:**\n{statute_info}"
            except Exception as e:
                logger.bind(request_id=request_id, user_id=user_id).warning(
                    f"Statute lookup failed: {str(e)}"
                )
        
        safe_answer = apply_guardrails(answer)
        
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
            f"LLM response completed | Model: {model_id} | Tool used: {tool_used} | KB citations: {len(kb_citations)}"
        )
        
        return ChatResponse(
            answer=safe_answer,
            citations=kb_citations,
            tool_used=tool_used,
            session_id=session_id
        )
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
            f"LLM generation failed: {str(e)}"
        )
        return ChatResponse(
            answer="I apologize, but I'm currently experiencing technical difficulties. Please try again later or contact support if the issue persists.",
            citations=[],
            tool_used=None,
            session_id=session_id
        )


def _should_use_kb_lookup(llm_answer: str, query: str) -> bool:
    """Determine if KB lookup is needed based on LLM response and query"""
    
    kb_indicators = [
        "I need to search for",
        "Let me look up",
        "I should check the knowledge base",
        "Let me find specific documents",
        "[KB_LOOKUP_NEEDED]",
        "I need to retrieve"
    ]
    
    for indicator in kb_indicators:
        if indicator.lower() in llm_answer.lower():
            return True
    
    specific_requests = [
        "what does article",
        "section",
        "specific regulation",
        "exact wording",
        "official text",
        "compliance requirements for",
        "detailed requirements",
        "specific obligations"
    ]
    
    for request_type in specific_requests:
        if request_type.lower() in query.lower():
            return True
    
    vague_responses = [
        "generally requires",
        "typically involves",
        "usually includes",
        "in general",
        "I don't have specific"
    ]
    
    for vague in vague_responses:
        if vague.lower() in llm_answer.lower():
            return True
    
    return False


@langsmith_service.trace(
    name="kb_lookup_and_enhance",
    run_type="retriever",
    metadata={"source": "bedrock_kb"}
)
async def _perform_kb_lookup_and_enhance(
    query: str, 
    initial_answer: str, 
    request_id: str, 
    user_id: str
) -> tuple[List[Citation], str]:
    """Perform KB lookup and enhance the LLM answer with retrieved documents"""
    
    try:
        kb = BedrockKB()
        
        results = kb.retrieve_documents(
            query=query,
            max_results=5,
            request_id=request_id,
            user_id=user_id
        )
        
        if not results:
            return [], initial_answer
        
        citations = []
        for result in results:
            citations.append(
                Citation(
                    source=result.source,
                    snippet=result.content[:500] + "..." if len(result.content) > 500 else result.content
                )
            )
        
        enhanced_answer = await _enhance_answer_with_kb_results(
            query, initial_answer, results, request_id, user_id
        )
        
        return citations, enhanced_answer
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id).error(
            f"KB lookup failed: {str(e)}"
        )
        return [], initial_answer


@langsmith_service.trace(
    name="enhance_with_kb_results",
    run_type="llm",
    metadata={"model": "nova-pro", "task": "enhancement"}
)
async def _enhance_answer_with_kb_results(
    query: str,
    initial_answer: str, 
    kb_results: List,
    request_id: str,
    user_id: str
) -> str:
    """Use LLM to enhance the initial answer with KB results"""
    
    try:
        bedrock_client = get_bedrock_client()
        
        kb_context = "\n\n".join([
            f"Document: {result.source}\nContent: {result.content[:800]}"
            for result in kb_results[:3]
        ])
        
        enhancement_prompt = f"""Here is my initial response to a user question:

INITIAL RESPONSE:
{initial_answer}

ADDITIONAL DOCUMENTS FOUND:
{kb_context}

USER QUESTION:
{query}

Please enhance my initial response by incorporating relevant information from the additional documents. Keep the response natural and conversational. Only add information that is directly relevant to the user's question. If the documents don't add valuable information, just return the initial response unchanged.

ENHANCED RESPONSE:"""

        model_id = _get_model_id_or_inference_profile()
        
        logger.bind(request_id=request_id, user_id=user_id).info(
            f"Enhancement using model/inference profile: {model_id}"
        )

        body = {
            "schemaVersion": "messages-v1",
            "messages": [{"role": "user", "content": [{"text": enhancement_prompt}]}],
            "inferenceConfig": {
                "maxTokens": 500,
                "temperature": 0.2
            }
        }
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response['body'].read())
        
        enhanced_answer = ""
        if 'output' in response_body and 'message' in response_body['output']:
            message = response_body['output']['message']
            if 'content' in message and message['content']:
                first_content = message['content'][0]
                if 'text' in first_content:
                    enhanced_answer = first_content['text']
        
        if not enhanced_answer:
            if 'content' in response_body and response_body['content']:
                if isinstance(response_body['content'], list) and response_body['content']:
                    first_item = response_body['content'][0]
                    if isinstance(first_item, dict) and 'text' in first_item:
                        enhanced_answer = first_item['text']
        
        return enhanced_answer if enhanced_answer else initial_answer
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id).warning(
            f"Answer enhancement failed: {str(e)}"
        )
        return initial_answer


def _get_tool_aware_system_prompt() -> str:
    """System prompt that makes LLM aware of available tools"""
    
    base_prompt = """You are a helpful AI assistant specialized in EU compliance regulations.

You have access to the following tools when needed:
1. Knowledge Base: Can search for specific EU legal documents and regulations

When answering:
1. First provide your general knowledge response
2. If you need specific GDPR or EU compliance details, use the Knowledge Base 
3. Be conversational and helpful
4. Consider previous conversation context
5. Be clear about limitations of your knowledge

"""
    return base_prompt


def _build_tool_aware_messages(query: str, chat_history: list, system_prompt: str) -> list:
    """Build conversation messages with tool awareness for Nova API format"""
    
    messages = []
    recent_history = chat_history[-6:] if len(chat_history) > 6 else chat_history
    
    logger.info(f"Processing {len(recent_history)} messages from chat history")
    
    for msg in recent_history:
        if hasattr(msg, 'type'):
            if msg.type == 'human':
                messages.append({
                    "role": "user", 
                    "content": [{"text": msg.content}]
                })
                logger.debug(f"Added user message: {msg.content[:50]}...")
            elif msg.type == 'ai':
                messages.append({
                    "role": "assistant", 
                    "content": [{"text": msg.content}]
                })
                logger.debug(f"Added assistant message: {msg.content[:50]}...")
    
    if messages:
        messages.append({
            "role": "user", 
            "content": [{"text": query}]
        })
        logger.info(f"Added current query to conversation with {len(messages)-1} previous messages")
    else:
        messages.append({
            "role": "user", 
            "content": [{"text": f"{system_prompt}\n\nUser Question: {query}\n\nPlease provide a helpful response:"}]
        })
        logger.info("Added current query as first message with system prompt")
    
    return messages


@langsmith_service.trace(
    name="search_documents",
    run_type="retriever",
    metadata={"source": "bedrock_kb", "endpoint": "direct_search"}
)
async def search_documents(
    query: str, 
    max_results: int = 10, 
    request_id: str = None, 
    user_id: str = None
) -> list:
    """Direct document search endpoint"""
    try:
        logger.bind(request_id=request_id, user_id=user_id).info(
            f"Direct document search | Query: {query[:50]}... | Max results: {max_results}"
        )
        
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
        
        logger.bind(request_id=request_id, user_id=user_id).info(
            f"Direct document search completed | Found: {len(documents)} results"
        )
        
        return documents
        
    except Exception as e:
        logger.bind(request_id=request_id, user_id=user_id).error(f"Document search failed: {str(e)}")
        return []