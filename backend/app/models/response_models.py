from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class Citation(BaseModel):
    source: str
    snippet: str

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    tool_used: Optional[str] = None
    session_id: Optional[str] = None  # Add session ID to response
    timestamp: datetime = datetime.now()

class SearchResponse(BaseModel):
    query: str
    total_results: int
    max_results: int
    documents: List[Dict[str, Any]]
    session_id: Optional[str] = None

class ChatHistoryRequest(BaseModel):
    session_id: str

class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    total_messages: int

class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    created_at: float
    last_activity: float
    message_count: int
    metadata: Dict[str, Any]