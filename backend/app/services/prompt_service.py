from typing import Dict, List, Optional
from loguru import logger
from app.config import settings

try:
    from langsmith import Client
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    logger.error("LangSmith not installed! Install with: pip install langsmith")
    raise ImportError("LangSmith is required for prompt management")


class PromptService:
    def __init__(self):
        self.client = None
        self.prompt_name = getattr(settings, 'LANGSMITH_PROMPT_NAME', None)
        
        if not self.prompt_name:
            logger.error("LANGSMITH_PROMPT_NAME not configured!")
            raise ValueError("LANGSMITH_PROMPT_NAME must be set (e.g., 'compliance-prompt:71222')")
        
        try:
            api_key = settings.LANGCHAIN_API_KEY
            if not api_key:
                raise ValueError("LANGCHAIN_API_KEY not set")
                
            self.client = Client(api_key=api_key)
            logger.info(f"PromptService initialized with prompt: {self.prompt_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LangSmith Client: {e}")
            raise
    
    def get_prompt(self, context: str = "") -> str:

        try:
            prompt_obj = self.client.pull_prompt(self.prompt_name, include_model=False)
            logger.debug(f"Pulled prompt from LangSmith: {self.prompt_name}")
            
            prompt_text = None
            
            if hasattr(prompt_obj, 'template'):
                # PromptTemplate object
                prompt_text = prompt_obj.template
            elif hasattr(prompt_obj, 'messages') and prompt_obj.messages:
                # ChatPromptTemplate - get first message content
                first_message = prompt_obj.messages[0]
                if hasattr(first_message, 'prompt') and hasattr(first_message.prompt, 'template'):
                    prompt_text = first_message.prompt.template
                elif hasattr(first_message, 'content'):
                    prompt_text = first_message.content
            elif isinstance(prompt_obj, str):
                prompt_text = prompt_obj
            else:
                logger.warning(f"Unknown prompt object type: {type(prompt_obj)}")
                prompt_text = str(prompt_obj)
            
            if not prompt_text:
                raise ValueError("Could not extract prompt text from LangSmith response")
            
            if "{context}" in prompt_text:
                return prompt_text.replace("{context}", context if context else "")
            
            return prompt_text
                
        except Exception as e:
            logger.error(f"Failed to pull prompt from LangSmith: {e}")
            raise RuntimeError(f"Cannot load prompt from LangSmith: {e}")
    
    def build_messages_with_history(
        self,
        query: str,
        chat_history: List,
        kb_context: str = "",
        max_history: int = 6
    ) -> List[Dict]:

        
        system_prompt = self.get_prompt(context=kb_context)
        
        messages = []
        recent_history = chat_history[-max_history:] if len(chat_history) > max_history else chat_history
        
        logger.debug(f"Building messages with {len(recent_history)} history messages")
        
        # Add chat history
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
        else:
            messages.append({
                "role": "user", 
                "content": [{"text": f"{system_prompt}\n\nUser Question: {query}"}]
            })
        
        return messages


prompt_service = PromptService()