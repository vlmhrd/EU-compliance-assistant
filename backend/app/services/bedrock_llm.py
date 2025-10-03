import os
from langchain_community.chat_models import BedrockChat

def get_bedrock_llm():
    model_id = os.getenv("BEDROCK_GENERATION_MODEL", "anthropic.claude-v2")
    return BedrockChat(
        model_id=model_id,
        client=None,
        region_name="eu-central-1",
    )
