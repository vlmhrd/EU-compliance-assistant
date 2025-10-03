# app/services/bedrock_client.py
import boto3
from functools import lru_cache
from app.config import settings


@lru_cache(maxsize=1)
def get_bedrock_client():
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


@lru_cache(maxsize=1)
def get_bedrock_agent_client():
    return boto3.client(
        service_name="bedrock-agent-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def clear_client_cache():
    get_bedrock_client.cache_clear()
    get_bedrock_agent_client.cache_clear()