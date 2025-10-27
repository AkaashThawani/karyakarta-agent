"""
Analysis Tools

AI-powered analysis tools:
- analyze_sentiment: Sentiment analysis
- summarize_content: Content summarization  
- compare_data: Data comparison
- validate_data: Data quality validation
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService
from src.services.llm_service import LLMService
import json
import re


class AnalyzeSentimentInput(BaseModel):
    """Input schema for analyze_sentiment tool."""
    text: str = Field(description="Text to analyze sentiment")
    detailed: Optional[bool] = Field(
        default=False,
        description="Return detailed sentiment breakdown"
    )


class SummarizeContentInput(BaseModel):
    """Input schema for summarize_content tool."""
    content: str = Field(description="Content to summarize")
    max_length: Optional[int] = Field(
        default=200,
        description="Maximum summary length in words"
    )
    style: Optional[str] = Field(
        default="concise",
        description="Summary style: 'concise', 'detailed', 'bullet'"
    )


class CompareDataInput(BaseModel):
    """Input schema for compare_data tool."""
    data1: str = Field(description="First dataset (JSON or text)")
    data2: str = Field(description="Second dataset (JSON or text)")
    comparison_type: Optional[str] = Field(
        default="differences",
        description="Type: 'differences', 'similarities', 'all'"
    )


class ValidateDataInput(BaseModel):
    """Input schema for validate_data tool."""
    data: str = Field(description="Data to validate (JSON or text)")
    schema_type: Optional[str] = Field(
        default="general",
        description="Schema type: 'general', 'json', 'email', 'url'"
    )
    strict: Optional[bool] = Field(
        default=False,
        description="Strict validation mode"
    )


class AnalyzeSentimentTool(BaseTool):
    """Tool for sentiment analysis using LLM."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None, llm_service: Optional[LLMService] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.llm_service = llm_service
    
    @property
    def name(self) -> str:
        return "analyze_sentiment"
    
    @property
    def description(self) -> str:
        return """Analyze sentiment of text using AI.
        
        Parameters:
        - text: Text to analyze
        - detailed: Return detailed breakdown
        
        Returns: Sentiment analysis (positive/negative/neutral) with score
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("text"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        text = kwargs.get("text", "")
        detailed = kwargs.get("detailed", False)
        
        if not text:
            return ToolResult(success=False, error="Text is required", metadata={})
        
        try:
            if self.llm_service:
                sentiment = self._analyze_with_llm(text, detailed)
            else:
                sentiment = self._analyze_basic(text)
            
            return ToolResult(
                success=True,
                data=json.dumps(sentiment, indent=2),
                metadata={"text_length": len(text)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def _analyze_with_llm(self, text: str, detailed: bool) -> Dict[str, Any]:
        """Analyze sentiment using LLM."""
        if not self.llm_service:
            return self._analyze_basic(text)
        
        prompt = f"""Analyze the sentiment of the following text. Return a JSON object with:
- sentiment: "positive", "negative", or "neutral"
- score: confidence score from 0.0 to 1.0
- explanation: brief explanation (if detailed)

Text: {text[:1000]}

