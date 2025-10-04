# app/services/streaming.py

import json
from typing import AsyncGenerator, List
from loguru import logger

from app.services.bedrock_client import get_bedrock_client
from app.services.langsmith_service import langsmith_service
from app.services.prompt_service import prompt_service
from app.core.guardrails import apply_guardrails
from app.config import settings


class StreamingService:
    
    def __init__(self):
        self.bedrock_client = get_bedrock_client()
        
    def _get_model_id_or_inference_profile(self) -> str:
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
        name="bedrock_stream_response",
        run_type="llm",
        metadata={"streaming": True, "model": "nova-pro"}
    )
    async def stream_response(
        self,
        query: str,
        chat_history: list,
        kb_context: str,
        session_id: str,
        request_id: str = None,
        user_id: str = None
    ) -> AsyncGenerator[dict, None]:
        
        try:
            # Build messages with KB context injected into prompt
            messages = prompt_service.build_messages_with_history(
                query=query,
                chat_history=chat_history,
                kb_context=kb_context,
                max_history=6
            )
            
            model_id = self._get_model_id_or_inference_profile()
            
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
            
            stream = response.get('body')
            if not stream:
                yield {
                    "type": "error",
                    "content": "No response stream available",
                    "session_id": session_id
                }
                return
            
            for event in stream:
                chunk = event.get('chunk')
                if not chunk:
                    continue
                    
                try:
                    chunk_data = json.loads(chunk.get('bytes').decode())
                    
                    if 'contentBlockDelta' in chunk_data:
                        delta = chunk_data['contentBlockDelta'].get('delta', {})
                        if 'text' in delta:
                            text_chunk = delta['text']
                            full_response += text_chunk
                            
                            yield {
                                "type": "chunk",
                                "content": text_chunk,
                                "session_id": session_id
                            }
                    
                    elif 'messageStop' in chunk_data:
                        safe_response = apply_guardrails(full_response)
                        
                        yield {
                            "type": "complete",
                            "content": safe_response,
                            "session_id": session_id
                        }
                        return
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Chunk processing error: {str(e)}")
                    continue
            
            # Stream ended
            if full_response:
                safe_response = apply_guardrails(full_response)
                yield {
                    "type": "complete",
                    "content": safe_response,
                    "session_id": session_id
                }
            else:
                yield {
                    "type": "error",
                    "content": "No response generated",
                    "session_id": session_id
                }
        
        except Exception as e:
            logger.error(f"Streaming failed: {str(e)}")
            yield {
                "type": "error",
                "content": f"Streaming error: {str(e)}",
                "session_id": session_id
            }


streaming_service = StreamingService()