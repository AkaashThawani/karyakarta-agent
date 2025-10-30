# Site Intelligence System - Zero-Hardcoded Site Learning

## 🎯 Overview

The Site Intelligence System is a revolutionary approach to web automation that uses LLM-driven discovery to learn site structure with **ZERO hardcoded assumptions**. Unlike traditional selectors that require manual mapping, this system:

- ✅ Discovers element types automatically
- ✅ Classifies elements by purpose (not just tag type)
- ✅ Builds semantic understanding of sites
- ✅ Caches knowledge for instant reuse
- ✅ Adapts to any site structure

---

## 🏗️ Architecture

### Three-Layer Learning System

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Universal DOM Extraction                      │
│  - Extract ALL interactive elements                     │
│  - No filtering, no assumptions                         │
│  - Complete attribute capture                           │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: LLM Type Discovery                           │
│  - LLM groups similar elements                         │
│  - Discovers site-specific categories                  │
│  - Names types semantically                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: LLM Element Classification                   │
│  - LLM determines purpose of each element              │
│  - Semantic naming (search_input, post_filter)         │
│  - Confidence scoring + reasoning                      │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 Complete Flow

### First Visit (Learning Mode)

```
User: "Go to reddit.com and search Games"

Step 1: Check Cache
→ No cache found for reddit.com

Step 2: Trigger Site Intelligence
→ page.evaluate() extracts ALL elements
→ Found: 150 interactive elements

Step 3: LLM Discovers Types
→ Analyzing elements...
→ Discovered types:
   - search_system (search input, search button)
   - content_sorting (hot, new, top tabs)
   - post_filters (time, subreddit dropdowns)
   - navigation (home, profile links)

Step 4: LLM Classifies Elements
→ Batch 1: 20 elements classified
→ Batch 2: 20 elements classified
→ ...
→ Total: 85 elements classified

Step 5: Build Schema
→ Created semantic map:
   {
     "main_search_input": "input[name='q']",
     "search_button": "button[type='submit']",
     "sort_by_hot": "button[data-filter='hot']",
     "time_filter_dropdown": "select[name='t']",
     ...
   }

Step 6: Save to Cache
→ Saved to: selector_cache/reddit.com.json
→ Section: "site_intelligence"

Step 7: Execute Task
→ Use learned selectors
→ Fill "main_search_input": "Games"
→ Click "search_button"
```

### Second Visit (Instant Execution)

```
User: "Go to reddit, search music, filter top 24hrs"

Step 1: Load Cache
→ Found: reddit.com.json (age: 2 days)
→ Loaded: site_intelligence section

Step 2: Execute Immediately
→ Use cached selectors:
   - main_search_input: "input[name='q']"
   - sort_by_top: "button[data-filter='top']"
   - time_filter_dropdown: "select[name='t']"

Step 3: No Learning Needed!
→ 10x faster execution
→ No trial-and-error
→ No LLM calls for classification
```

---

## 📁 Cache Structure

### selector_cache/reddit.com.json

```json
{
  "site_intelligence": {
    "url": "reddit.com",
    "learned_at": "2025-10-29T16:00:00Z",
    "total_elements_found": 150,
    "classified_elements": 85,
    "discovered_types": [
      {
        "type_name": "search_system",
        "description": "Reddit's search functionality",
        "importance": "high",
        "element_indices": [0, 1, 2]
      },
      {
        "type_name": "content_sorting",
        "description": "Ways to sort posts (hot, new, top, rising)",
        "importance": "high",
        "element_indices": [10, 11, 12, 13]
      },
      {
        "type_name": "post_filters",
        "description": "Filters for time range and subreddit",
        "importance": "medium",
        "element_indices": [20, 21]
      }
    ],
    "elements": {
      "main_search_input": {
        "selector": "input[name='q']",
        "purpose": "Primary search functionality for finding content",
        "category": "search_system",
        "confidence": 0.98,
        "reasoning": "Input with name='q', type='search', search placeholder"
      },
      "search_button": {
        "selector": "button[type='submit']",
        "purpose": "Submit search query",
        "category": "search_system",
        "confidence": 0.95,
        "reasoning": "Submit button adjacent to search input"
      },
      "sort_by_hot": {
        "selector": "button[data-filter='hot']",
        "purpose": "Filter posts by 'hot' algorithm",
        "category": "content_sorting",
        "confidence": 0.92,
        "reasoning": "Button with 'hot' text, sorting control"
      },
      "sort_by_new": {
        "selector": "button[data-filter='new']",
        "purpose": "Filter posts by newest first",
        "category": "content_sorting",
        "confidence": 0.92,
        "reasoning": "Button with 'new' text, sorting control"
      },
      "time_filter_dropdown": {
        "selector": "select[name='t']",
        "purpose": "Filter posts by time range (hour, day, week, etc.)",
        "category": "post_filters",
        "confidence": 0.90,
        "reasoning": "Dropdown with time range options"
      }
    }
  },
  "playwright_execute": {
    "search_input": {
      "best": "input[name='q']",
      "selectors": {
        "input[name='q']": {
          "success": 15,
          "fail": 0,
          "last_used": 1730239200,
          "avg_response_time": 0.22
        }
      },
      "fallbacks": []
    }
  }
}
```

