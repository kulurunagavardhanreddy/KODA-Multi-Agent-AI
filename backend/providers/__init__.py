# providers package init

from .base_provider import BaseLLMProvider
from .gemini_provider import GeminiProvider
from .llm_provider import LLMProvider
from backend.config import LLM_PROVIDER

def get_provider(provider_name: str = None) -> BaseLLMProvider:
    """Returns the requested provider instance. Defaults to the configured system provider."""
    if not provider_name:
        provider_name = LLM_PROVIDER
        
    name_clean = provider_name.lower().strip()
    if name_clean in ("gemini", "gemini_provider", "google"):
        return GeminiProvider()
    return LLMProvider()
