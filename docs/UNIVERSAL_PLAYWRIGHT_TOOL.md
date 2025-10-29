# Universal Playwright Tool - Complete Documentation

## Overview

The Universal Playwright Tool provides a **dynamic interface** to the entire Playwright Page API, allowing the agent to execute ANY Playwright method without requiring individual tool implementations for each method.

## Key Features

✅ **Dynamic Method Execution**: Call any Playwright Page method by name  
✅ **Comprehensive API Coverage**: Access to 100+ Playwright methods  
✅ **Flexible Parameter Handling**: Support for selectors, arguments, and options  
✅ **Session Management**: Persistent browser sessions across multiple operations  
✅ **Automatic Serialization**: Handles complex return types (bytes, objects, etc.)  
✅ **Browserless Cloud Support**: Works with remote and local browsers  

## Architecture

### Tool Implementation

**File**: `karyakarta-agent/src/tools/playwright_universal.py`

**Main Class**: `UniversalPlaywrightTool`

**Key Methods**:
- `execute()`: Main entry point for tool execution
- `_execute_playwright_method()`: Async method execution
- `_call_page_method()`: Dynamic method dispatch
- `_serialize_result()`: Result type handling

### Integration

The tool is integrated into `agent_logic.py` alongside other tools and is available to both AgentManager and MultiAgentManager systems.

## Usage Guide

### Basic Usage

The agent can call the tool with these parameters:

```python
{
    "method": "goto",  # Playwright method name
    "url": "https://example.com",  # Optional URL for navigation
    "selector": "#button",  # Optional CSS selector
    "args": {"wait_until": "networkidle"},  # Optional arguments
    "close_after": False  # Whether to close browser after
}
```

### Common Method Categories

#### 1. Navigation Methods

**goto** - Navigate to URL
```json
{
    "method": "goto",
    "args": {"url": "https://example.com", "wait_until": "networkidle"}
}
```

**go_back** - Go back in history
```json
{
    "method": "go_back"
}
```

**go_forward** - Go forward in history
```json
{
    "method": "go_forward"
}
```

**reload** - Reload page
```json
{
    "method": "reload"
}
```

#### 2. Interaction Methods

**click** - Click element
```json
{
    "method": "click",
    "selector": "button.submit"
}
```

**fill** - Fill input field
```json
{
    "method": "fill",
    "selector": "input[name='email']",
    "args": {"value": "test@example.com"}
}
```

**press** - Press keyboard key
```json
{
    "method": "press",
    "selector": "input",
    "args": {"key": "Enter"}
}
```

**hover** - Hover over element
```json
{
    "method": "hover",
    "selector": ".menu-item"
}
```

**check** - Check checkbox
```json
{
    "method": "check",
    "selector": "input[type='checkbox']"
}
```

**uncheck** - Uncheck checkbox
```json
{
    "method": "uncheck",
    "selector": "input[type='checkbox']"
}
```

**select_option** - Select dropdown option
```json
{
    "method": "select_option",
    "selector": "select",
    "args": {"value": "option1"}
}
```

#### 3. Content Extraction Methods

**content** - Get full HTML
```json
{
    "method": "content"
}
```

**inner_text** - Get element text
```json
{
    "method": "inner_text",
    "selector": "h1"
}
```

**inner_html** - Get element HTML
```json
{
    "method": "inner_html",
    "selector": ".container"
}
```

**text_content** - Get text content
```json
{
    "method": "text_content",
    "selector": "p"
}
```

**get_attribute** - Get element attribute
```json
{
    "method": "get_attribute",
    "selector": "a",
    "args": {"name": "href"}
}
```

#### 4. Screenshot Methods

**screenshot** - Take screenshot
```json
{
    "method": "screenshot",
    "args": {
        "path": "screenshot.png",
        "full_page": true
    }
}
```

Returns: Base64-encoded image string

#### 5. Waiting Methods

**wait_for_selector** - Wait for element
```json
{
    "method": "wait_for_selector",
    "selector": ".loading",
    "args": {"state": "hidden"}
}
```

**wait_for_load_state** - Wait for page load
```json
{
    "method": "wait_for_load_state",
    "args": {"state": "networkidle"}
}
```

