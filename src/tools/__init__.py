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
    
    # Helper classes (used by tools)
    'PlaywrightChartExtractor',
    'ElementParser',
    'SiteIntelligenceTool',
    
    # Learning manager
    'LearningManager',
    'get_learning_manager',
]
