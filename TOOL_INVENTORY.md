# Tool Inventory - Which Tools to Keep?

## Current Status
- **23 tool files** in src/tools/
- **7 tools** in registry (actually used)
- **16 tools** not in registry (potentially unused)

---

## ✅ Tools in Registry (Currently Used - 7)

### 1. playwright_execute (playwright_universal.py)
**Status:** ✅ ESSENTIAL
**Use:** Universal browser automation - navigate, click, fill, extract
**Registry:** Yes
**Keep:** YES - Core functionality

### 2. google_search (search.py)
**Status:** ✅ ESSENTIAL
**Use:** Google search for finding information
**Registry:** Yes
**Keep:** YES - Core functionality

### 3. chart_extractor (chart_extractor_tool.py)
**Status:** ✅ ESSENTIAL
**Use:** Extract structured data (tables, lists) from webpages
**Registry:** Yes
**Keep:** YES - Core functionality

### 4. api_call (api_call.py)
**Status:** ✅ ESSENTIAL
**Use:** Make HTTP API requests (GET/POST/PUT/DELETE)
**Registry:** Yes
**Keep:** YES - Core functionality

### 5. calculator (calculator.py)
**Status:** ✅ ESSENTIAL
**Use:** Perform mathematical calculations
**Registry:** Yes
**Keep:** YES - Core functionality

### 6. excel_export (excel_export.py - ExcelExportTool)
**Status:** ✅ USEFUL
**Use:** Export data to Excel files
**Registry:** Yes
**Keep:** YES - Data export feature

### 7. csv_export (excel_export.py - CSVExportTool)
**Status:** ✅ USEFUL
**Use:** Export data to CSV files
**Registry:** Yes
**Keep:** YES - Data export feature

---

## ❓ Tools NOT in Registry (Potentially Unused - 16+)

### Support/Infrastructure Files (Keep)

#### base.py
**Status:** ✅ ESSENTIAL
**Use:** Abstract BaseTool class - foundation for all tools
**Keep:** YES - Required by all other tools

#### chart_extractor.py
**Status:** ✅ ESSENTIAL
**Use:** Core extraction logic used by chart_extractor_tool.py
**Keep:** YES - Backend for chart_extractor

#### element_parser.py
**Status:** ✅ ESSENTIAL
**Use:** HTML parsing utilities used by extractors
**Keep:** YES - Used by extraction tools

#### universal_extractor.py
**Status:** ✅ ESSENTIAL
**Use:** Universal extraction engine with DFS traversal
**Keep:** YES - Core extraction logic

### Analysis Tools (analysis_tools.py)

#### 1. analyze_sentiment
**Status:** ⚠️ NOT REGISTERED
**Use:** LLM-based sentiment analysis
**Used:** Unknown
**Keep?** DISCUSS - Could be useful for review analysis

#### 2. summarize_content
**Status:** ⚠️ NOT REGISTERED
**Use:** LLM-based content summarization
**Used:** Unknown
**Keep?** DISCUSS - Could be useful for long content

#### 3. compare_data
**Status:** ⚠️ NOT REGISTERED
**Use:** Compare two datasets
**Used:** Unknown
**Keep?** DISCUSS - Could be useful for comparisons

#### 4. validate_data
**Status:** ⚠️ NOT REGISTERED
**Use:** Data quality validation
**Used:** Unknown
**Keep?** DISCUSS - Could be useful for validation

### Browse Tools (browse_advanced.py)

#### 5. browse_and_wait
**Status:** ⚠️ NOT REGISTERED
**Use:** Browse with explicit wait
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

#### 6. browse_with_scroll
**Status:** ⚠️ NOT REGISTERED
**Use:** Browse with infinite scroll
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

#### 7. browse_with_click
**Status:** ⚠️ NOT REGISTERED
**Use:** Browse with element clicking
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

### Browse Forms (browse_forms.py)

