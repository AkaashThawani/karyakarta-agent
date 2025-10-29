"""
Tools Package - Agent tools and capabilities

This package contains all tool implementations for the agent.
"""

# Import base tools
from .base import BaseTool
from .search import SearchTool
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

__all__ = [
    # Base tools
    'BaseTool',
    'SearchTool',
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
]
