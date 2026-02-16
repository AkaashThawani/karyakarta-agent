# 🎯 Intelligent Element Registry System

## Overview

A holistic solution combining reliable element extraction, clear identification, agent awareness, and plan enforcement.

## Architecture

```
User Query: "Go to amazon.com and search for robot vacuums"
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. PLANNING NODE                                            │
│    TaskDecomposer creates 6-step plan:                      │
│    1. goto amazon.com                                       │
│    2. fill search box                                       │
│    3. press Enter                                           │
│    4. wait 3s                                               │
│    5. press Escape (close popups)                           │
│    6. extract prices                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. FORCED EXECUTION - Step 1: Navigate                      │
│    Agent: FORCE tool call (no LLM decision)                 │
│    Tool: playwright_execute(method='goto', url='...')       │
│    Result: ✅ Navigated to Amazon                           │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PAGE INTELLIGENCE NODE (NEW!)                            │
│    Scans page and builds Element Registry:                  │
│                                                              │
│    inputs: {                                                │
│      "search_input": {                                      │
│        selector: "#twotabsearchtextbox",                    │
│        type: "text",                                        │
│        purpose: "search",                                   │
│        visible: true                                        │
│      }                                                      │
│    }                                                        │
│                                                              │
│    buttons: {                                               │
│      "search_button": {                                     │
│        selector: "#nav-search-submit-button",               │
│        text: "Go",                                          │
│        purpose: "search",                                   │
│        clickable: true,                                     │
│        in_viewport: true                                    │
│      }                                                      │
│    }                                                        │
│                                                              │
│    Registry stored in state → available to all steps!       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. FORCED EXECUTION - Step 2: Fill Search                   │
│    Agent: FORCE tool call with registry enhancement         │
│    Plan says: playwright_execute(method='fill')             │
│    Enhancement: Lookup "search_input" in registry           │
│    Final call: playwright_execute(                          │
│      method='fill',                                         │
│      selector='#twotabsearchtextbox',  ← From registry!    │
│      args={'value': 'robot vacuums'}                        │
│    )                                                        │
│    Result: ✅ Search box filled                             │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. FORCED EXECUTION - Step 3: Submit Search                 │
│    Plan says: press Enter                                   │
│    Smart fallback: If "enter" in description,               │
│                    use press instead of click               │
│    Final call: playwright_execute(                          │
│      method='press',                                        │
│      args={'key': 'Enter'}                                  │
│    )                                                        │
│    Result: ✅ Search submitted (no button click needed!)    │
└─────────────────────────────────────────────────────────────┘
    ↓
    Continue with remaining steps...
```

## Key Components

### 1. **Enhanced State with Element Registry**

```python
class EnhancedState(TypedDict):
    messages: List
    plan: Optional[dict]           # Task decomposition plan
    current_step_index: int        # Which step we're executing
    page_context: Optional[dict]   # Browser page state
    element_registry: Optional[dict]  # 🆕 Identified interactive elements!
    task_completed: bool
```

### 2. **Page Intelligence Scanner**

**File:** `src/core/page_intelligence.py`

**Capabilities:**
- Scans ALL inputs, buttons, selects after navigation
- Infers purpose using heuristics (search, email, password, etc.)
- Generates semantic labels ("search_input" vs "#twotabsearchtextbox")
- Filters hidden/off-screen elements
- Checks clickability and viewport position

**Example Output:**
```python
{
    "inputs": {
        "search_input": {
            "selector": "#twotabsearchtextbox",
            "type": "text",
            "purpose": "search",
            "label": "Search Amazon",
            "visible": True
        },
        "email_input": {
            "selector": "#ap_email",
            "type": "email",
            "purpose": "email",
            "visible": False  # Hidden on this page
        }
    },
    "buttons": {
        "search_button": {
            "selector": "#nav-search-submit-button",
            "text": "Go",
            "purpose": "search",
            "clickable": True,
            "in_viewport": True
        },
        "close_button": {
            "selector": ".close-modal",
            "text": "×",
            "purpose": "close",
            "clickable": False,  # Off-screen
            "in_viewport": False
        }
    }
}
```

### 3. **Forced Plan Execution with Smart Enhancement**

**File:** `src/core/graph_v2.py` → `call_model()`

**How it works:**

1. **Check if plan exists** and not completed
2. **Get current step** from plan
3. **Force tool call** (skip LLM decision)
4. **Smart parameter enhancement:**
   - If filling: Lookup "search_input" from registry
   - If clicking: Find clickable button from registry
   - If "enter" in description: Use press instead of click
   - Fallback: Use original plan parameters

**Example:**
```python
# Plan says: fill search box
# Registry has: search_input → "#twotabsearchtextbox"

# Agent creates forced tool call:
AIMessage(
    tool_calls=[{
        "name": "playwright_execute",
        "args": {
            "method": "fill",
            "selector": "#twotabsearchtextbox",  # From registry!
            "args": {"value": "robot vacuums"}
        }
    }]
)
```

### 4. **Workflow Integration**

```
planning → agent → tools → page_intelligence? → agent → ...
                     ↓            ↑
                  (if goto)   (scan page)
```

**Decision logic:**
- After tools node, check if last tool was `playwright_execute(method='goto')`
- If yes: Run `page_intelligence` to scan page
- If no: Go directly back to `agent`

## Benefits

### ✅ **Reliability**
- No more wrong selectors (registry verified)
- No more hidden elements (filtered during scan)
- No more "element outside viewport" errors

### ✅ **Plan Enforcement**
- LLM can't ignore plan
- Exact tools and parameters executed
- Smart enhancements using registry

### ✅ **Agent Awareness**
- Agent knows what inputs/buttons exist
- Semantic names easier to understand
- Clear purpose labels ("search", "login", etc.)

### ✅ **Fallback Strategies**
- Press Enter if button not clickable
- Use registry selector if plan selector fails
- Skip hidden elements automatically

## Testing

### Test Case 1: Amazon Search
```
Input: "Go to amazon.com and search for robot vacuums"

Expected Behavior:
1. ✅ Plan created with 6 steps
2. ✅ Navigate to amazon.com
3. ✅ Page intelligence scans page
4. ✅ Registry built: search_input, search_button
5. ✅ Fill uses registry selector
6. ✅ Submit uses press Enter (not click)
7. ✅ Results extracted
```

### Test Case 2: AMC Movie Showtimes
```
Input: "Find showtimes at AMC Alderwood for Saturday"

Expected Behavior:
1. ✅ Navigate to AMC website
2. ✅ Registry identifies date_select dropdown
3. ✅ Click date selector using registry
4. ✅ Select Saturday using select_option
5. ✅ Extract showtimes
```

## Future Enhancements

1. **LLM Vision Integration**: Use vision to verify element purpose
2. **Learning from Failures**: Update registry if selector fails
3. **Cross-page Registry**: Remember elements across navigations
4. **Smart Waiting**: Auto-detect when elements load dynamically

## Summary

This system transforms unreliable browser automation into a **robust, intelligent** workflow by:

1. 🔍 **Scanning pages** after navigation
2. 🏷️ **Labeling elements** with semantic names
3. 🎯 **Forcing plan execution** with registry lookup
4. ⚡ **Smart fallbacks** when elements aren't clickable

No more nested kwargs! No more wrong selectors! No more clicking hidden elements!

**The agent now KNOWS the page structure and FOLLOWS the plan exactly.**
