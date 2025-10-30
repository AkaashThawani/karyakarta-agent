# Fallback System with Learning

## Overview

A comprehensive tool fallback architecture with intelligent learning that keeps ALL tools as backup options for Playwright. The system learns from every execution and optimizes tool selection over time.

## Architecture

### 1. Learning Manager (`learning_manager.py`)
Tracks performance of ALL tools across ALL sites.

**Features:**
- Records every tool execution (success/failure)
- Tracks success rates per tool per site
- Calculates reliability scores (recent + overall)
- Provides intelligent tool recommendations
- Auto-saves performance data

**Example Usage:**
```python
from src.tools.learning_manager import get_learning_manager

learning_manager = get_learning_manager()

# Record execution
learning_manager.record_tool_execution(
    url="example.com",
    tool_name="playwright_execute",
    success=True,
    response_time=0.5
)

# Get best tool for site
best_tool, confidence = learning_manager.get_best_tool_for_site(
    url="example.com",
    candidate_tools=["playwright_execute", "browse_advanced", "scraper"]
)
# Returns: ("playwright_execute", 0.95)

# Get fallback chain
chain = learning_manager.get_fallback_chain(
    url="example.com",
    all_tools=["playwright_execute", "browse_advanced", "scraper"]
)
# Returns: ["playwright_execute", "browse_advanced", "scraper"]
# (ordered by historical success rate)
```

### 2. Fallback Manager (`fallback_manager.py`)
Manages tool fallback chains using learning data.

**Tool Hierarchies:**
```python
TOOL_HIERARCHIES = {
    "browser_automation": [
        "playwright_execute",  # Primary
        "browse_advanced",     # Fallback 1
        "browse_forms",        # Fallback 2
        "scraper"              # Fallback 3
    ],
    "data_extraction": [
        "chart_extractor",     # Primary
        "extract_advanced",    # Fallback 1
        "extract_structured",  # Fallback 2
        "extractor"            # Fallback 3
    ],
    "web_scraping": [
        "playwright_execute",  # Primary
        "browse_advanced",     # Fallback 1
        "scraper"              # Fallback 2
    ]
}
```

**Example Usage:**
```python
from src.tools.fallback_manager import get_fallback_manager

fallback_manager = get_fallback_manager()

def tool_executor(tool_name, params):
    # Execute the specified tool
    if tool_name == "playwright_execute":
        return playwright_tool.execute(params)
    elif tool_name == "browse_advanced":
        return browse_tool.execute(params)
    # ... etc

success, result, tool_used = fallback_manager.execute_with_fallback(
    task_type="browser_automation",
    url="example.com",
    tool_executor=tool_executor,
    task_params={"action": "click", "selector": "button"}
)
```

## Learning Process

### Initial State (No Data)
```
User: "Click button on example.com"
System: Tries tools in default order:
  1. playwright_execute → Success ✅
  Records: example.com → playwright_execute (100% success)
```

### After Some Learning
```
User: "Click button on example.com"
System: Checks learning data:
  - playwright_execute: 95% success (10 attempts)
  - browse_advanced: 80% success (5 attempts)
  Tries: playwright_execute first (best score)
  
  If fails: Falls back to browse_advanced
  Records: Both results for future optimization
```

### Adaptive Learning
```
Scenario: Playwright starts failing on example.com

Attempt 1: playwright_execute → Fail ❌
  Records: example.com → playwright_execute (90% success now)
  Fallback: browse_advanced → Success ✅
  Records: example.com → browse_advanced (85% success)

Attempt 2: playwright_execute → Fail ❌
  Records: example.com → playwright_execute (80% success now)
  Fallback: browse_advanced → Success ✅
  Records: example.com → browse_advanced (90% success)

Attempt 3: System learns browse_advanced is now better
  Tries: browse_advanced first! (higher recent success)
  Result: Success ✅ (faster, no wasted attempt)
```

## Reliability Scoring

```python
reliability_score = (overall_success_rate * 0.3) + (recent_success_rate * 0.7)
```

**Why this formula?**
- 70% weight on recent (last 10 attempts)
- 30% weight on overall history
- Adapts quickly to changes
- Still respects long-term patterns

## Data Storage

### Location
```
karyakarta-agent/learning_cache/tool_performance.json
```

