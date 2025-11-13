"""
LLM Service - PRIORITY 2

IMPLEMENTATION STATUS: ✅ IMPLEMENTED

Abstraction layer for LLM providers with Gemini 2.5 structured outputs.
Uses proper JSON schema validation instead of mime-type forcing.

Usage:
    from src.services.llm_service import LLMService
    from src.core.config import settings

    llm_service = LLMService(settings)
    model = llm_service.get_model()
    model_with_schema = llm_service.get_model_with_schema(schema_dict)
    model_with_tools = llm_service.get_model_with_tools(tools)
"""

from typing import List, Any, Dict, Optional, Union
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.runnables import Runnable
from src.core.config import Settings


class LLMService:
    """
    Service for managing LLM providers with Gemini 2.5 structured outputs.

    Uses Gemini's native JSON schema validation for reliable structured responses.
    """

    def __init__(self, settings: Settings):
        """
        Initialize LLM service with settings.

        Args:
            settings: Application settings with LLM configuration
        """
        self.settings = settings
        self._model = None
        self._model_with_schema = {}  # Cache models by schema

    def get_model(self) -> ChatGoogleGenerativeAI:
        """
        Get the basic LLM model instance (no structured output).

        Returns:
            Configured LLM model
        """
        if self._model is None:
            self._model = ChatGoogleGenerativeAI(
                model=self.settings.llm_model,
                temperature=self.settings.llm_temperature,
                google_api_key=self.settings.GEMINI_API_KEY,
                max_output_tokens=8192,
                top_p=0.95,
                top_k=40
            )
        return self._model

    def get_model_with_schema(self, schema: Dict[str, Any], schema_name: str = "response") -> Runnable:
        """
        Get LLM model with JSON schema validation (Gemini 2.5 structured outputs).

        Uses LangChain's with_structured_output() method which properly handles
        Gemini's structured output configuration.

        Args:
            schema: JSON schema dictionary
            schema_name: Name for the schema (used for caching)

        Returns:
            Runnable with structured output enabled

        Usage:
            schema = {
                "type": "object",
                "properties": {
                    "task_type": {"type": "string"},
                    "required_tools": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["task_type"]
            }
            model = llm_service.get_model_with_schema(schema, "task_analysis")
            response = model.invoke("Analyze this task...")
            # response will be a dict matching the schema
        """
        cache_key = f"{schema_name}_{hash(str(schema))}"

        if cache_key not in self._model_with_schema:
            base_model = self.get_model()

            # Use LangChain's structured output method
            # This should properly configure Gemini for structured outputs
            structured_model = base_model.with_structured_output(
                schema=schema,
                method="json_schema"
            )

            self._model_with_schema[cache_key] = structured_model

        return self._model_with_schema[cache_key]

    def get_model_with_tools(self, tools: List[Any]) -> ChatGoogleGenerativeAI:
        """
        Get LLM model bound with tools.

        Args:
            tools: List of LangChain tools to bind to the model

        Returns:
            LLM model with tools bound
        """
        model = self.get_model()
        return model.bind_tools(tools)

    def invoke_with_schema(
        self,
        prompt: str,
        schema: Dict[str, Any],
        schema_name: str = "response",
        system_message: Optional[str] = None
    ) -> Any:
        """
        Convenience method to invoke LLM with schema validation.

        Args:
            prompt: User prompt
            schema: JSON schema for response validation
            schema_name: Schema identifier for caching
            system_message: Optional system message

        Returns:
            Validated response matching schema (dict for structured output)
        """
        model = self.get_model_with_schema(schema, schema_name)

        messages = []
        if system_message:
            messages.append(SystemMessage(content=system_message))
        messages.append({"role": "user", "content": prompt})

        response = model.invoke(messages)

        # For structured output, response is already the parsed dict
        # For regular models, it would be an AIMessage
        if isinstance(response, dict):
            return response
        elif hasattr(response, 'content'):
            return response.content
        else:
            return response

    def reset(self):
        """Reset all model instances (useful for changing settings)."""
        self._model = None
        self._model_with_schema.clear()

    # =========================================================================
    # COMMON SCHEMAS
    # =========================================================================

    @staticmethod
    def get_task_analysis_schema() -> Dict[str, Any]:
        """Schema for task analysis responses."""
        return {
            "type": "object",
            "properties": {
                "task_type": {
                    "type": "string",
                    "enum": ["search", "web_scraping", "api_request", "general"],
                    "description": "Type of task being performed"
                },
                "query_params": {
                    "type": "object",
                    "description": "API query parameters if applicable"
                },
                "required_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of required tool names"
                },
                "required_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Data fields that must be extracted"
                },
                "task_structure": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["single", "sequential", "adaptive"],
                            "description": "Execution strategy"
                        },
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tool": {"type": "string"},
                                    "parameters": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string"},
                                            "url": {"type": "string"},
                                            "method": {"type": "string"},
                                            "selector": {"type": "string"},
                                            "selector_hint": {"type": "string"},
                                            "args": {"type": "object"},
                                            "required_fields": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            },
                                            "limit": {"type": "integer"},
                                            "params": {"type": "object"}
                                        },
                                        "description": "Tool-specific parameters"
                                    },
                                    "description": {"type": "string"}
                                },
                                "required": ["tool", "parameters", "description"]
                            },
                            "description": "Execution steps"
                        },
                        "goal": {
                            "type": "string",
                            "description": "Goal for adaptive execution"
                        }
                    },
                    "required": ["type"]
                }
            },
            "required": ["task_type", "required_tools", "task_structure"]
        }

    @staticmethod
    def get_subtask_schema() -> Dict[str, Any]:
        """Schema for subtask decomposition responses."""
        return {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string"},
                            "parameters": {"type": "object"},
                            "description": {"type": "string"}
                        },
                        "required": ["tool", "parameters", "description"]
                    }
                }
            },
            "required": ["subtasks"]
        }

    @staticmethod
    def get_field_extraction_schema() -> Dict[str, Any]:
        """Schema for field extraction responses."""
        return {
            "type": "object",
            "properties": {
                "user_requested": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields explicitly requested by user"
                },
                "suggested": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional useful fields to extract"
                },
                "category": {"type": "string", "description": "Data category"},
                "year": {"type": "integer", "description": "Year if applicable"}
            },
            "required": ["user_requested", "suggested"]
        }

    # Future: Add methods for other providers
    # def get_openai_model(self) -> ChatOpenAI:
    #     ...
    #
    # def get_anthropic_model(self) -> ChatAnthropic:
    #     ...
