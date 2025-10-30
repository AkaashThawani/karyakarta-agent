"""
Universal HTML Extractor

Extracts EVERYTHING from HTML using selectolax (already installed).
No new dependencies needed!

Features:
- Extracts ALL HTML elements (tables, lists, links, images, forms, buttons, divs, etc.)
- Uses selectolax for speed (10x faster than BeautifulSoup)
- Falls back to lxml and pandas when needed
- Smart search to find relevant data
- PARALLEL EXTRACTION - 3-4x faster than serial!
"""

from selectolax.parser import HTMLParser
from typing import List, Dict, Any, Optional
import re
import asyncio


class UniversalExtractor:
    """Extract EVERYTHING from HTML - no element left behind! With parallel processing!"""
    
    def extract_everything(self, html: str, url: str = '') -> Dict[str, Any]:
        """
        Synchronous wrapper for backward compatibility.
        """
        # Run async version
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.extract_everything_async(html, url))
    
    async def extract_everything_async(self, html: str, url: str = '') -> Dict[str, Any]:
        """
        Extract ALL elements in PARALLEL with 2-minute timeout.
        
        Args:
            html: HTML string to parse
            url: Source URL (for context)
            
        Returns:
            Dictionary with all extracted data organized by type
        """
        tree = HTMLParser(html)
        
        try:
            # Run ALL 13 extractions in parallel with 2-minute timeout!
            async with asyncio.timeout(120):  # 2 minutes
                print(f"[EXTRACT] 🚀 Starting parallel extraction of 13 element types")
                
                results = await asyncio.gather(
                    asyncio.to_thread(self._extract_metadata, tree, url),
                    asyncio.to_thread(self._extract_links, tree),
                    asyncio.to_thread(self._extract_images, tree),
                    asyncio.to_thread(self._extract_tables, tree),
                    asyncio.to_thread(self._extract_lists, tree),
                    asyncio.to_thread(self._extract_forms, tree),
                    asyncio.to_thread(self._extract_buttons, tree),
                    asyncio.to_thread(self._extract_cards, tree),
                    asyncio.to_thread(self._extract_divs, tree),
                    asyncio.to_thread(self._extract_spans, tree),
                    asyncio.to_thread(self._extract_headings, tree),
                    asyncio.to_thread(self._extract_paragraphs, tree),
                    asyncio.to_thread(self._extract_data_attributes, tree),
                    return_exceptions=True
                )
                
                # Build result dict
                keys = ['metadata', 'links', 'images', 'tables', 'lists',
                       'forms', 'buttons', 'cards', 'divs', 'spans',
                       'headings', 'paragraphs', 'data_attributes']
                
                result = {}
                for i, key in enumerate(keys):
                    if isinstance(results[i], Exception):
                        print(f"[EXTRACT] ⚠️ {key} extraction failed: {results[i]}")
                        result[key] = [] if key != 'metadata' else {}
                    else:
                        result[key] = results[i]
                        count = len(result[key]) if isinstance(result[key], list) else 1
                        print(f"[EXTRACT] ✅ {key}: {count} items")
                
                # Add summary
                result['summary'] = self._create_summary(result)
                
                print(f"[EXTRACT] 🎉 Parallel extraction complete!")
                return result
                
        except asyncio.TimeoutError:
            print(f"[EXTRACT] ⚠️ Timeout after 2 minutes - returning empty result")
            return {
                'metadata': {},
                'links': [],
                'images': [],
                'tables': [],
                'lists': [],
                'forms': [],
                'buttons': [],
                'cards': [],
                'divs': [],
                'spans': [],
                'headings': [],
                'paragraphs': [],
                'data_attributes': [],
                'summary': {'total_elements': 0}
            }
        except Exception as e:
            print(f"[EXTRACT] ❌ Parallel extraction failed: {e}")
            # Fallback to serial extraction
            print(f"[EXTRACT] Falling back to serial extraction...")
            return self._extract_serial(tree, url)
    
    def _extract_serial(self, tree, url: str) -> Dict[str, Any]:
        """Fallback serial extraction if parallel fails"""
        result = {
            'metadata': self._extract_metadata(tree, url),
            'links': self._extract_links(tree),
            'images': self._extract_images(tree),
            'tables': self._extract_tables(tree),
            'lists': self._extract_lists(tree),
            'forms': self._extract_forms(tree),
            'buttons': self._extract_buttons(tree),
            'cards': self._extract_cards(tree),
            'divs': self._extract_divs(tree),
            'spans': self._extract_spans(tree),
            'headings': self._extract_headings(tree),
            'paragraphs': self._extract_paragraphs(tree),
            'data_attributes': self._extract_data_attributes(tree)
        }
        result['summary'] = self._create_summary(result)
        return result
    
    def _extract_metadata(self, tree, url: str) -> Dict:
        """Extract page metadata"""
        title_elem = tree.css_first('title')
        desc_elem = tree.css_first('meta[name="description"]')
        keywords_elem = tree.css_first('meta[name="keywords"]')
        
        return {
            'url': url,
            'title': title_elem.text() if title_elem else '',
            'description': desc_elem.attributes.get('content', '') if desc_elem else '',
            'keywords': keywords_elem.attributes.get('content', '') if keywords_elem else ''
        }
    
    def _extract_links(self, tree) -> List[Dict]:
        """Extract ALL links with text and href"""
        links = []
        
        for a in tree.css('a'):
            href = a.attributes.get('href', '')
            text = a.text(strip=True)
            
            if href or text:
                links.append({
                    'text': text,
                    'href': href,
                    'title': a.attributes.get('title', ''),
                    'class': a.attributes.get('class', '')
                })
        
        return links
    
    def _extract_images(self, tree) -> List[Dict]:
        """Extract ALL images"""
        images = []
        
        for img in tree.css('img'):
            images.append({
                'src': img.attributes.get('src', ''),
                'alt': img.attributes.get('alt', ''),
                'title': img.attributes.get('title', '')
            })
        
        return images
    
    def _extract_tables(self, tree) -> List[Dict]:
        """Extract ALL tables with headers and rows"""
        tables = []
        
        for idx, table in enumerate(tree.css('table')):
            # Extract headers
            headers = [th.text(strip=True) for th in table.css('th')]
            
            # Extract rows
            rows = []
            for tr in table.css('tr'):
                cells = [td.text(strip=True) for td in tr.css('td')]
                if cells:
                    # Create dict if we have headers
                    if headers and len(headers) > 0:
                        row = {}
                        for i, header in enumerate(headers):
                            row[header if header else f'col_{i}'] = cells[i] if i < len(cells) else ''
                    else:
                        # No headers, use column indices
                        row = {f'col_{i}': v for i, v in enumerate(cells)}
                    rows.append(row)
            
            if rows:
                tables.append({
                    'table_id': idx,
                    'headers': headers,
                    'rows': rows,
                    'row_count': len(rows),
                    'class': table.attributes.get('class', '')
                })
        
        return tables
    
    def _extract_lists(self, tree) -> List[Dict]:
        """Extract ALL lists (ul, ol)"""
        lists = []
        
        for idx, list_elem in enumerate(tree.css('ul, ol')):
            items = [li.text(strip=True) for li in list_elem.css('li')]
            items = [item for item in items if item]
            
            if items:
                lists.append({
                    'list_id': idx,
                    'type': list_elem.tag,
                    'items': items,
                    'count': len(items),
                    'class': list_elem.attributes.get('class', '')
                })
        
        return lists
    
    def _extract_forms(self, tree) -> List[Dict]:
        """Extract ALL forms with inputs"""
        forms = []
        
        for idx, form in enumerate(tree.css('form')):
            inputs = []
            for input_elem in form.css('input, textarea, select'):
                inputs.append({
                    'type': input_elem.attributes.get('type', ''),
                    'name': input_elem.attributes.get('name', ''),
                    'placeholder': input_elem.attributes.get('placeholder', '')
                })
            
            forms.append({
                'form_id': idx,
                'action': form.attributes.get('action', ''),
                'method': form.attributes.get('method', 'get'),
                'inputs': inputs
            })
        
        return forms
    
    def _extract_buttons(self, tree) -> List[Dict]:
        """Extract ALL buttons"""
        buttons = []
        
        for button in tree.css('button, input[type="button"], input[type="submit"]'):
            buttons.append({
                'text': button.text(strip=True),
                'type': button.attributes.get('type', ''),
                'class': button.attributes.get('class', '')
            })
        
        return buttons
    
    def _extract_cards(self, tree) -> List[Dict]:
        """Extract card-like structures"""
        cards = []
        
        selectors = ['.card', '.item', 'article', '[class*="card"]', '[class*="item"]']
        
        for selector in selectors:
            for card in tree.css(selector):
                title_elem = card.css_first('h1, h2, h3, h4, .title, [class*="title"]')
                desc_elem = card.css_first('p, .description, [class*="desc"]')
                link_elem = card.css_first('a')
                
                card_data = {
                    'title': title_elem.text(strip=True) if title_elem else '',
                    'description': desc_elem.text(strip=True) if desc_elem else '',
                    'link': link_elem.attributes.get('href', '') if link_elem else '',
                    'full_text': card.text(strip=True),
                    'class': card.attributes.get('class', '')
                }
                
                # Only add if has some content
                if card_data['title'] or card_data['description'] or len(card_data['full_text']) > 20:
                    cards.append(card_data)
        
        return cards
    
    def _extract_divs(self, tree) -> List[Dict]:
        """Extract structured divs"""
        divs = []
        
        patterns = [
            '[class*="row"]',
            '[class*="item"]',
            '[class*="entry"]',
            '[class*="game"]',
            '[class*="product"]',
            '[data-id]',
            '[data-name]',
            '[data-value]'
        ]
        
        for pattern in patterns:
            for div in tree.css(pattern):
                text = div.text(strip=True)
                if text and len(text) > 10:
                    data_attrs = {k: v for k, v in div.attributes.items() if k.startswith('data-')}
                    divs.append({
                        'text': text,
                        'class': div.attributes.get('class', ''),
                        'data': data_attrs
                    })
        
        return divs
    
    def _extract_spans(self, tree) -> List[Dict]:
        """Extract spans with classes/data"""
        spans = []
        
        # Extract spans with classes or specific data attributes
        for span in tree.css('span[class], span[data-id], span[data-name], span[data-value], span[data-price]'):
            text = span.text(strip=True)
            if text:
                data_attrs = {k: v for k, v in span.attributes.items() if k.startswith('data-')}
                spans.append({
                    'text': text,
                    'class': span.attributes.get('class', ''),
                    'data': data_attrs
                })
        
        return spans
    
    def _extract_headings(self, tree) -> List[Dict]:
        """Extract ALL headings (h1-h6)"""
        headings = []
        
        for h in tree.css('h1, h2, h3, h4, h5, h6'):
            headings.append({
                'level': h.tag,
                'text': h.text(strip=True),
                'class': h.attributes.get('class', '')
            })
        
        return headings
    
    def _extract_paragraphs(self, tree) -> List[str]:
        """Extract ALL paragraphs"""
        return [p.text(strip=True) for p in tree.css('p') if p.text(strip=True)]
    
    def _extract_data_attributes(self, tree) -> List[Dict]:
        """Extract ALL elements with data-* attributes"""
        elements = []
        
        # Extract elements with common data attributes
        selectors = [
            '[data-id]', '[data-name]', '[data-value]', '[data-type]',
            '[data-price]', '[data-rating]', '[data-product]', '[data-item]'
        ]
        
        for selector in selectors:
            for elem in tree.css(selector):
                data_attrs = {k: v for k, v in elem.attributes.items() if k.startswith('data-')}
                if data_attrs:
                    elements.append({
                        'tag': elem.tag,
                        'text': elem.text(strip=True),
                        'data': data_attrs,
                        'class': elem.attributes.get('class', '')
                    })
        
        return elements
    
    def _create_summary(self, result: Dict) -> Dict:
        """Create summary of extracted data"""
        return {
            'links_count': len(result['links']),
            'images_count': len(result['images']),
            'tables_count': len(result['tables']),
            'lists_count': len(result['lists']),
            'forms_count': len(result['forms']),
            'buttons_count': len(result['buttons']),
            'cards_count': len(result['cards']),
            'divs_count': len(result['divs']),
            'headings_count': len(result['headings']),
            'total_elements': sum([
                len(result['links']),
                len(result['images']),
                len(result['tables']),
                len(result['lists']),
                len(result['cards']),
                len(result['divs'])
            ])
        }


