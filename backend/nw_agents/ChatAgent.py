import asyncio
import asyncio
from secretKeys import SILICONFLOW_BASE_URL, SILICONFLOW_MODEL, SILICONFLOW_API_KEY
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

import logging
logger = logging.getLogger(__name__)

ChatAgent = Agent(
    model=OpenAIModel(
        model_name=SILICONFLOW_MODEL,
        base_url=SILICONFLOW_BASE_URL,
        api_key=SILICONFLOW_API_KEY,
    ),
    system_prompt="You are a network monitoring assistant. Based on the provided network metrics, answer the user's question about the current network performance.",
    model_settings={'temperature': 0.5},
    result_retries=3,
    retries=3,
    result_type=str
)