#### 8. browse_with_form
**Status:** ⚠️ NOT REGISTERED
**Use:** Fill and submit forms
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

#### 9. browse_with_auth
**Status:** ⚠️ NOT REGISTERED
**Use:** Authentication handling
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

#### 10. browse_multi_page
**Status:** ⚠️ NOT REGISTERED
**Use:** Pagination handling
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

### Extraction Tools (extract_advanced.py)

#### 11. extract_table
**Status:** ⚠️ NOT REGISTERED
**Use:** Extract HTML tables
**Used:** Unknown
**Keep?** DISCUSS - Covered by chart_extractor?

#### 12. extract_links
**Status:** ⚠️ NOT REGISTERED
**Use:** Extract links from pages
**Used:** Unknown
**Keep?** DISCUSS - Covered by universal_extractor?

#### 13. extract_images
**Status:** ⚠️ NOT REGISTERED
**Use:** Extract images from pages
**Used:** Unknown
**Keep?** DISCUSS - Could be useful for image extraction

#### 14. extract_text_blocks
**Status:** ⚠️ NOT REGISTERED
**Use:** Extract text blocks
**Used:** Unknown
**Keep?** DISCUSS - Covered by universal_extractor?

### Other Tools

#### 15. extract_structured (extract_structured.py)
**Status:** ⚠️ NOT REGISTERED
**Use:** Structured data extraction
**Used:** Unknown
**Keep?** DISCUSS - Redundant with chart_extractor?

#### 16. scraper (scraper.py)
**Status:** ⚠️ NOT REGISTERED
**Use:** Basic web scraping
**Used:** Unknown
**Keep?** DISCUSS - Covered by playwright_execute?

#### 17. get_next_chunk (chunk_reader.py)
**Status:** ⚠️ NOT REGISTERED
**Use:** Chunk-based pagination
**Used:** Unknown
**Keep?** DISCUSS - Specialized pagination

#### 18. list_tools (list_tools.py)
**Status:** ⚠️ NOT REGISTERED
**Use:** List available tools
**Used:** Unknown
**Keep?** DISCUSS - Meta tool

#### 19. site_intelligence (site_intelligence.py)
**Status:** ⚠️ NOT REGISTERED + DISABLED IN CODE
**Use:** Site-specific intelligence
**Used:** Disabled
**Keep?** DELETE - Already disabled in code

#### 20. fallback_manager (fallback_manager.py)
**Status:** ⚠️ NOT REGISTERED
**Use:** Fallback extraction logic
**Used:** Unknown
**Keep?** DISCUSS - Infrastructure

#### 21. learning_manager (learning_manager.py)
**Status:** ⚠️ NOT REGISTERED
**Use:** Learning/adaptation logic
**Used:** Unknown
**Keep?** DISCUSS - Infrastructure

---

## 📊 Recommendation Summary

### Definitely Keep (11 files)
- base.py, api_call.py, calculator.py
- chart_extractor.py, chart_extractor_tool.py
- element_parser.py, excel_export.py
- playwright_universal.py, search.py
- universal_extractor.py, __init__.py

### Probably Delete (Covered by existing tools)
- browse_advanced.py (3 tools - covered by playwright_execute)
- browse_forms.py (3 tools - covered by playwright_execute)
- scraper.py (covered by playwright_execute)
- extractor.py (replaced by universal_extractor)
- extract_structured.py (redundant with chart_extractor)

### Maybe Keep (Specialized functionality)
- analysis_tools.py (LLM analysis - could be useful)
- extract_advanced.py (image extraction might be unique)
- chunk_reader.py (specialized pagination)
- list_tools.py (meta tool for introspection)

### Definitely Delete (Already disabled)
- site_intelligence.py (disabled in code)
- fallback_manager.py (unused infrastructure)
- learning_manager.py (unused infrastructure)

---

## 🤔 Discussion Needed

Which tools should we keep? Let's discuss each category before deleting.