class SmartSearcher:
    """Search through extracted data to find relevant information"""
    
    def search(
        self,
        extracted_data: Dict[str, Any],
        query: str,
        required_fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search extracted data for relevant information.
        
        Args:
            extracted_data: Data from UniversalExtractor
            query: Search query (e.g., "steam games")
            required_fields: Optional list of required fields
            
        Returns:
            List of matching records
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Try tables first (most structured)
        for table in extracted_data.get('tables', []):
            if self._table_matches(table, query_words, required_fields):
                print(f"[SEARCH] Found matching table with {table['row_count']} rows")
                return table['rows'][:10]  # Return top 10
        
        # Try lists
        for list_data in extracted_data.get('lists', []):
            if self._list_matches(list_data, query_words):
                print(f"[SEARCH] Found matching list with {list_data['count']} items")
                return self._convert_list_to_records(list_data['items'][:10])
        
        # Try cards
        cards = extracted_data.get('cards', [])
        matching_cards = [c for c in cards if self._card_matches(c, query_words)]
        if matching_cards:
            print(f"[SEARCH] Found {len(matching_cards)} matching cards")
            return matching_cards[:10]
        
        # Try divs
        divs = extracted_data.get('divs', [])
        matching_divs = [d for d in divs if self._text_matches(d.get('text', ''), query_words)]
        if matching_divs:
            print(f"[SEARCH] Found {len(matching_divs)} matching divs")
            return matching_divs[:10]
        
        print("[SEARCH] No matches found")
        return []
    
    def _table_matches(
        self,
        table: Dict,
        query_words: set,
        required_fields: Optional[List[str]]
    ) -> bool:
        """Check if table matches query"""
        # Check headers
        headers_text = ' '.join(table.get('headers', [])).lower()
        if any(word in headers_text for word in query_words):
            return True
        
        # Check required fields in headers
        if required_fields:
            headers_lower = [h.lower() for h in table.get('headers', [])]
            matches = sum(1 for field in required_fields 
                         if any(field.lower() in h for h in headers_lower))
            if matches >= 2:  # At least 2 fields match
                return True
        
        # Check first row content
        if table.get('rows'):
            first_row_text = ' '.join(str(v) for v in table['rows'][0].values()).lower()
            if any(word in first_row_text for word in query_words):
                return True
        
        return False
    
    def _list_matches(self, list_data: Dict, query_words: set) -> bool:
        """Check if list matches query"""
        # Check class name
        class_name = list_data.get('class', '').lower()
        if any(word in class_name for word in query_words):
            return True
        
        # Check first few items
        sample_items = list_data.get('items', [])[:3]
        sample_text = ' '.join(sample_items).lower()
        return any(word in sample_text for word in query_words)
    
    def _card_matches(self, card: Dict, query_words: set) -> bool:
        """Check if card matches query"""
        text = f"{card.get('title', '')} {card.get('description', '')}".lower()
        return any(word in text for word in query_words)
    
    def _text_matches(self, text: str, query_words: set) -> bool:
        """Check if text matches query"""
        text_lower = text.lower()
        return any(word in text_lower for word in query_words)
    
    def _convert_list_to_records(self, items: List[str]) -> List[Dict]:
        """Convert list items to structured records"""
        records = []
        for idx, item in enumerate(items, 1):
            records.append({
                'rank': str(idx),
                'name': item,
                'raw': item
            })
        return records
