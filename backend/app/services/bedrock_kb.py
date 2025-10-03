# app/services/bedrock_kb.py
import os
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from loguru import logger

from app.config import settings
from app.services.bedrock_client import get_bedrock_agent_client, get_bedrock_client
from app.services.langsmith_service import langsmith_service
from app.core.error_handler import KnowledgeBaseError
from app.core.logging_config import LoggingConfig


class RetrievalType(Enum):
    VECTOR = "VECTOR"
    HYBRID = "HYBRID"


@dataclass
class RetrievalResult:
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]
    location: Dict[str, Any]


@dataclass
class GenerationResult:
    answer: str
    citations: List[RetrievalResult]
    source_documents: List[Dict[str, Any]]
    session_id: Optional[str] = None
    guardrails_applied: bool = False


class MockBedrockKB:    
    def __init__(self):
        self.kb_id = "mock-kb"
    
    @langsmith_service.trace(
        name="mock_kb_retrieve_documents",
        run_type="retriever",
        metadata={"source": "mock_kb", "mock": True}
    )
    def retrieve_documents(self, query: str, **kwargs) -> List[RetrievalResult]:
        """Mock document retrieval"""
        return [
            RetrievalResult(
                content=f"Mock legal document content related to: {query}. This is a sample legal document excerpt that would normally come from your AWS Bedrock Knowledge Base.",
                source="mock://legal-documents/sample.pdf",
                score=0.85,
                metadata={"type": "legal_document", "mock": True},
                location={"type": "mock"}
            )
        ]
    
    @langsmith_service.trace(
        name="mock_kb_generate_response",
        run_type="llm",
        metadata={"source": "mock_kb", "mock": True}
    )
    def generate_response(self, query: str, **kwargs) -> GenerationResult:
        mock_citation = RetrievalResult(
            content="This is a mock citation for development purposes. In production, this would contain actual legal document excerpts.",
            source="mock://legal-db/contract-law.pdf",
            score=0.9,
            metadata={"section": "contracts", "mock": True},
            location={"type": "mock"}
        )
        
        return GenerationResult(
            answer=f"Mock Response: Thank you for your legal question: '{query}'. In a production environment with a properly configured AWS Bedrock Knowledge Base, I would provide detailed legal analysis based on your uploaded documents. For now, this is a mock response to help you test the application structure.",
            citations=[mock_citation],
            source_documents=[{"mock": True}],
            session_id=None
        )
    
    @langsmith_service.trace(
        name="mock_kb_health_check",
        run_type="tool",
        metadata={"source": "mock_kb", "mock": True}
    )
    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "kb_id": "mock-kb",
            "model_id": "mock-model",
            "timestamp": time.time(),
            "mock": True,
            "message": "Using mock KB for development"
        }