Return only the JSON object:"""
        
        model = self.llm_service.get_model()
        response = model.invoke(prompt)
        content_str = response.content if hasattr(response, 'content') else str(response)
        
        # Ensure content is string
        if not isinstance(content_str, str):
            content_str = str(content_str)
        
        # Try to parse JSON from response
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*"sentiment"[^{}]*\}', content_str, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass
        
        # Fallback to simple extraction
        if "positive" in content_str.lower():
            sentiment = "positive"
        elif "negative" in content_str.lower():
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "score": 0.5,
            "explanation": "Sentiment detected from LLM response"
        }
    
    def _analyze_basic(self, text: str) -> Dict[str, Any]:
        """Basic sentiment analysis without LLM."""
        text_lower = text.lower()
        
        # Simple word counting
        positive_words = ["good", "great", "excellent", "amazing", "wonderful", "love", "best", "perfect"]
        negative_words = ["bad", "terrible", "awful", "worst", "hate", "poor", "horrible", "disappointing"]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = min(0.5 + (positive_count * 0.1), 1.0)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = min(0.5 + (negative_count * 0.1), 1.0)
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {
            "sentiment": sentiment,
            "score": score,
            "positive_indicators": positive_count,
            "negative_indicators": negative_count
        }
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=AnalyzeSentimentInput)
        def analyze_sentiment(text: str, detailed: bool = False) -> str:
            """Analyze sentiment of text."""
            result = tool_instance.execute(text=text, detailed=detailed)
            return tool_instance.format_result(result)
        
        return analyze_sentiment


class SummarizeContentTool(BaseTool):
    """Tool for content summarization using LLM."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None, llm_service: Optional[LLMService] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
        self.llm_service = llm_service
    
    @property
    def name(self) -> str:
        return "summarize_content"
    
    @property
    def description(self) -> str:
        return """Summarize content using AI.
        
        Parameters:
        - content: Content to summarize
        - max_length: Max summary length in words
        - style: 'concise', 'detailed', 'bullet'
        
        Returns: Summarized content
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("content"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        content = kwargs.get("content", "")
        max_length = kwargs.get("max_length", 200)
        style = kwargs.get("style", "concise")
        
        if not content:
            return ToolResult(success=False, error="Content is required", metadata={})
        
        try:
            if self.llm_service:
                summary = self._summarize_with_llm(content, max_length, style)
            else:
                summary = self._summarize_basic(content, max_length)
            
            return ToolResult(
                success=True,
                data=summary,
                metadata={"original_length": len(content), "summary_length": len(summary)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def _summarize_with_llm(self, content: str, max_length: int, style: str) -> str:
        """Summarize using LLM."""
        if not self.llm_service:
            return self._summarize_basic(content, max_length)
        
        style_instructions = {
            "concise": "Provide a brief, concise summary.",
            "detailed": "Provide a detailed summary covering main points.",
            "bullet": "Provide a bullet-point summary of key points."
        }
        
        instruction = style_instructions.get(style, style_instructions["concise"])
        
        prompt = f"""{instruction} Maximum {max_length} words.

Content:
{content[:3000]}

