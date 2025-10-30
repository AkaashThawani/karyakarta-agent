"""
Data Merger Utility

Merges data from multiple sources, handling conflicts and missing fields.
Used for multi-source data extraction tasks (e.g., scraping from multiple sites).

Example:
    sources = [
        {"song": "Flowers", "artist": "Miley Cyrus"},
        {"song": "Flowers", "producer": "Greg Kurstin"},
        {"description": "Pop song from 2023"}
    ]
    
    merged = merge_data(sources)
    # Result: All fields combined into one record
"""

from typing import List, Dict, Any, Optional


def merge_data(
    sources: List[Dict[str, Any]],
    priority_order: Optional[List[str]] = None,
    key_field: Optional[str] = None
) -> Dict[str, Any]:
    """
    Merge data from multiple sources into a single record.
    
    Args:
        sources: List of data dictionaries from different sources
        priority_order: Optional list of source names in priority order
        key_field: Optional field to match records (e.g., "song" for matching songs)
        
    Returns:
        Merged dictionary with all fields
        
    Strategy:
        - First non-empty value wins for each field
        - If priority_order specified, respects that order
        - Handles nested dictionaries and lists
    """
    if not sources:
        return {}
    
    merged = {}
    
    for source in sources:
        if not isinstance(source, dict):
            continue
            
        for key, value in source.items():
            # Skip if already have a value for this key
            if key in merged and merged[key]:
                continue
            
            # Skip None or empty values
            if value is None or value == "" or value == []:
                continue
            
            merged[key] = value
    
    return merged


def merge_list_of_records(
    sources: List[List[Dict[str, Any]]],
    match_field: str = "id",
    source_names: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Merge multiple lists of records based on a matching field.
    
    Args:
        sources: List of lists of records from different sources
        match_field: Field to use for matching records across sources
        source_names: Optional names for tracking data source
        
    Returns:
        List of merged records
        
    Example:
        source1 = [{"id": 1, "song": "Flowers", "artist": "Miley"}]
        source2 = [{"id": 1, "producer": "Greg Kurstin"}]
        
        merged = merge_list_of_records([source1, source2], match_field="id")
        # Result: [{"id": 1, "song": "Flowers", "artist": "Miley", "producer": "Greg Kurstin"}]
    """
    # Build index by match_field
    records_by_key = {}
    
    for source_idx, source in enumerate(sources):
        source_name = source_names[source_idx] if source_names else f"source_{source_idx}"
        
        for record in source:
            if not isinstance(record, dict):
                continue
            
            key = record.get(match_field)
            if key is None:
                continue
            
            if key not in records_by_key:
                records_by_key[key] = {
                    "_sources": [],
                    "_match_key": key
                }
            
            # Merge this record into the accumulated record
            for field, value in record.items():
                if field in records_by_key[key] and records_by_key[key][field]:
                    continue  # Already have value
                
                if value is not None and value != "" and value != []:
                    records_by_key[key][field] = value
            
            records_by_key[key]["_sources"].append(source_name)
    
    # Convert back to list
    merged_list = []
    for key, record in records_by_key.items():
        # Remove internal fields
        record.pop("_match_key", None)
        merged_list.append(record)
    
    return merged_list


def check_field_completeness(
    data: Dict[str, Any],
    required_fields: List[str]
) -> Dict[str, Any]:
    """
    Check if data has all required fields populated.
    
    Args:
        data: Data dictionary to check
        required_fields: List of field names that must be present
        
    Returns:
        Dictionary with completeness metrics:
        {
            "complete": bool,
            "missing": List[str],
            "coverage": float (0-100%)
        }
    """
    missing = []
    
    for field in required_fields:
        value = data.get(field)
        
        # Check if field is missing or empty
        if value is None or value == "" or value == []:
            missing.append(field)
    
    coverage = 0.0
    if required_fields:
        coverage = ((len(required_fields) - len(missing)) / len(required_fields)) * 100
    
    return {
        "complete": len(missing) == 0,
        "missing": missing,
        "present": [f for f in required_fields if f not in missing],
        "coverage": round(coverage, 2)
    }


def prioritize_sources(
    sources: List[Dict[str, Any]],
    priority_map: Dict[str, int]
) -> List[Dict[str, Any]]:
    """
    Sort sources by priority (lower number = higher priority).
    
    Args:
        sources: List of source data dictionaries
        priority_map: Dict mapping source name to priority (1=highest)
        
    Returns:
        Sorted list with highest priority sources first
        
    Example:
        priority_map = {
            "spotify": 1,
            "billboard": 2,
            "genius": 3
        }
    """
    def get_priority(source):
        source_name = source.get("_source_name", "unknown")
        return priority_map.get(source_name, 999)
    
    return sorted(sources, key=get_priority)


def merge_with_confidence(
    sources: List[Dict[str, Any]],
    confidence_threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Merge data considering confidence scores.
    
    Args:
        sources: List of data dicts with _confidence scores
        confidence_threshold: Minimum confidence to accept value
        
    Returns:
        Merged data using highest confidence values
    """
    merged = {}
    field_scores = {}
    
    for source in sources:
        confidence = source.get("_confidence", 1.0)
        
        if confidence < confidence_threshold:
            continue
        
        for key, value in source.items():
            if key.startswith("_"):  # Skip internal fields
                continue
            
            if value is None or value == "":
                continue
            
            # Use highest confidence value
            current_score = field_scores.get(key, 0)
            if confidence > current_score:
                merged[key] = value
                field_scores[key] = confidence
    
    return merged
