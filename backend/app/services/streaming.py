# app/services/streaming.py

import json
import time
from typing import AsyncGenerator, Optional, List
from loguru import logger

from app.models.request_models import ChatRequest
from app.models.response_models import Citation
from app.services.bedrock_client import get_bedrock_client
from app.services.bedrock_kb import BedrockKB
from app.services.langsmith_service import langsmith_service
from app.core.guardrails import apply_guardrails


class StreamingService:
    
    def __init__(self):
        self.bedrock_client = get_bedrock_client()
        
    def _get_model_id_or_inference_profile(self) -> str:
        from app.config import settings
        
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
    
    def _build_messages(self, query: str, chat_history: list, system_prompt: str) -> list:
        
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
                elif msg.type == 'ai':
                    messages.append({
                        "role": "assistant", 
                        "content": [{"text": msg.content}]
                    })
        
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
        name="bedrock_stream_response",
        run_type="llm",
        metadata={"streaming": True, "model": "nova-pro", "provider": "bedrock"}
    )
    async def stream_response(
        self,
        query: str,
        chat_history: list,
        session_id: str,
        request_id: str = None,
        user_id: str = None
    ) -> AsyncGenerator[dict, None]:
        
        try:
            system_prompt = """You are a helpful AI assistant specialized in EU compliance regulations. Be clear and concise, don't provide information that was not asked.

You have access to the following tools when needed:
1. Knowledge Base: Can search for specific EU legal documents and regulations

When answering:
1. First provide your general knowledge response. BE CONCISE.
2. If you need specific GDPR or EU compliance details, use the Knowledge Base 
3. Be conversational and helpful
4. Consider previous conversation context
5. Be clear about limitations of your knowledge"""

            messages = self._build_messages(query, chat_history, system_prompt)
            model_id = self._get_model_id_or_inference_profile()
            
            logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
                f"Starting streaming LLM call | Model: {model_id} | History length: {len(chat_history)}"
            )
            
            body = {
                "schemaVersion": "messages-v1",
                "messages": messages,
                "inferenceConfig": {
                    "maxTokens": 1000,
                    "temperature": 0.3
                }
            }
            
            response = self.bedrock_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            full_response = ""
            chunk_count = 0
            
            stream = response.get('body')
            if not stream:
                logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
                    "No stream body received from Bedrock"
                )
                yield {
                    "type": "error",
                    "content": "No response stream available",
                    "session_id": session_id
                }
                return
            
            logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
                "Processing streaming response events"
            )
            
            for event in stream:
                chunk = event.get('chunk')
                if not chunk:
                    continue
                    
                try:
                    chunk_data = json.loads(chunk.get('bytes').decode())
                    chunk_count += 1
                    
                    logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                        f"Chunk {chunk_count}: {list(chunk_data.keys())}"
                    )
                    
                    if 'messageStart' in chunk_data:
                        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                            "Stream started"
                        )
                        continue
                        
                    elif 'contentBlockStart' in chunk_data:
                        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                            "Content block started"
                        )
                        continue
                        
                    elif 'contentBlockDelta' in chunk_data:
                        delta = chunk_data['contentBlockDelta'].get('delta', {})
                        if 'text' in delta:
                            text_chunk = delta['text']
                            full_response += text_chunk
                            
                            logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                                f"Text chunk: '{text_chunk[:50]}...'"
                            )
                            
                            yield {
                                "type": "chunk",
                                "content": text_chunk,
                                "session_id": session_id
                            }
                    
                    elif 'contentBlockStop' in chunk_data:
                        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                            "Content block stopped"
                        )
                        continue
                        
                    elif 'messageStop' in chunk_data:
                        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).info(
                            f"Stream completed | Chunks processed: {chunk_count} | Response length: {len(full_response)}"
                        )
                        
                        safe_response = apply_guardrails(full_response)
                        
                        yield {
                            "type": "complete",
                            "content": safe_response,
                            "session_id": session_id
                        }
                        return
                    
                    else:
                        logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).debug(
                            f"Unknown chunk type: {list(chunk_data.keys())}"
                        )
                        
                except json.JSONDecodeError as e:
                    logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).warning(
                        f"Failed to parse streaming chunk: {str(e)}"
                    )
                    continue
                except Exception as e:
                    logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
                        f"Error processing chunk: {str(e)}"
                    )
                    continue
            
            if full_response:
                logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).warning(
                    f"Stream ended without messageStop | Chunks: {chunk_count} | Response length: {len(full_response)}"
                )
                safe_response = apply_guardrails(full_response)
                yield {
                    "type": "complete",
                    "content": safe_response,
                    "session_id": session_id
                }
            else:
                logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
                    f"No response content after {chunk_count} chunks"
                )
                yield {
                    "type": "error",
                    "content": "No response generated from stream",
                    "session_id": session_id
                }
        
        except Exception as e:
            logger.bind(request_id=request_id, user_id=user_id, session_id=session_id).error(
                f"Streaming failed: {str(e)}"
            )
            yield {
                "type": "error",
                "content": f"Streaming error: {str(e)}",
                "session_id": session_id
            }
    
    @langsmith_service.trace(
        name="enhance_with_kb_lookup",
        run_type="chain",
        metadata={"source": "bedrock_kb", "task": "enhancement"}
    )
    async def enhance_with_kb_lookup(
        self,
        query: str,
        initial_response: str,
        request_id: str = None,
        user_id: str = None
    ) -> tuple[List[Citation], str]:
        
        try:
            if not self._should_use_kb_lookup(initial_response, query):
                return [], initial_response
            
            logger.bind(request_id=request_id, user_id=user_id).info(
                "Performing KB lookup for response enhancement"
            )
            
            kb = BedrockKB()
            results = kb.retrieve_documents(
                query=query,
                max_results=5,
                request_id=request_id,
                user_id=user_id
            )
            
            if not results:
                return [], initial_response
            
            citations = []
            for result in results:
                citations.append(
                    Citation(
                        source=result.source,
                        snippet=result.content[:500] + "..." if len(result.content) > 500 else result.content
                    )
                )
            
            enhanced_response = await self._enhance_response_with_kb(
                query, initial_response, results, request_id, user_id
            )
            
            return citations, enhanced_response
            
        except Exception as e:
            logger.bind(request_id=request_id, user_id=user_id).error(
                f"KB enhancement failed: {str(e)}"
            )
            return [], initial_response
    
    def _should_use_kb_lookup(self, response: str, query: str) -> bool:
        
        kb_indicators = [
            "I need to search for",
            "Let me look up",
            "I should check the knowledge base",
            "Let me find specific documents",
            "[KB_LOOKUP_NEEDED]",
            "I need to retrieve"
        ]
        
        for indicator in kb_indicators:
            if indicator.lower() in response.lower():
                return True
        
        specific_requests = [
            "what does article",
            "section",
            "specific regulation",
            "exact wording",
            "official text",
            "compliance requirements for",
            "detailed requirements"
        ]
        
        for request_type in specific_requests:
            if request_type.lower() in query.lower():
                return True
        
        return False
    
    @langsmith_service.trace(
        name="enhance_response_with_kb",
        run_type="llm",
        metadata={"model": "nova-pro", "task": "kb_enhancement"}
    )
    async def _enhance_response_with_kb(
        self,
        query: str,
        initial_response: str,
        kb_results: List,
        request_id: str,
        user_id: str
    ) -> str:
        
        try:
            kb_context = "\n\n".join([
                f"Document: {result.source}\nContent: {result.content[:800]}"
                for result in kb_results[:3]
            ])
            
            enhancement_prompt = f"""Here is my initial response to a user question:

INITIAL RESPONSE:
{initial_response}

ADDITIONAL DOCUMENTS FOUND:
{kb_context}

USER QUESTION:
{query}

Please enhance my initial response by incorporating relevant information from the additional documents. Keep the response natural and conversational. Only add information that is directly relevant to the user's question.

ENHANCED RESPONSE:"""

            model_id = self._get_model_id_or_inference_profile()
            
            body = {
                "schemaVersion": "messages-v1",
                "messages": [{"role": "user", "content": [{"text": enhancement_prompt}]}],
                "inferenceConfig": {
                    "maxTokens": 500,
                    "temperature": 0.2
                }
            }
            
            response = self.bedrock_client.invoke_model(
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
            
            return enhanced_answer if enhanced_answer else initial_response
            
        except Exception as e:
            logger.bind(request_id=request_id, user_id=user_id).warning(
                f"Response enhancement failed: {str(e)}"
            )
            return initial_response


streaming_service = StreamingService()