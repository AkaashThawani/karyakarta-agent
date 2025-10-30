"""
Tools Package - Agent tools and capabilities

This package contains all tool implementations for the agent.
"""

# Import base tools
from .base import BaseTool
# from .search import SearchTool  # TEMP DISABLED - Agent should use browser to search Google
from .scraper import ScraperTool
from .calculator import CalculatorTool
from .extractor import ExtractorTool
from .chunk_reader import GetNextChunkTool
from .list_tools import ListToolsTool

# Import Playwright-based browsing tools
from .browse_advanced import (
    BrowseAndWaitTool,
    BrowseWithScrollTool,
    BrowseWithClickTool
)

# Import Playwright-based form and navigation tools
from .browse_forms import (
    BrowseWithFormTool,
    BrowseWithAuthTool,
    BrowseMultiPageTool
)

# Import extraction tools
from .extract_structured import ExtractStructuredTool
from .extract_advanced import (
    ExtractTableTool,
    ExtractLinksTool,
    ExtractImagesTool,
    ExtractTextBlocksTool
)

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

# Import learning and fallback managers
from .learning_manager import LearningManager, get_learning_manager
from .fallback_manager import ToolFallbackChain, get_fallback_manager

__all__ = [
    # Base tools
    'BaseTool',
    # 'SearchTool',  # TEMP DISABLED - Agent should use browser to search Google
    'ScraperTool',
    'CalculatorTool',
    'ExtractorTool',
    'GetNextChunkTool',
    'ListToolsTool',
    
    # Playwright browsing tools
    'BrowseAndWaitTool',
    'BrowseWithScrollTool',
    'BrowseWithClickTool',
    
    # Playwright form and navigation tools
    'BrowseWithFormTool',
    'BrowseWithAuthTool',
    'BrowseMultiPageTool',
    
    # Extraction tools
    'ExtractStructuredTool',
    'ExtractTableTool',
    'ExtractLinksTool',
    'ExtractImagesTool',
    'ExtractTextBlocksTool',
    
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
    
    # Learning and fallback managers
    'LearningManager',
    'get_learning_manager',
    'ToolFallbackChain',
    'get_fallback_manager',
]