**wait_for_timeout** - Wait for time
```json
{
    "method": "wait_for_timeout",
    "args": {"timeout": 2000}
}
```

#### 6. Evaluation Methods

**evaluate** - Execute JavaScript
```json
{
    "method": "evaluate",
    "args": {"expression": "document.title"}
}
```

#### 7. Element Query Methods

**query_selector** - Find single element
```json
{
    "method": "query_selector",
    "selector": ".item"
}
```

**query_selector_all** - Find all elements
```json
{
    "method": "query_selector_all",
    "selector": ".items"
}
```

## Complete Method Reference

### Navigation & Lifecycle
- `goto(url, **options)` - Navigate to URL
- `go_back(**options)` - Navigate back
- `go_forward(**options)` - Navigate forward
- `reload(**options)` - Reload page
- `close(**options)` - Close page
- `bring_to_front()` - Bring page to front

### Content & DOM
- `content()` - Get HTML content
- `title()` - Get page title
- `url` - Get current URL
- `frame(name_or_url)` - Get frame
- `frames` - Get all frames
- `main_frame` - Get main frame

### Element Interaction
- `click(selector, **options)` - Click element
- `dblclick(selector, **options)` - Double click
- `fill(selector, value, **options)` - Fill input
- `press(selector, key, **options)` - Press key
- `type(selector, text, **options)` - Type text
- `hover(selector, **options)` - Hover element
- `focus(selector, **options)` - Focus element
- `check(selector, **options)` - Check checkbox
- `uncheck(selector, **options)` - Uncheck checkbox
- `select_option(selector, values, **options)` - Select option
- `set_input_files(selector, files, **options)` - Upload files
- `tap(selector, **options)` - Tap element
- `drag_and_drop(source, target, **options)` - Drag and drop

### Content Extraction
- `inner_text(selector, **options)` - Get inner text
- `inner_html(selector, **options)` - Get inner HTML
- `text_content(selector, **options)` - Get text content
- `get_attribute(selector, name, **options)` - Get attribute
- `input_value(selector, **options)` - Get input value

### Element State
- `is_visible(selector, **options)` - Check visibility
- `is_hidden(selector, **options)` - Check hidden
- `is_enabled(selector, **options)` - Check enabled
- `is_disabled(selector, **options)` - Check disabled
- `is_checked(selector, **options)` - Check checked
- `is_editable(selector, **options)` - Check editable

### Waiting & Timing
- `wait_for_selector(selector, **options)` - Wait for element
- `wait_for_load_state(state, **options)` - Wait for load
- `wait_for_timeout(timeout)` - Wait for time
- `wait_for_function(expression, **options)` - Wait for condition
- `wait_for_url(url, **options)` - Wait for URL

### Screenshots & PDFs
- `screenshot(**options)` - Take screenshot
- `pdf(**options)` - Generate PDF

### JavaScript Execution
- `evaluate(expression, **options)` - Execute JS
- `evaluate_handle(expression, **options)` - Execute JS (returns handle)
- `add_script_tag(**options)` - Add script tag
- `add_style_tag(**options)` - Add style tag

### Element Queries
- `query_selector(selector)` - Find one element
- `query_selector_all(selector)` - Find all elements
- `locator(selector)` - Create locator
- `get_by_role(role, **options)` - Get by ARIA role
- `get_by_text(text, **options)` - Get by text
- `get_by_label(text, **options)` - Get by label
- `get_by_placeholder(text, **options)` - Get by placeholder
- `get_by_alt_text(text, **options)` - Get by alt text
- `get_by_title(text, **options)` - Get by title
- `get_by_test_id(testId)` - Get by test ID

### Configuration
- `set_viewport_size(size)` - Set viewport size
- `set_extra_http_headers(headers)` - Set HTTP headers
- `set_default_timeout(timeout)` - Set default timeout
- `set_default_navigation_timeout(timeout)` - Set navigation timeout
- `emulate_media(**options)` - Emulate media
- `set_content(html, **options)` - Set HTML content

### Events & Routing
- `route(url, handler)` - Intercept requests
- `unroute(url, handler)` - Remove route
- `route_from_har(har, **options)` - Route from HAR

