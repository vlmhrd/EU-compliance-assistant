# app/services/memory_service.py
from typing import Optional, Dict, Any, List
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.memory.chat_memory import BaseChatMemory
import json
import time
from dataclasses import dataclass
from loguru import logger
from requests import session

from app.config import settings
from app.services.langsmith_service import langsmith_service


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    created_at: float
    last_activity: float
    memory: BaseChatMemory
    metadata: Dict[str, Any]


class ChatMemoryService:
    
    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.cleanup_interval = 3600  # 1 hour
        self.session_timeout = 7200   # 2 hours
        self.max_sessions = 1000      # Memory limit
        
        logger.info("Initialized ChatMemoryService")
    
    @langsmith_service.trace(
        name="memory_get_or_create_session",
        run_type="tool",
        metadata={"operation": "session_management", "service": "memory"}
    )
    def get_or_create_session(
        self, 
        session_id: str, 
        user_id: str,
        memory_type: str = "buffer_window",
        **kwargs
    ) -> ChatSession:
        
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_activity = time.time()
            logger.debug(f"Retrieved existing session: {session_id} with {len(session.memory.chat_memory.messages)} messages")
            return session
        
        memory = self._create_memory(memory_type, **kwargs)
        
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            created_at=time.time(),
            last_activity=time.time(),
            memory=memory,
            metadata=kwargs.get('metadata', {})
        )
        
        self.sessions[session_id] = session
        self._cleanup_old_sessions()
        
        logger.info(f"Created new chat session: {session_id} for user: {user_id} | Type: {memory_type}")
        return session
    
    @langsmith_service.trace(
        name="memory_create_memory",
        run_type="tool",
        metadata={"operation": "memory_initialization"}
    )
    def _create_memory(self, memory_type: str, **kwargs) -> BaseChatMemory:

        if memory_type == "buffer_window":
            memory = ConversationBufferWindowMemory(
                k=kwargs.get('window_size', 10),  # Keep last 10 exchanges
                return_messages=True,
                memory_key="chat_history"
            )
            logger.debug(f"Created buffer window memory with k={kwargs.get('window_size', 10)}")
            return memory
        
        else:
            memory = ConversationBufferWindowMemory(
                k=10,
                return_messages=True,
                memory_key="chat_history"
            )
            logger.debug("Created default buffer window memory")
            return memory
    
    @langsmith_service.trace(
        name="memory_add_message",
        run_type="tool",
        metadata={"operation": "add_message", "service": "memory"}
    )
    def add_message(self, session_id: str, human_message: str, ai_message: str, replace_last: bool = False):
        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found when trying to add message")
            return
    
        session = self.sessions[session_id]
    
        if replace_last and session.memory.chat_memory.messages:
            if len(session.memory.chat_memory.messages) >= 2:
                session.memory.chat_memory.messages.pop()  # Remove AI message
                session.memory.chat_memory.messages.pop()  # Remove user message
                logger.debug(f"Replaced last message pair in session {session_id}")
            elif len(session.memory.chat_memory.messages) == 1:
                session.memory.chat_memory.messages.pop()  # Remove single message
                logger.debug(f"Replaced last single message in session {session_id}")
    
        session.memory.chat_memory.add_user_message(human_message)
        session.memory.chat_memory.add_ai_message(ai_message)
        session.last_activity = time.time()
    
        total_messages = len(session.memory.chat_memory.messages)
        logger.debug(f"{'Replaced and added' if replace_last else 'Added'} message pair to session {session_id}. Total messages: {total_messages}")
    
        logger.debug(f"Human: {human_message[:100]}...")
        logger.debug(f"AI: {ai_message[:100]}...")
    
    @langsmith_service.trace(
        name="memory_get_chat_history",
        run_type="retriever",
        metadata={"operation": "get_history", "service": "memory"}
    )
    def get_chat_history(self, session_id: str) -> List[BaseMessage]:
        if session_id not in self.sessions:
            logger.debug(f"No session found for {session_id}, returning empty history")
            return []
        
        messages = self.sessions[session_id].memory.chat_memory.messages
        logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
        return messages
    
    @langsmith_service.trace(
        name="memory_get_variables",
        run_type="retriever",
        metadata={"operation": "get_memory_variables", "service": "memory"}
    )
    def get_memory_variables(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            logger.debug(f"No session found for {session_id}, returning empty memory variables")
            return {"chat_history": []}
        
        try:
            memory_vars = self.sessions[session_id].memory.load_memory_variables({})
            chat_history = memory_vars.get("chat_history", [])
            logger.debug(f"Retrieved memory variables for session {session_id}: {len(chat_history)} messages")
            
            for i, msg in enumerate(chat_history):
                if hasattr(msg, 'type'):
                    logger.debug(f"Message {i}: type={msg.type}, content={msg.content[:50]}...")
                else:
                    logger.debug(f"Message {i}: {type(msg).__name__}")
            
            return memory_vars
        except Exception as e:
            logger.error(f"Error loading memory variables for session {session_id}: {str(e)}")
            return {"chat_history": []}
    
    @langsmith_service.trace(
        name="memory_clear_session",
        run_type="tool",
        metadata={"operation": "clear_session", "service": "memory"}
    )
    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id].memory.clear()
            del self.sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
        else:
            logger.warning(f"Attempted to clear non-existent session: {session_id}")
    
    @langsmith_service.trace(
        name="memory_get_session_info",
        run_type="retriever",
        metadata={"operation": "get_session_info", "service": "memory"}
    )
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "message_count": len(session.memory.chat_memory.messages),
            "metadata": session.metadata
        }
    
    def list_active_sessions(self) -> List[str]:
        return list(self.sessions.keys())
    
    def _cleanup_old_sessions(self):
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")
        
        if len(self.sessions) > self.max_sessions:
            sorted_sessions = sorted(
                self.sessions.items(), 
                key=lambda x: x[1].last_activity
            )
            
            to_remove = len(self.sessions) - self.max_sessions
            for i in range(to_remove):
                session_id = sorted_sessions[i][0]
                del self.sessions[session_id]
                logger.info(f"Removed old session due to limit: {session_id}")


memory_service = ChatMemoryService()