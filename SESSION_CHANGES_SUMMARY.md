# All Code Changes Made This Session

## Summary
Fixed infinite hangs caused by blocking async Playwright calls without timeouts.

## Files Modified (5 total)

### 1. ✅ reason_agent.py
**Change**: LLM now generates parameters in decomposition steps
**Lines**: Multiple changes to parameter generation logic
**Why**: Allows LLM to generate dynamic parameters instead of hardcoding

### 2. ✅ task_decomposer.py  
**Change**: Uses LLM-provided parameters directly
**Lines**: Parameter extraction from LLM response
**Why**: Supports dynamic parameter generation

### 3. ✅ universal_extractor.py
**Changes**:
- Line 44-51: Removed excessive logging (26 log lines removed)
- Line 65: Reduced timeout from 120s → 30s
- Line 128-145: Added 30s timeout to serial fallback extraction
**Why**: 
- Cleaner logs
- Faster timeouts prevent long hangs
- Serial fallback was missing timeout entirely!

### 4. ✅ chart_extractor.py
**Changes**:
- Line 8: Added `import asyncio`
- Line 147-150: Removed page.evaluate() check, replaced with simple 2s delay
- Line 164: Wrapped `page.content()` in `asyncio.wait_for(timeout=5.0)` - 6 instances total:
  * Line 164: UniversalExtractor section
  * Line 197: pandas section  
  * Line 508: _extract_with_heuristics
  * Line 557: _llm_fill_missing_fields
  * Line 606: _llm_extract_all
  * One more in another method
- Line 217-223: Disabled Site Intelligence (commented out)
**Why**: 
- page.content() was blocking forever if page in bad state
- Site Intelligence needs better agent implementation

### 5. ✅ main.py
**Changes**:
- Line 37-82: Added shutdown handler for Playwright cleanup
**Why**: Properly closes browsers, stops event loops on Ctrl+C

### 6. ✅ BLOCKING_CALLS_AUDIT.md (new file)
**Created**: Documentation of all blocking calls found

## Root Causes Fixed

### Issue 1: `page.content()` blocks forever
**Problem**: Playwright's `page.content()` waits for page to be stable. If page is loading/navigating, waits indefinitely.
**Solution**: Wrapped ALL 6 instances in `asyncio.wait_for(timeout=5.0)`

### Issue 2: `page.evaluate()` blocks forever
**Problem**: Checking document.readyState could hang if page in transition
**Solution**: Removed entirely, replaced with simple 2-second delay

### Issue 3: Serial fallback had no timeout
**Problem**: If parallel extraction failed, serial mode ran without any timeout
**Solution**: Added 30s timeout wrapper around serial extraction

### Issue 4: Playwright browsers not closing on shutdown
**Problem**: Event loops and browsers stayed open after Ctrl+C
**Solution**: Added FastAPI shutdown handler to close all resources

## Still To Fix

### Issue 5: _extract_with_locators() hanging
**Problem**: Many await calls without timeouts:
- `await table.count()`
- `await rows.count()`
- `await cell.text_content()`
- etc.

**Solution Needed**: Wrap entire _extract_with_locators() in timeout

## Testing Status
- ✅ UniversalExtractor works (extracted 634 cards)
- ✅ Logging cleaned up
- ❌ Still hangs at "Trying Playwright locators..."
- ❌ Server won't close on Ctrl+C (Playwright still blocking)

## Next Steps
1. Add timeout wrapper to _extract_with_locators()
2. Add timeout wrapper to _extract_from_item()
3. Test that extraction completes
4. Test that Ctrl+C exits cleanly
