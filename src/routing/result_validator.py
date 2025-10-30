"""
Result Validator - Validates extraction results and suggests next steps

This module checks if extracted data is complete and suggests actions
to gather missing data through click-throughs, form fills, etc.
"""

from typing import List, Dict, Any, Optional
import re


class ResultValidator:
    """Validate extraction results and suggest next steps for missing data"""
    
    def validate(
        self,
        results: List[Dict[str, Any]],
        required_fields: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate extraction results against required fields.
        
        Args:
            results: List of extracted records
            required_fields: List of required field names
            context: Optional context (url, page_type, etc.)
            
        Returns:
            Dictionary with validation results and suggestions
        """
        if not results:
            return {
                'valid': False,
                'complete': False,
                'missing_fields': required_fields,
                'coverage': 0.0,
                'confidence': 0.0,
                'suggested_actions': [
                    {'action': 're_extract', 'reason': 'No results found'}
                ]
            }
        
        # Check completeness
        present_fields = set(results[0].keys())
        required_set = set(required_fields)
        missing_fields = list(required_set - present_fields)
        
        coverage = len(present_fields & required_set) / len(required_set) if required_set else 1.0
        
        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(results, required_fields)
        
        # Generate suggestions if incomplete
        suggested_actions = []
        if missing_fields:
            suggested_actions = self.suggest_next_steps(missing_fields, context or {})
        
        return {
            'valid': coverage > 0.0,
            'complete': len(missing_fields) == 0,
            'missing_fields': missing_fields,
            'present_fields': list(present_fields),
            'coverage': coverage,
            'confidence': confidence,
            'record_count': len(results),
            'suggested_actions': suggested_actions
        }
    
    def suggest_next_steps(
        self,
        missing_fields: List[str],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Suggest next steps to gather missing data.
        
        Args:
            missing_fields: List of missing field names
            context: Context information (url, page_type, etc.)
            
        Returns:
            List of suggested actions
        """
        suggestions = []
        url = context.get('url', '')
        
        for field in missing_fields:
            field_lower = field.lower()
            
            # Price field - usually on product detail pages
            if any(keyword in field_lower for keyword in ['price', 'cost', 'amount']):
                suggestions.append({
                    'action': 'click_through',
                    'target': 'product_link',
                    'extract_from': 'detail_page',
                    'field': field,
                    'reason': 'Price typically found on product detail pages',
                    'priority': 'high'
                })
            
            # Rating field - may need to look for star icons or review sections
            elif any(keyword in field_lower for keyword in ['rating', 'score', 'stars']):
                suggestions.append({
                    'action': 'extract_with_pattern',
                    'pattern': 'star_rating',
                    'field': field,
                    'reason': 'Look for star ratings or numeric scores',
                    'priority': 'medium'
                })
            
            # Contact info - may be on separate contact page
            elif any(keyword in field_lower for keyword in ['phone', 'email', 'contact']):
                suggestions.append({
                    'action': 'navigate',
                    'target': 'contact_page',
                    'extract_from': 'contact_page',
                    'field': field,
                    'reason': 'Contact information often on separate page',
                    'priority': 'medium'
                })
            
            # Website/URL - look for links
            elif any(keyword in field_lower for keyword in ['website', 'url', 'link']):
                suggestions.append({
                    'action': 'extract_links',
                    'filter': 'external_links',
                    'field': field,
                    'reason': 'Extract website URLs from links',
                    'priority': 'low'
                })
            
            # Description - may need full product page
            elif any(keyword in field_lower for keyword in ['description', 'details', 'info']):
                suggestions.append({
                    'action': 'click_through',
                    'target': 'detail_link',
                    'extract_from': 'detail_page',
                    'field': field,
                    'reason': 'Detailed descriptions on product pages',
                    'priority': 'medium'
                })
            
            # Publisher/Author/Company - may be in metadata
            elif any(keyword in field_lower for keyword in ['publisher', 'author', 'company', 'brand']):
                suggestions.append({
                    'action': 'extract_metadata',
                    'locations': ['detail_page', 'about_section'],
                    'field': field,
                    'reason': 'Publisher info often in product metadata',
                    'priority': 'medium'
                })
            
            # Generic fallback
            else:
                suggestions.append({
                    'action': 'click_through',
                    'target': 'detail_link',
                    'extract_from': 'detail_page',
                    'field': field,
                    'reason': f'Field {field} likely on detail page',
                    'priority': 'low'
                })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        suggestions.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))
        
        return suggestions
    
    def _calculate_confidence(
        self,
        results: List[Dict[str, Any]],
        required_fields: List[str]
    ) -> float:
        """
        Calculate confidence score for extraction results.
        
        Factors:
        - Data completeness (all required fields present)
        - Data quality (non-empty values)
        - Data consistency (similar structure across records)
        
        Returns:
            Confidence score (0.0-1.0)
        """
        if not results:
            return 0.0
        
        scores = []
        
        # 1. Completeness score
        present_fields = set(results[0].keys())
        required_set = set(required_fields)
        completeness = len(present_fields & required_set) / len(required_set) if required_set else 1.0
        scores.append(completeness)
        
        # 2. Data quality score (non-empty values)
        quality_scores = []
        for result in results:
            non_empty = sum(1 for v in result.values() if v and str(v).strip())
            total = len(result)
            quality_scores.append(non_empty / total if total > 0 else 0.0)
        
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        scores.append(avg_quality)
        
        # 3. Consistency score (same fields across records)
        if len(results) > 1:
            first_fields = set(results[0].keys())
            consistency_scores = []
            for result in results[1:]:
                result_fields = set(result.keys())
                similarity = len(first_fields & result_fields) / len(first_fields | result_fields)
                consistency_scores.append(similarity)
            
            avg_consistency = sum(consistency_scores) / len(consistency_scores) if consistency_scores else 1.0
            scores.append(avg_consistency)
        else:
            scores.append(1.0)  # Single record is consistent
        
        # Calculate weighted average
        weights = [0.4, 0.4, 0.2]  # Completeness and quality more important
        confidence = sum(s * w for s, w in zip(scores, weights))
        
        return round(confidence, 2)
    
    def check_field_presence(
        self,
        results: List[Dict[str, Any]],
        field: str
    ) -> Dict[str, Any]:
        """
        Check if a specific field is present and has valid data.
        
        Returns:
            {
                'present': bool,
                'filled_count': int,
                'empty_count': int,
                'fill_rate': float
            }
        """
        if not results:
            return {
                'present': False,
                'filled_count': 0,
                'empty_count': 0,
                'fill_rate': 0.0
            }
        
        present = field in results[0]
        filled_count = 0
        empty_count = 0
        
        for result in results:
            if field in result:
                value = result[field]
                if value and str(value).strip():
                    filled_count += 1
                else:
                    empty_count += 1
            else:
                empty_count += 1
        
        total = filled_count + empty_count
        fill_rate = filled_count / total if total > 0 else 0.0
        
        return {
            'present': present,
            'filled_count': filled_count,
            'empty_count': empty_count,
            'fill_rate': round(fill_rate, 2)
        }