### Structure
```json
{
  "example.com": {
    "playwright_execute": {
      "tool_name": "playwright_execute",
      "site": "example.com",
      "total_attempts": 10,
      "successful_attempts": 9,
      "failed_attempts": 1,
      "success_rate": 0.9,
      "recent_success_rate": 0.8,
      "avg_response_time": 0.5,
      "reliability_score": 0.83,
      "last_success": "2025-10-29T23:00:00",
      "last_failure": "2025-10-29T22:00:00",
      "recent_successes": [true, true, false, true, true, true, true, true, false, true]
    },
    "browse_advanced": {
      "tool_name": "browse_advanced",
      "site": "example.com",
      "total_attempts": 5,
      "successful_attempts": 4,
      "success_rate": 0.8,
      "recent_success_rate": 1.0,
      "avg_response_time": 0.7,
      "reliability_score": 0.94,
      "recent_successes": [true, true, true, false, true]
    }
  }
}
```

## Benefits

### 1. Robustness
✅ Never complete failure (multiple fallbacks)
✅ Handles edge cases gracefully
✅ Self-healing (adapts when tools break)

### 2. Performance
✅ Uses fastest tool for each site
✅ Skips tools that historically fail
✅ Minimizes wasted attempts

### 3. Intelligence
✅ Learns from every execution
✅ Adapts to site changes
✅ Improves over time

### 4. Transparency
✅ Clear logging at each step
✅ Performance metrics available
✅ Easy to debug

## Integration Example

### Executor Agent Integration
```python
from src.tools.fallback_manager import get_fallback_manager

class ExecutorAgent:
    def execute_browser_task(self, url: str, params: Dict[str, Any]):
        fallback_manager = get_fallback_manager()
        
        def executor(tool_name: str, tool_params: Dict[str, Any]):
            # Get tool instance
            tool = self.get_tool(tool_name)
            if not tool:
                raise Exception(f"Tool {tool_name} not found")
            
            # Execute
            return tool.execute(**tool_params)
        
        success, result, tool_used = fallback_manager.execute_with_fallback(
            task_type="browser_automation",
            url=url,
            tool_executor=executor,
            task_params=params,
            max_attempts=3  # Try up to 3 tools
        )
        
        if success:
            return AgentResult.success_result(
                data=result,
                metadata={"tool_used": tool_used}
            )
        else:
            return AgentResult.error_result(
                error=f"All tools failed: {result}"
            )
```

## Monitoring

### Get Site Stats
```python
stats = learning_manager.get_site_stats("example.com")
# Returns all tool performance data for the site
```

### Get Global Rankings
```python
rankings = learning_manager.get_global_tool_ranking()
# Returns: [("playwright_execute", 0.92), ("scraper", 0.85), ...]
```

### Clear Site Data
```python
learning_manager.clear_site_data("example.com")
# Clears all performance data for site (fresh start)
```

## Tool Status

### Active Tools (With Fallbacks)
1. **playwright_execute** - Primary browser automation
2. **browse_advanced** - Fallback browser tools
3. **browse_forms** - Form-specific fallback
4. **scraper** - HTTP scraping fallback
5. **chart_extractor** - Primary data extraction
6. **extract_advanced** - Extraction fallback 1
7. **extract_structured** - Extraction fallback 2
8. **extractor** - Extraction fallback 3
9. **calculator** - Math operations
10. **analysis_tools** - Data analysis

### Tool Purpose
All previously "unused" tools are now **active fallbacks**:
- They serve as backup when primary tools fail
- System learns which tool works best where
- No tool is wasted
- Complete coverage of edge cases

## Future Enhancements

### Planned Features
1. **A/B Testing**: Periodically try different tools to discover improvements
2. **Time-based Learning**: Weight recent attempts more heavily
3. **Error Pattern Recognition**: Learn which errors benefit from which fallback
4. **Cross-site Learning**: Apply patterns from similar sites
5. **Performance Optimization**: Cache tool instances for faster fallback

## Conclusion

This fallback system transforms ALL tools into a unified, intelligent system:
- **Before**: Unused tools sitting idle
- **After**: Active fallback chain with learning
- **Result**: Robust, self-improving, never-failing system

The system gets smarter with every execution and adapts to changing conditions automatically.
