# System Integrations - KaryaKarta Agent

**Last Updated:** October 31, 2025

This document consolidates all external integrations and internal systems.

## 📚 Table of Contents

1. [Playwright Integration](#playwright-integration)
2. [Multi-Agent System](#multi-agent-system)
3. [Supabase Integration](#supabase-integration)
4. [LLM Integration](#llm-integration)
5. [Selector System](#selector-system)
6. [Site Intelligence](#site-intelligence)
7. [Extraction System](#extraction-system)

---

## 🎭 Playwright Integration

### Overview
Playwright provides browser automation capabilities for dynamic web scraping and interaction.

### Features
- **Persistent Browser Sessions**: Reusable browser instances per session
- **Dynamic Method Execution**: Runtime method invocation via UniversalPlaywrightTool
- **Automatic Cleanup**: Graceful shutdown handling
- **Session Isolation**: Separate contexts per user session

### Implementation

#### UniversalPlaywrightTool
```python
# Dynamic method execution
tool = UniversalPlaywrightTool(session_id, logger, settings)
result = tool.execute(
    action="navigate",
    url="https://example.com"
)
```

#### Key Components
- `playwright_universal.py`: Main tool implementation
- Session-based browser management
- Event loop per session
- Timeout handling (60s default)

### Browser Lifecycle
1. **Initialization**: Browser launched on first use
2. **Reuse**: Same browser instance for session
3. **Cleanup**: Automatic on app shutdown
4. **Timeout**: 5s timeout for graceful close

### Supported Actions
- Navigate to URL
- Click elements
- Fill forms
- Extract content
- Take screenshots
- Execute JavaScript
- Wait for selectors
- Scroll pages

---

## 🤖 Multi-Agent System

### Architecture

#### Reason Agent
- **Purpose**: High-level planning and task decomposition
- **Capabilities**: 
  - Task analysis
  - Strategy formulation
  - Tool selection guidance
  - Result validation

#### Executor Agent
- **Purpose**: Tool execution and result synthesis
- **Capabilities**:
  - Tool invocation
  - Error handling
  - Result aggregation
  - Response formatting

### Intelligent Routing

#### Routing Strategies
1. **REASON_FIRST**: Complex planning tasks
2. **EXECUTOR_FIRST**: Direct execution tasks
3. **BALANCED**: Automatic selection based on task

#### Decision Logic
```python
if task_requires_planning:
    use_reason_agent()
elif task_is_simple:
    use_executor_agent()
else:
    use_balanced_approach()
```

### Configuration
```python
USE_MULTI_AGENT_SYSTEM = True  # Enable/disable multi-agent

# In agent_logic.py
manager = MultiAgentManager(
    llm_service=llm_service,
    memory_service=memory_service,
    logging_service=logger,
    tools=tools,
    enable_routing=True,
    routing_strategy=RoutingStrategy.BALANCED
)
```

---

## 💾 Supabase Integration

### Overview
Supabase provides cloud database and authentication services.

### Components

#### Database
- **Conversations**: Store chat history
- **Sessions**: Track user sessions
- **Tool Results**: Cache tool outputs

#### Authentication
- OAuth integration
- Session management
- User profiles

### Implementation
```python
from src.services.supabase_service import SupabaseService

supabase = SupabaseService()
supabase.store_conversation(session_id, messages)
```

### Features
- Real-time synchronization
- Automatic backups
- Row-level security
- API access

---

## 🧠 LLM Integration

### Supported Models

#### Google Gemini (Primary)
- Model: gemini-1.5-flash
- Use: General tasks, extraction, analysis
- Configuration: via `GOOGLE_API_KEY`

#### Model Selection
```python
from src.services.llm_service import LLMService

llm = LLMService(settings)
model = llm.get_model()  # Returns configured model
```

### Features
- **Temperature Control**: Adjustable creativity
- **Token Management**: Automatic counting
- **Streaming**: Real-time responses
- **Fallback**: Error recovery mechanisms

### Usage Patterns

#### Text Generation
```python
response = model.invoke(prompt)
content = response.content
```

#### Tool Calling
```python
model_with_tools = model.bind_tools(tools)
response = model_with_tools.invoke(messages)
```

---

## 🎯 Selector System

### Overview
Intelligent CSS selector management for web scraping reliability.

### Components

#### Selector Map
- **Purpose**: Cache proven selectors per domain
- **Location**: `selector_cache/`
- **Format**: JSON per domain

#### Dynamic Selectors
- **Fallback Generation**: Auto-create when cached fails
- **Learning**: Update cache on success
- **Validation**: Test before using

### Implementation

```python
from src.routing.selector_map import get_selector_map

selector_map = get_selector_map()
selectors = selector_map.get_selectors("example.com")
```

### Cache Structure
```json
{
  "domain": "example.com",
  "selectors": {
    "title": "h1.main-title",
    "content": "div.content",
    "links": "a.item-link"
  },
  "last_validated": "2025-10-31T17:00:00Z",
  "success_rate": 0.95
}
```

### Optimization
- Periodic validation
- Success rate tracking
- Automatic deprecation
- Fallback generation

---

## 🧩 Site Intelligence

### Overview
Learn and adapt to website structures automatically.

### Features
- **Structure Analysis**: Identify page patterns
- **Selector Learning**: Discover reliable selectors
- **Pattern Recognition**: Detect common layouts
- **Self-Improvement**: Update strategies based on results

### Implementation
```python
from src.tools.site_intelligence import SiteIntelligenceTool

intelligence = SiteIntelligenceTool()
schema = await intelligence.build_site_schema(url, page, llm_service)
```

### Learning Process
1. **Analysis**: Examine page structure
2. **Pattern Detection**: Identify repeating elements
3. **Selector Extraction**: Generate reliable selectors
4. **Validation**: Test extracted selectors
5. **Caching**: Store successful patterns

### Use Cases
- First-time site visits
- Dynamic content handling
- Structure changes detection
- Fallback creation

---

## 📊 Extraction System

### Overview
Multi-layered data extraction with automatic fallbacks.

### Layers

#### 1. Universal Extractor
- **Method**: Extract everything, then search
- **Speed**: Fast (pure parsing)
- **Accuracy**: High for structured data
- **Use**: First attempt for all extractions

#### 2. Cached Selectors
- **Method**: Use proven selectors
- **Speed**: Very Fast
- **Accuracy**: Very High (proven)
- **Use**: When domain is known

#### 3. Heuristic Patterns
- **Method**: Pattern matching
- **Speed**: Medium
- **Accuracy**: Medium-High
- **Use**: Unknown structures

#### 4. LLM Extraction
- **Method**: AI-powered parsing
- **Speed**: Slow
- **Accuracy**: High (context-aware)
- **Use**: Last resort fallback

### Implementation

```python
from src.tools.chart_extractor import PlaywrightChartExtractor

extractor = PlaywrightChartExtractor()
records = await extractor.extract_chart(
    page=page,
    url=url,
    required_fields=["name", "price", "rating"]
)
```

### Features
- **Completeness Validation**: Check for missing fields
- **Coverage Metrics**: Track extraction success
- **Self-Learning**: Improve from successes
- **Pattern Caching**: Remember what works

### Completeness Validation
```python
validation = {
    "complete": True/False,
    "coverage": 0.0-1.0,
    "missing_fields": ["field1", "field2"],
    "extracted_fields": ["field3", "field4"]
}
```

---

## 🔄 Fallback System

### Overview
Automatic fallback mechanisms for reliability.

### Fallback Chain

#### Tool Execution
1. Primary tool execution
2. Retry with adjusted params
3. Alternative tool selection
4. Manual intervention request

#### Extraction
1. Universal Extractor
2. Cached selectors
3. Heuristic patterns
4. LLM extraction

#### Browser Actions
1. Standard navigation
2. Wait for load
3. Retry with timeout increase
4. Error reporting

### Implementation
```python
from src.tools.fallback_manager import FallbackManager

manager = FallbackManager()
result = manager.execute_with_fallback(
    primary_tool=tool1,
    fallback_tools=[tool2, tool3],
    params=params
)
```

---

## 📈 Learning Manager

### Overview
Continuous improvement through usage patterns.

### Features
- **Success Tracking**: Monitor tool performance
- **Pattern Learning**: Identify successful strategies
- **Failure Analysis**: Learn from errors
- **Strategy Optimization**: Adjust approaches

### Metrics Tracked
- Tool success rates
- Extraction accuracy
- Response times
- Error frequencies

### Implementation
```python
from src.tools.learning_manager import get_learning_manager

manager = get_learning_manager()
manager.record_success(tool_name, context)
manager.record_failure(tool_name, error, context)
```

---

## 🔧 Configuration

### Environment Variables
```bash
# LLM Configuration
GOOGLE_API_KEY=your_key_here

# Supabase Configuration
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_key_here

# Logging
LOGGING_URL=http://localhost:3000/api/logging

# Browser
HEADLESS_BROWSER=true
BROWSER_TIMEOUT=60000
```

### Settings Management
```python
from src.core.config import settings

# Access configuration
api_key = settings.google_api_key
timeout = settings.browser_timeout
```

---

## 🐛 Troubleshooting

### Common Issues

#### Playwright Issues
- **Browser not closing**: Check shutdown handlers
- **Timeout errors**: Increase timeout settings
- **Session conflicts**: Clear session cache

#### Extraction Issues
- **No data found**: Check selector cache
- **Partial data**: Validate completeness
- **Slow extraction**: Review fallback chain

#### Multi-Agent Issues
- **Agent selection**: Verify routing strategy
- **Context loss**: Check memory service
- **Tool conflicts**: Review tool registration

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📚 References

### Internal Documentation
- [Architecture](ARCHITECTURE.md)
- [API Contract](API_CONTRACT.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Session Management](SESSION_MANAGEMENT.md)

### External Resources
- [Playwright Documentation](https://playwright.dev)
- [LangChain Documentation](https://python.langchain.com)
- [Supabase Documentation](https://supabase.com/docs)

---

**Last Updated**: October 31, 2025  
**Maintained By**: KaryaKarta Development Team  
**Status**: ✅ Production Ready
