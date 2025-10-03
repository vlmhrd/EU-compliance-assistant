# app/core/guardrails.py - No disclaimers version
import time
from typing import Dict, Optional
from loguru import logger
from botocore.exceptions import ClientError

from app.config import settings
from app.services.bedrock_client import get_bedrock_client


class BedrockGuardrails:
    
    def __init__(self):
        self.guardrail_id = settings.BEDROCK_GUARDRAIL_ID
        self.guardrail_version = getattr(settings, 'BEDROCK_GUARDRAIL_VERSION', 'DRAFT')
        self.is_enabled = bool(self.guardrail_id and self.guardrail_id.strip())
        
        if self.is_enabled:
            try:
                self.bedrock_client = get_bedrock_client()
                logger.info(f"Bedrock Guardrails enabled: {self.guardrail_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize Bedrock Guardrails: {e}")
                self.is_enabled = False
        else:
            logger.info("Bedrock Guardrails disabled - no guardrail ID configured")

    def apply_guardrails(
        self, 
        answer: str, 
        user_input: str = None,
        request_id: str = None,
        user_id: str = None
    ) -> str:
        
        if not self.is_enabled:
            return answer  # Return content as-is
        
        try:
            result = self._apply_bedrock_guardrails(answer, user_input, request_id, user_id)
            
            if result['blocked']:
                logger.bind(request_id=request_id, user_id=user_id).warning(
                    "Content blocked by Bedrock Guardrails"
                )
                return self._generate_blocked_response()
            
            filtered_answer = result.get('filtered_content', answer)
            return filtered_answer
            
        except Exception as e:
            logger.bind(request_id=request_id, user_id=user_id).error(
                f"Guardrails error: {e}"
            )
            # Return original content on error
            return answer

    def _apply_bedrock_guardrails(
        self, 
        content: str, 
        user_input: str = None,
        request_id: str = None,
        user_id: str = None
    ) -> Dict:
        
        try:
            request_params = {
                'guardrailIdentifier': self.guardrail_id,
                'guardrailVersion': self.guardrail_version,
                'source': 'OUTPUT',
                'content': [{'text': {'text': content}}]
            }
            
            response = self.bedrock_client.apply_guardrail(**request_params)
            
            action = response.get('action', 'NONE')
            outputs = response.get('outputs', [])
            
            result = {
                'blocked': action == 'GUARDRAIL_INTERVENED',
                'action': action,
                'filtered_content': content  # Default to original
            }
            
            if outputs and len(outputs) > 0:
                output_text = outputs[0].get('text')
                if output_text:
                    result['filtered_content'] = output_text
            
            return result
            
        except ClientError as e:
            logger.bind(request_id=request_id, user_id=user_id).error(
                f"Bedrock Guardrails error: {e.response['Error']['Code']}"
            )
            return {'blocked': False, 'error': str(e), 'filtered_content': content}

    def _generate_blocked_response(self) -> str:
        return (
            "I cannot provide a response to this query due to content policy restrictions. "
            "Please rephrase your question or consult appropriate resources for guidance."
        )

    def health_check(self) -> Dict:
        if not self.is_enabled:
            return {
                "status": "disabled",
                "guardrail_id": None,
                "message": "No guardrail configured - content returned as-is"
            }
        
        try:
            test_result = self._apply_bedrock_guardrails("This is a test message.")
            
            return {
                "status": "healthy",
                "guardrail_id": self.guardrail_id,
                "version": self.guardrail_version,
                "test_successful": not test_result.get('error')
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "guardrail_id": self.guardrail_id,
                "error": str(e)
            }


_guardrails_instance = None

def get_guardrails():
    global _guardrails_instance
    if _guardrails_instance is None:
        _guardrails_instance = BedrockGuardrails()
    return _guardrails_instance

def apply_guardrails(
    answer: str, 
    user_input: str = None, 
    request_id: str = None, 
    user_id: str = None
) -> str:
    guardrails = get_guardrails()
    return guardrails.apply_guardrails(answer, user_input, request_id, user_id)