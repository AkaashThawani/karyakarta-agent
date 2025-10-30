# Tool Usage Audit

## Date: October 29, 2025

## Summary
Out of 19 tool files in `src/tools/`, only **8 are actively used** in the current system.

---

## ✅ ACTIVELY USED TOOLS (8)

### Core Tools (Used in Production)
1. **search.py** - `SearchTool`
   - Usage: Google search functionality
   - Called by: `reason_agent.py` as `google_search`
   - Status: ✅ CRITICAL - Keep

2. **playwright_universal.py** - `UniversalPlaywrightTool`
   - Usage: Browser automation (all Playwright methods)
   - Called by: `reason_agent.py` as `playwright_execute`
   - Status: ✅ CRITICAL - Keep

3. **chart_extractor.py** - `PlaywrightChartExtractor`
   - Usage: Structured data extraction (tables, lists)
   - Called by: `playwright_universal.py` via `extract_chart` method
   - Status: ✅ CRITICAL - Keep

4. **site_intelligence.py** - `SiteIntelligenceTool`
   - Usage: Learn website structure with LLM + heuristics
   - Called by: `playwright_universal.py` for selector resolution
   - Status: ✅ CRITICAL - Keep

5. **element_parser.py** - `ElementParser`
   - Usage: Parse HTML elements heuristically (no LLM)
   - Called by: `site_intelligence.py` and `playwright_universal.py`
   - Status: ✅ CRITICAL - Keep

### Support Tools (Used Internally)
6. **base.py** - `BaseTool`, `ToolResult`
   - Usage: Base classes for all tools
   - Status: ✅ CRITICAL - Keep

7. **scraper.py** - `ScraperTool`
   - Usage: Web scraping
   - Called by: `validator.py`
   - Status: ✅ Keep (used by validator)

8. **__init__.py**
   - Usage: Package initialization
   - Status: ✅ Keep

---

## ❌ UNUSED TOOLS (11)

### Imported Only in agent_logic.py (Old File)
These tools are imported in `agent_logic.py` but **NEVER used** in the actual multi-agent system:

9. **analysis_tools.py** (327 lines)
   - Tools: `AnalyzeSentimentTool`, `SummarizeContentTool`, `CompareDataTool`, `ValidateDataTool`
   - Imported by: `agent_logic.py` only
   - Status: ❌ UNUSED - Candidate for removal

10. **calculator.py** (66 lines)
    - Tool: `CalculatorTool`
    - Imported by: `agent_logic.py`, `validator.py`
    - Registered in tool_registry.json
    - Status: ⚠️ REGISTERED BUT NEVER SELECTED - Remove or fix

11. **extractor.py** (?) 
    - Tool: `ExtractorTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Candidate for removal

12. **list_tools.py** (?)
    - Tool: `ListToolsTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Candidate for removal

13. **chunk_reader.py** (?)
    - Tool: `GetNextChunkTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Candidate for removal

14. **extract_structured.py** (?)
    - Tool: `ExtractStructuredTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Candidate for removal

15. **extract_advanced.py** (?)
    - Tools: `ExtractTableTool`, `ExtractLinksTool`, `ExtractImagesTool`, `ExtractTextBlocksTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Candidate for removal

16. **browse_advanced.py** (?)
    - Tools: `BrowseAndWaitTool`, `BrowseWithScrollTool`, `BrowseWithClickTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Replaced by playwright_universal

17. **browse_forms.py** (?)
    - Tools: `BrowseWithFormTool`, `BrowseWithAuthTool`, `BrowseMultiPageTool`
    - Imported by: `agent_logic.py` only
    - Status: ❌ UNUSED - Replaced by playwright_universal

### Never Imported Anywhere
These files are **completely unused**:

18. **events.py**
    - Status: ❌ COMPLETELY UNUSED - Safe to delete

19. **excel_export.py**
    - Status: ❌ COMPLETELY UNUSED - Safe to delete

20. **places.py**
    - Status: ❌ COMPLETELY UNUSED - Safe to delete

---

## 📊 Usage Statistics

- **Total Tools:** 20 files
- **Actively Used:** 8 (40%)
- **Unused:** 12 (60%)
- **Safely Deletable:** 3 (events, excel_export, places)
- **Imported but Unused:** 9 (analysis_tools, calculator, extractor, etc.)

---

## 🎯 RECOMMENDATIONS

### Immediate Actions (Priority 1)
1. **Delete completely unused files:**
   ```bash
   rm src/tools/events.py
   rm src/tools/excel_export.py
   rm src/tools/places.py
   ```

2. **Archive unused but imported tools:**
   ```bash
   mkdir -p src/tools/_archived
   mv src/tools/analysis_tools.py src/tools/_archived/
   mv src/tools/extractor.py src/tools/_archived/
   mv src/tools/list_tools.py src/tools/_archived/
   mv src/tools/chunk_reader.py src/tools/_archived/
   mv src/tools/extract_structured.py src/tools/_archived/
   mv src/tools/extract_advanced.py src/tools/_archived/
   mv src/tools/browse_advanced.py src/tools/_archived/
   mv src/tools/browse_forms.py src/tools/_archived/
   ```

3. **Update agent_logic.py:**
   - Remove imports for archived tools
   - Or mark agent_logic.py itself as deprecated if it's old

### Special Case: calculator.py
- **Status:** Registered in tool_registry.json but never selected by LLM
- **Options:**
  1. Keep and add to LLM tool selection examples
  2. Archive if mathematical operations aren't needed
- **Recommendation:** Archive for now, can restore if needed

### Future Cleanup (Priority 2)
4. **Clean up tool_registry.json:**
   - Remove entries for deleted/archived tools
   - Keep only: google_search, playwright_execute, chart_extractor

5. **Update documentation:**
   - Remove references to archived tools
   - Update README with current tool list

---

## 🔄 SYSTEM AFTER CLEANUP

**Active Tools (8):**
1. search.py (google_search)
2. playwright_universal.py (browser automation)
3. chart_extractor.py (data extraction)
4. site_intelligence.py (learning)
5. element_parser.py (parsing)
6. scraper.py (web scraping)
7. base.py (base classes)
8. __init__.py (package init)

**Result:**
- Cleaner codebase
- Easier maintenance
- Less confusion
- Faster imports
- Reduced complexity

---

## ⚠️ IMPORTANT NOTE

Before deleting any files, ensure:
1. Run tests if available
2. Check for any dynamic imports (`importlib`, `__import__`)
3. Search for string references to tool names
4. Backup files before deletion
5. Update requirements.txt if tools had specific dependencies
