"""
LLM Service - PRIORITY 2

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Abstraction layer for LLM providers.
Makes it easy to switch between different LLM providers (Google, OpenAI, etc.)

Usage:
    from src.services.llm_service import LLMService
    from src.core.config import settings
    
    llm_service = LLMService(settings)
    model = llm_service.get_model()
    model_with_tools = llm_service.get_model_with_tools(tools)
"""

from typing import List, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.config import Settings


class LLMService:
    """
    Service for managing LLM providers.
    Currently supports Google Gemini, but can be extended for other providers.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize LLM service with settings.
        
        Args:
            settings: Application settings with LLM configuration
        """
        self.settings = settings
        self._model = None
    
    def get_model(self) -> ChatGoogleGenerativeAI:
        """
        Get the LLM model instance.
        
        Returns:
            Configured LLM model
        """
        if self._model is None:
            self._model = ChatGoogleGenerativeAI(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature
            )
        return self._model
    
    def get_model_with_tools(self, tools: List[Any]) -> ChatGoogleGenerativeAI:
        """
        Get LLM model bound with tools.
        
        Args:
            tools: List of LangChain tools to bind to the model
            
        Returns:
            LLM model with tools bound
        """
        model = self.get_model()
        return model.bind_tools(tools)  # type: ignore
    
    def reset(self):
        """Reset the model instance (useful for changing settings)."""
        self._model = None
    
    # Future: Add methods for other providers
    # def get_openai_model(self) -> ChatOpenAI:
    #     ...
    # 
    # def get_anthropic_model(self) -> ChatAnthropic:
    #     ...
