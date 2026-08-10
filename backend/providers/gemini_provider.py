# gemini_provider.py

from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import GEMINI_API_KEY
from .base_provider import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    """Integrates Gemini 2.5 Flash as the chat provider."""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            api_key=GEMINI_API_KEY, 
            temperature=0.3,
            safety_settings={
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE"
            }
        )

    def get_llm(self):
        return self.llm