Summary:"""
        
        model = self.llm_service.get_model()
        response = model.invoke(prompt)
        result = response.content if hasattr(response, 'content') else str(response)
        
        # Ensure result is string
        if not isinstance(result, str):
            result = str(result)
        
        return result
    
    def _summarize_basic(self, content: str, max_length: int) -> str:
        """Basic summarization without LLM."""
        # Simple truncation
        words = content.split()
        if len(words) <= max_length:
            return content
        
        return " ".join(words[:max_length]) + "..."
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=SummarizeContentInput)
        def summarize_content(content: str, max_length: int = 200, style: str = "concise") -> str:
            """Summarize content using AI."""
            result = tool_instance.execute(content=content, max_length=max_length, style=style)
            return tool_instance.format_result(result)
        
        return summarize_content


class CompareDataTool(BaseTool):
    """Tool for comparing two datasets."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "compare_data"
    
    @property
    def description(self) -> str:
        return """Compare two datasets.
        
        Parameters:
        - data1: First dataset
        - data2: Second dataset
        - comparison_type: 'differences', 'similarities', 'all'
        
        Returns: Comparison results
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("data1") and kwargs.get("data2"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        data1 = kwargs.get("data1", "")
        data2 = kwargs.get("data2", "")
        comparison_type = kwargs.get("comparison_type", "differences")
        
        if not data1 or not data2:
            return ToolResult(success=False, error="Both data1 and data2 are required", metadata={})
        
        try:
            comparison = self._compare(data1, data2, comparison_type)
            
            return ToolResult(
                success=True,
                data=json.dumps(comparison, indent=2),
                metadata={"comparison_type": comparison_type}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def _compare(self, data1: str, data2: str, comparison_type: str) -> Dict[str, Any]:
        """Compare two datasets."""
        # Try to parse as JSON
        try:
            obj1 = json.loads(data1)
            obj2 = json.loads(data2)
            return self._compare_json(obj1, obj2, comparison_type)
        except:
            return self._compare_text(data1, data2, comparison_type)
    
    def _compare_json(self, obj1: Any, obj2: Any, comparison_type: str) -> Dict[str, Any]:
        """Compare JSON objects."""
        if isinstance(obj1, dict) and isinstance(obj2, dict):
            keys1 = set(obj1.keys())
            keys2 = set(obj2.keys())
            
            result = {
                "type": "dict_comparison",
                "keys_only_in_data1": list(keys1 - keys2),
                "keys_only_in_data2": list(keys2 - keys1),
                "common_keys": list(keys1 & keys2),
                "different_values": {}
            }
            
            for key in keys1 & keys2:
                if obj1[key] != obj2[key]:
                    result["different_values"][key] = {
                        "data1": obj1[key],
                        "data2": obj2[key]
                    }
            
            return result
        else:
            return {"equal": obj1 == obj2, "data1": obj1, "data2": obj2}
    
    def _compare_text(self, text1: str, text2: str, comparison_type: str) -> Dict[str, Any]:
        """Compare text data."""
        lines1 = set(text1.split('\n'))
        lines2 = set(text2.split('\n'))
        
        return {
            "type": "text_comparison",
            "lines_only_in_data1": len(lines1 - lines2),
            "lines_only_in_data2": len(lines2 - lines1),
            "common_lines": len(lines1 & lines2),
            "equal": text1 == text2
        }
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=CompareDataInput)
        def compare_data(data1: str, data2: str, comparison_type: str = "differences") -> str:
            """Compare two datasets."""
            result = tool_instance.execute(data1=data1, data2=data2, comparison_type=comparison_type)
            return tool_instance.format_result(result)
        
        return compare_data


class ValidateDataTool(BaseTool):
    """Tool for data quality validation."""
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None, settings: Optional[Any] = None):
        super().__init__(logger)
        self.session_id = session_id
        self.settings = settings
    
    @property
    def name(self) -> str:
        return "validate_data"
    
    @property
    def description(self) -> str:
        return """Validate data quality and format.
        
        Parameters:
        - data: Data to validate
        - schema_type: 'general', 'json', 'email', 'url'
        - strict: Strict validation mode
        
        Returns: Validation results with issues found
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        return bool(kwargs.get("data"))
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        data = kwargs.get("data", "")
        schema_type = kwargs.get("schema_type", "general")
        strict = kwargs.get("strict", False)
        
        if not data:
            return ToolResult(success=False, error="Data is required", metadata={})
        
        try:
            validation = self._validate(data, schema_type, strict)
            
            return ToolResult(
                success=True,
                data=json.dumps(validation, indent=2),
                metadata={"schema_type": schema_type, "valid": validation["valid"]}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), metadata={})
    
    def _validate(self, data: str, schema_type: str, strict: bool) -> Dict[str, Any]:
        """Validate data."""
        if schema_type == "json":
            return self._validate_json(data, strict)
        elif schema_type == "email":
            return self._validate_email(data)
        elif schema_type == "url":
            return self._validate_url(data)
        else:
            return self._validate_general(data)
    
    def _validate_json(self, data: str, strict: bool) -> Dict[str, Any]:
        """Validate JSON."""
        try:
            json.loads(data)
            return {"valid": True, "type": "json", "issues": []}
        except json.JSONDecodeError as e:
            return {"valid": False, "type": "json", "issues": [str(e)]}
    
    def _validate_email(self, data: str) -> Dict[str, Any]:
        """Validate email."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(email_pattern, data.strip()))
        
        issues = []
        if not is_valid:
            issues.append("Invalid email format")
        
        return {"valid": is_valid, "type": "email", "issues": issues}
    
    def _validate_url(self, data: str) -> Dict[str, Any]:
        """Validate URL."""
        url_pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
        is_valid = bool(re.match(url_pattern, data.strip()))
        
        issues = []
        if not is_valid:
            issues.append("Invalid URL format")
        
        return {"valid": is_valid, "type": "url", "issues": issues}
    
    def _validate_general(self, data: str) -> Dict[str, Any]:
        """General validation."""
        issues = []
        
        if not data.strip():
            issues.append("Data is empty")
        
        if len(data) < 10:
            issues.append("Data seems too short")
        
        return {
            "valid": len(issues) == 0,
            "type": "general",
            "issues": issues,
            "length": len(data)
        }
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=ValidateDataInput)
        def validate_data(data: str, schema_type: str = "general", strict: bool = False) -> str:
            """Validate data quality."""
            result = tool_instance.execute(data=data, schema_type=schema_type, strict=strict)
            return tool_instance.format_result(result)
        
        return validate_data