class EnhancedBedrockKB:
    def __init__(self, kb_id: str = None, model_id: str = None):
        self.kb_id = kb_id or settings.BEDROCK_KNOWLEDGE_BASE_ID
        self.model_id = model_id or settings.BEDROCK_GENERATION_MODEL
        
        if not self.kb_id or self.kb_id.strip() == "" or "your-actual-knowledge-base-id" in self.kb_id:
            logger.warning(f"Invalid BEDROCK_KNOWLEDGE_BASE_ID: '{self.kb_id}'. Using mock KB for development.")
            self.mock_kb = MockBedrockKB()
            self.is_mock = True
            return
            
        self.is_mock = False
        
        try:
            self.agent_client = get_bedrock_agent_client()
            self.runtime_client = get_bedrock_client()
            logger.info(f"Initialized Bedrock KB client with KB ID: {self.kb_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock clients: {str(e)}")
            logger.warning("Falling back to mock KB for development")
            self.mock_kb = MockBedrockKB()
            self.is_mock = True

    @langsmith_service.trace(
        name="kb_retrieve_documents",
        run_type="retriever",
        metadata={"source": "bedrock_kb", "operation": "retrieve"}
    )
    def retrieve_documents(
        self, 
        query: str, 
        max_results: int = 10,
        retrieval_type: RetrievalType = RetrievalType.VECTOR,
        request_id: str = None,
        user_id: str = None
    ) -> List[RetrievalResult]:
        
        if self.is_mock:
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Using mock KB retrieval for query: {query[:50]}..."
            )
            return self.mock_kb.retrieve_documents(query, max_results=max_results)

        start_time = time.time()
        
        try:
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Starting KB retrieval | Query: {query[:100]}... | Max results: {max_results}"
            )
            
            retrieval_config = {
                "vectorSearchConfiguration": {
                    "numberOfResults": max_results
                }
            }
            
            if retrieval_type == RetrievalType.HYBRID:
                retrieval_config["vectorSearchConfiguration"]["overrideSearchType"] = "HYBRID"
            
            response = self.agent_client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration=retrieval_config
            )
            
            duration = time.time() - start_time
            results = self._parse_retrieval_results(response.get("retrievalResults", []))
            
            LoggingConfig.log_kb_query(
                request_id=request_id or "unknown",
                user_id=user_id or "unknown",
                query=query,
                num_results=len(results),
                duration=duration
            )
            
            return results
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = f"AWS Bedrock error ({error_code}): {e.response['Error']['Message']}"
            logger.bind(request_id=request_id, user_id=user_id).error(error_msg)
            raise KnowledgeBaseError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during retrieval: {str(e)}"
            logger.bind(request_id=request_id, user_id=user_id).error(error_msg)
            raise KnowledgeBaseError(error_msg)

    @langsmith_service.trace(
        name="kb_generate_response",
        run_type="chain",
        metadata={"source": "bedrock_kb", "operation": "generate"}
    )
    def generate_response(
        self, 
        query: str,
        max_results: int = 5,
        model_id: str = None,
        session_id: str = None,
        request_id: str = None,
        user_id: str = None,
        system_prompt: str = None
    ) -> GenerationResult:        
        if self.is_mock:
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Using mock KB generation for query: {query[:50]}..."
            )
            return self.mock_kb.generate_response(query)

        start_time = time.time()
        model = model_id or self.model_id
        
        try:
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"Starting RAG generation | Model: {model} | Session: {session_id} (will be ignored)"
            )
            
            region = settings.AWS_REGION or "us-east-1"
            
            config = {
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": self.kb_id,
                    "modelArn": f"arn:aws:bedrock:{region}::foundation-model/{model}",
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {
                            "numberOfResults": max_results
                        }
                    }
                },
                "type": "KNOWLEDGE_BASE"
            }
            
            if system_prompt and "$search_results$" in system_prompt:
                config["knowledgeBaseConfiguration"]["generationConfiguration"] = {
                    "promptTemplate": {
                        "textPromptTemplate": system_prompt + "\n\nHuman: $query$\n\nAssistant:"
                    }
                }
                logger.bind(request_id=request_id, user_id=user_id).info("Using custom prompt template")
            else:
                if system_prompt:
                    logger.bind(request_id=request_id, user_id=user_id).warning(
                        "System prompt missing $search_results$ placeholder. Using default."
                    )
                logger.bind(request_id=request_id, user_id=user_id).info("Using default Bedrock KB prompt template")
            
            request_params = {
                "input": {"text": query},
                "retrieveAndGenerateConfiguration": config
            }
            
            logger.bind(request_id=request_id, user_id=user_id).info(
                "Making Bedrock call WITHOUT session ID to avoid validation errors"
            )
            
            response = self.agent_client.retrieve_and_generate(**request_params)
            
            duration = time.time() - start_time
            result = self._parse_generation_result(response)
            
            logger.bind(request_id=request_id, user_id=user_id).info(
                f"RAG generation completed | Duration: {duration:.3f}s | Citations: {len(result.citations)}"
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = f"AWS Bedrock generation error ({error_code}): {e.response['Error']['Message']}"
            
            if error_code == 'ValidationException' and 'Session' in str(e):
                logger.bind(request_id=request_id, user_id=user_id).error(
                    f"Bedrock session validation failed: {error_msg}"
                )
            else:
                logger.bind(request_id=request_id, user_id=user_id).error(error_msg)
            
            raise KnowledgeBaseError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during generation: {str(e)}"
            logger.bind(request_id=request_id, user_id=user_id).error(error_msg)
            raise KnowledgeBaseError(error_msg)

    @langsmith_service.trace(
        name="kb_parse_retrieval_results",
        run_type="parser",
        metadata={"source": "bedrock_kb", "operation": "parse"}
    )
    def _parse_retrieval_results(self, raw_results: List[Dict[str, Any]]) -> List[RetrievalResult]:
        results = []
        
        for item in raw_results:
            try:
                content = item.get("content", {}).get("text", "")
                location = item.get("location", {})
                metadata = item.get("metadata", {})
                score = item.get("score", 0.0)
                
                source = "Unknown"
                if "s3Location" in location:
                    source = location["s3Location"].get("uri", "Unknown")
                elif "type" in location and location["type"] == "S3":
                    source = location.get("s3Location", {}).get("uri", "Unknown")
                
                result = RetrievalResult(
                    content=content,
                    source=source,
                    score=score,
                    metadata=metadata,
                    location=location
                )
                results.append(result)
                
            except Exception as e:
                logger.warning(f"Failed to parse retrieval result: {str(e)} | Item: {item}")
                continue
        
        return results

    @langsmith_service.trace(
        name="kb_parse_generation_result",
        run_type="parser",
        metadata={"source": "bedrock_kb", "operation": "parse"}
    )
    def _parse_generation_result(self, response: Dict[str, Any]) -> GenerationResult:
        try:
            output = response.get("output", {})
            answer = output.get("text", "Sorry, I could not generate a response.")
            session_id = response.get("sessionId")
            
            citations = []
            source_documents = []
            
            for citation in response.get("citations", []):
                for ref in citation.get("retrievedReferences", []):
                    try:
                        content = ref.get("content", {}).get("text", "")
                        location = ref.get("location", {})
                        metadata = ref.get("metadata", {})
                        
                        source = "Unknown"
                        if "s3Location" in location:
                            source = location["s3Location"].get("uri", "Unknown")
                        
                        citation_result = RetrievalResult(
                            content=content,
                            source=source,
                            score=0.0,
                            metadata=metadata,
                            location=location
                        )
                        citations.append(citation_result)
                        source_documents.append(ref)
                        
                    except Exception as e:
                        logger.warning(f"Failed to parse citation: {str(e)}")
                        continue
            
            return GenerationResult(
                answer=answer,
                citations=citations,
                source_documents=source_documents,
                session_id=session_id
            )
            
        except Exception as e:
            logger.error(f"Failed to parse generation result: {str(e)}")
            raise KnowledgeBaseError(f"Failed to parse generation result: {str(e)}")

    @langsmith_service.trace(
        name="kb_health_check",
        run_type="tool",
        metadata={"source": "bedrock_kb", "operation": "health_check"}
    )
    def health_check(self) -> Dict[str, Any]:
        
        if self.is_mock:
            return self.mock_kb.health_check()
            
        try:
            test_response = self.agent_client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": "test"},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": 1}
                }
            )
            
            return {
                "status": "healthy",
                "kb_id": self.kb_id,
                "model_id": self.model_id,
                "timestamp": time.time(),
                "region": settings.AWS_REGION
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "kb_id": self.kb_id,
                "timestamp": time.time()
            }


BedrockKB = EnhancedBedrockKB