---

## 🎯 Integration with Selector Map

### Lookup Hierarchy

```python
def get_selector(url, tool, hint):
    """
    1. Try site-specific learned selectors (fastest)
    2. Try site intelligence (LLM-learned)
    3. Fallback to generic selectors
    """
    
    domain = extract_domain(url)
    
    # 1. Site-specific learned (O(1))
    best = cache[domain][tool][hint]["best"]
    if best:
        return best  # Already learned, instant!
    
    # 2. Site intelligence (LLM-learned)
    intelligence = cache[domain]["site_intelligence"]
    if hint in intelligence["elements"]:
        return intelligence["elements"][hint]["selector"]
    
    # 3. Generic fallback
    return generic[tool][hint]["best"]
```

### Example Flow

```
User: "Search reddit for python"

1. get_selector("reddit.com", "playwright_execute", "search_input")
   
2. Check learned selectors:
   → Not found (first use)
   
3. Check site intelligence:
   → Found: "main_search_input"
   → Selector: "input[name='q']"
   → Return selector
   
4. Execute with selector
   → Success!
   
5. Promote selector:
   → Move from site_intelligence to playwright_execute
   → Mark as "best"
   → Future lookups skip step 3
```

---

## 🚀 Benefits

### 1. Zero Hardcoding

**Traditional Approach:**
```python
# ❌ Hardcoded - needs manual mapping per site
SELECTORS = {
    "reddit": {
        "search": "input[name='q']",
        "filter": "select[name='t']"
    },
    "twitter": {
        "search": "input[aria-label='Search']",
        "filter": "..."
    }
}
```

**Site Intelligence:**
```python
# ✅ Zero hardcoding - learns automatically
selector = intelligence.get_element_selector(domain, "search_input")
# LLM discovered and classified automatically!
```

### 2. Semantic Understanding

**Traditional:** "input[name='q']" (technical)

**Site Intelligence:** 
- Name: "main_search_input"
- Purpose: "Primary search functionality for finding content"
- Category: "search_system"
- Confidence: 0.98
- Reasoning: "Input with name='q', type='search', search placeholder"

### 3. Adaptability

- Works with ANY framework (React, Vue, Svelte, vanilla)
- Handles custom components
- Discovers site-specific patterns
- No manual updates needed

### 4. Self-Improving

```
Visit 1: Learn site (30s)
Visit 2: Instant execution (0s learning)
Visit 3: Even faster (promoted selectors)
```

---

## 🧪 Usage Example

### Basic Usage

```python
from src.tools.site_intelligence import SiteIntelligenceTool

# Initialize
intelligence = SiteIntelligenceTool(session_id="demo")

# Learn site (first time only)
schema = await intelligence.learn_site(
    url="https://reddit.com",
    page=playwright_page,
    llm_service=llm_service
)

# Get selector by semantic name
selector = intelligence.get_element_selector(
    domain="reddit.com",
    semantic_name="main_search_input"
)

# Use selector
await page.fill(selector, "python programming")
```

### Integration with Playwright

```python
# Automatic integration
from src.routing.selector_map import get_selector_map

selector_map = get_selector_map()

# Automatically checks site intelligence
selector = selector_map.get_selector(
    url="https://reddit.com",
    tool="playwright_execute",
    hint="search_input"  # Will match "main_search_input"
)
```

---

## 📊 Performance

| Metric | Traditional | Site Intelligence |
|--------|-------------|-------------------|
| **Setup Time** | Manual mapping | 30s one-time |
| **Subsequent Visits** | Same | Instant (cached) |
| **Adaptability** | Requires updates | Automatic |
| **Framework Support** | Limited | Universal |
| **Custom Components** | Manual | Automatic |
| **Maintenance** | High | Zero |

---

## 🔧 Configuration

### Cache Expiration

```python
# Default: 30 days
# Set in site_intelligence.py:

if age_days < 30:  # Cache valid for 30 days
    return existing
```

### Token Limits

```python
# Adjust element limits for token efficiency
.slice(0, 150)  # Max elements to extract
sample = elements[:30]  # Sample for type discovery
batch_size = 20  # Batch size for classification
```

---

## 🎉 Summary

The Site Intelligence System represents a paradigm shift in web automation:

**Old Way:**
- Manual selector mapping per site
- Hardcoded element types
- Requires updates on site changes
- Limited to known patterns

**New Way:**
- Automatic site learning
- LLM-driven discovery
- Adapts to changes automatically
- Works with ANY site structure

**Result:**
- ✅ Zero hardcoding
- ✅ Semantic understanding
- ✅ Self-improving
- ✅ Universal compatibility
- ✅ Production-ready

---

## 📚 See Also

- `SELECTOR_MAP_OPTIMIZATION.md` - Performance optimizations
- `src/tools/site_intelligence.py` - Implementation
- `src/routing/selector_map.py` - Integration