## Advanced Usage Examples

### Multi-Step Workflow

```python
# Step 1: Navigate
{
    "method": "goto",
    "args": {"url": "https://example.com/login"}
}

# Step 2: Fill form
{
    "method": "fill",
    "selector": "input[name='username']",
    "args": {"value": "user@example.com"}
}

# Step 3: Submit
{
    "method": "click",
    "selector": "button[type='submit']"
}

# Step 4: Wait for navigation
{
    "method": "wait_for_load_state",
    "args": {"state": "networkidle"}
}

# Step 5: Extract data
{
    "method": "inner_text",
    "selector": ".welcome-message"
}

# Step 6: Close (optional)
{
    "method": "close",
    "close_after": true
}
```

### JavaScript Evaluation

```python
# Execute complex JavaScript
{
    "method": "evaluate",
    "args": {
        "expression": """
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                return links.map(link => ({
                    text: link.textContent,
                    href: link.href
                }));
            }
        """
    }
}
```

### Screenshot with Options

```python
{
    "method": "screenshot",
    "args": {
        "full_page": true,
        "type": "png",
        "quality": 90,
        "clip": {
            "x": 0,
            "y": 0,
            "width": 800,
            "height": 600
        }
    }
}
```

## Error Handling

The tool includes comprehensive error handling:

```python
try:
    result = universal_playwright_tool.execute(
        method="click",
        selector="#button"
    )
    if result.is_success():
        print("Success:", result.data)
    else:
        print("Error:", result.error)
except Exception as e:
    print("Exception:", str(e))
```

## Browser Session Management

### Persistent Sessions

The tool maintains browser sessions across multiple calls:
- First call: Creates browser and page
- Subsequent calls: Reuses existing browser/page
- Explicit close: Use `close_after=True` or call `close()` method

### Browserless Cloud

Set environment variable for cloud browsers:
```bash
BROWSERLESS_API_KEY=your_key_here
```

## Performance Considerations

1. **Session Reuse**: Reuse browser sessions for multiple operations
2. **Timeout Configuration**: Adjust timeouts based on page complexity
3. **Wait Strategies**: Use appropriate wait methods (selector, load state)
4. **Screenshot Size**: Use `clip` option for large screenshots
5. **Browser Closure**: Close browsers when done to free resources

## Limitations

1. **Async Only**: All Playwright operations are async
2. **Serialization**: Complex objects converted to strings
3. **Element Handles**: Limited support for element handle passing
4. **File Uploads**: Requires local file paths
5. **Downloads**: Handled separately (see download events)

## Integration with Multi-Agent System

The Universal Playwright Tool is registered in the ToolRegistry with:
- **Category**: SCRAPING
- **Cost Level**: LOW
- **Average Latency**: 3.0 seconds
- **Reliability**: 95%

This allows the MultiAgentManager to intelligently route browser automation tasks to this tool.

## Future Enhancements

Potential improvements:
1. ✨ WebSocket support for real-time interactions
2. ✨ Enhanced file upload/download handling
3. ✨ Video recording capabilities
4. ✨ Network traffic inspection
5. ✨ Mobile device emulation presets
6. ✨ Parallel browser session management

## Troubleshooting

### Common Issues

**Issue**: "Method not found on Playwright Page object"
- **Solution**: Check method name spelling and Playwright version

**Issue**: "Selector not found"
- **Solution**: Use `wait_for_selector` first, verify selector is correct

**Issue**: "Timeout exceeded"
- **Solution**: Increase timeout in args or use appropriate wait strategy

**Issue**: "Browser not initialized"
- **Solution**: Include URL in first call or call `goto` first

## Conclusion

The Universal Playwright Tool provides the agent with complete access to browser automation capabilities, enabling sophisticated web scraping, testing, and interaction workflows without requiring individual tool implementations for each Playwright method.

**Total Methods Available**: 100+  
**Integration Status**: ✅ Complete  
**Production Ready**: ✅ Yes

---

**Last Updated**: 2025-10-28  
**Tool**: UniversalPlaywrightTool  
**Location**: `karyakarta-agent/src/tools/playwright_universal.py`
