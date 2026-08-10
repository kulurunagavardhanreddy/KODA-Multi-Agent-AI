# base_provider.py

from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    """Base interface for all LLM provider integrations."""

    @abstractmethod
    def get_llm(self):
        """Returns the underlying LangChain chat model instance."""
        pass
