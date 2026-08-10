# llm_provider.py

import os
import requests
import logging
from langchain_openai import ChatOpenAI
from .base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)

class LLMProvider(BaseLLMProvider):
    """Integrates remote custom GPU Server endpoint (e.g. Qwen / Mistral) via ChatOpenAI client interface."""
    
    def __init__(self):
        self.api_base = os.getenv("MISTRAL_API_BASE", "http://164.52.199.204/v1")
        self.api_key = os.getenv("MISTRAL_API_KEY", "EMPTY")
        env_model = os.getenv("MISTRAL_MODEL_NAME", "")
        
        self.model_name = self._get_dynamic_model_name(self.api_base, env_model)
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=self.api_base,
            temperature=0.3,
            streaming=True
        )

    def _get_dynamic_model_name(self, api_base, env_model):
        """Uses the model from .env to save startup time, otherwise fetches dynamically."""
        if env_model and env_model.strip():
            logger.info("🌟 [Config] Loaded model name directly from .env: '%s'", env_model)
            return env_model.strip()
            
        logger.info("🔍 [Config] No model in .env. Fetching dynamically from %s...", api_base)
        try:
            url = f"{api_base.rstrip('/')}/models"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    model_id = data["data"][0]["id"]
                    logger.info("🌟 [Config] Successfully fetched dynamic model name: '%s'", model_id)
                    return model_id
        except Exception as e:
            logger.warning("⚠️ [Config] Failed to fetch dynamic model name from %s: %s", api_base, e)
        
        default_model = "mistralai/Ministral-3-14B-Instruct-2512"
        logger.warning("⚠️ [Config] Using hardcoded fallback model name: '%s'", default_model)
        return default_model

    def get_llm(self):
        return self.llm
