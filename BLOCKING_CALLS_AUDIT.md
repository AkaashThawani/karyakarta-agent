# Blocking Async Calls Audit

## 🔴 Critical Blocking Calls Found

### chart_extractor.py
1. **Line 142**: `await page.goto(url, wait_until='domcontentloaded', timeout=10000)` ✅ Has timeout
2. **Line 147**: `await page.wait_for_timeout(2000)` ✅ Safe - simple sleep
3. **Line 161**: `html = await page.content()` ❌ **NO TIMEOUT - CAN HANG FOREVER!**
4. **Line 185**: `html = await page.content()` ❌ **NO TIMEOUT - CAN HANG FOREVER!**
5. **Line 504**: `html = await page.content()` ❌ **NO TIMEOUT**
6. **Line 553**: `html = await page.content()` ❌ **NO TIMEOUT**

### universal_extractor.py
- Uses `asyncio.timeout(30)` wrapper ✅ But if `page.content()` blocks, timeout won't help!

## 🎯 Root Cause

`page.content()` is a Playwright method that:
1. Waits for the page to be in a stable state
2. If page is navigating/loading, it waits indefinitely
3. **Has no built-in timeout** - must be wrapped!

## ✅ Solution

Wrap ALL `page.content()` calls in `asyncio.wait_for()`:

```python
# Before (blocks forever)
html = await page.content()

# After (times out)
html = await asyncio.wait_for(
    page.content(),
    timeout=5.0  # 5 seconds max
)
```

## 📝 Changes Made This Session

1. ✅ Updated reason_agent.py - LLM generates parameters
2. ✅ Updated task_decomposer.py - uses LLM parameters
3. ✅ Updated universal_extractor.py - reduced timeout 120s→30s, added serial fallback timeout
4. ❌ Updated chart_extractor.py - removed page state check BUT didn't fix page.content()!

## 🔧 Fix Needed

Wrap ALL `page.content()` calls in chart_extractor.py with timeouts!
