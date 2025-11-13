"""
Tools Package - Agent tools and capabilities

This package contains all tool implementations for the agent.
"""

# Import base tools
from .base import BaseTool
from .calculator import CalculatorTool
from .chunk_reader import GetNextChunkTool

# Import analysis tools
from .analysis_tools import (
    AnalyzeSentimentTool,
    SummarizeContentTool,
    CompareDataTool,
    ValidateDataTool
)

# Import Playwright universal tool
from .playwright_universal import UniversalPlaywrightTool

# Import helper classes (not tools, but used by tools)
from .chart_extractor import PlaywrightChartExtractor
from .chart_extractor_tool import ChartExtractorTool
from .element_parser import ElementParser
from .site_intelligence import SiteIntelligenceTool

# Import content extractor
from .content_extractor import ContentExtractor
from .content_extractor_tool import ContentExtractorTool

# Import interactive element extractor
from .interactive_element_extractor import InteractiveElementExtractor
from .interactive_element_extractor_tool import InteractiveElementExtractorTool

# Import semantic element selector
from .semantic_element_selector import SemanticElementSelector, get_element_selector

# Import learning manager
from .learning_manager import LearningManager, get_learning_manager

__all__ = [
    # Base tools
    'BaseTool',
    'CalculatorTool',
    'GetNextChunkTool',
    
    # Analysis tools
    'AnalyzeSentimentTool',
    'SummarizeContentTool',
    'CompareDataTool',
    'ValidateDataTool',
    
    # Playwright tools
    'UniversalPlaywrightTool',
    'ChartExtractorTool',

    # Content extractor
    'ContentExtractor',
    'ContentExtractorTool',

    # Interactive element extractor
    'InteractiveElementExtractor',
    'InteractiveElementExtractorTool',

    # Semantic element selector
    'SemanticElementSelector',
    'get_element_selector',

    # Helper classes (used by tools)
    'PlaywrightChartExtractor',
    'ElementParser',
    'SiteIntelligenceTool',

    # Learning manager
    'LearningManager',
    'get_learning_manager',
]
