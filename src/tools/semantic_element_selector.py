"""
Semantic Element Selector - Vector-based Element Matching

Uses ChromaDB for semantic search of interactive elements.
Matches task intent with element descriptions using vector similarity.
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import chromadb
from chromadb.config import Settings


class SemanticElementSelector:
    """
    Semantic element selector using vector search.

    Stores element descriptions in ChromaDB and performs semantic queries
    to find elements that match task intent without LLM calls.
    """

    def __init__(self, collection_name: str = "interactive_elements", persist_directory: str = "./element_cache"):
        """
        Initialize semantic element selector.

        Args:
            collection_name: Name of ChromaDB collection
            persist_directory: Directory to persist vector database
        """
        self.collection_name = collection_name
        # Use absolute path to avoid working directory issues
        if persist_directory.startswith("./"):
            # Convert relative path to absolute based on this file's directory
            base_dir = Path(__file__).parent.parent.parent  # karyakarta-agent directory
            self.persist_directory = base_dir / persist_directory[2:]  # Remove "./"
        else:
            self.persist_directory = Path(persist_directory)

        self.persist_directory.mkdir(exist_ok=True)

        print(f"[SemanticElementSelector] Initializing with persist_directory: {self.persist_directory.absolute()}")

        # Initialize ChromaDB client
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False)
            )
            print(f"[SemanticElementSelector] ChromaDB client initialized successfully")
        except Exception as e:
            print(f"[SemanticElementSelector] Failed to initialize ChromaDB client: {e}")
            self.client = None
            return

        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"[SemanticElementSelector] Found existing collection: {collection_name}")
        except Exception as e:
            print(f"[SemanticElementSelector] Collection '{collection_name}' does not exist (exception: {type(e).__name__}: {e}), creating it...")
            try:
                self.collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"description": "Interactive elements for semantic search"}
                )
                print(f"[SemanticElementSelector] Successfully created new collection: {collection_name}")
            except Exception as create_e:
                print(f"[SemanticElementSelector] Failed to create collection: {type(create_e).__name__}: {create_e}")
                self.collection = None

    def store_elements(self, url: str, elements: Dict[str, List[Dict[str, Any]]]) -> int:
        """
        Store extracted elements in vector database.

        Args:
            url: Source URL of elements
            elements: Categorized elements from InteractiveElementExtractor

        Returns:
            Number of elements stored
        """
        if not self.collection:
            print("[SemanticElementSelector] Collection not initialized, cannot store elements")
            return 0

        stored_count = 0

        # Extract domain for grouping
        domain = self._extract_domain(url)

        # Process each category
        for category, element_list in elements.items():
            for element in element_list:
                try:
                    # Create unique ID
                    element_id = f"{domain}_{category}_{hash(json.dumps(element, sort_keys=True))}"

                    # Get semantic description
                    description = element.get("description", "")
                    if not description:
                        continue

                    # Prepare metadata
                    metadata = {
                        "url": url,
                        "domain": domain,
                        "category": category,
                        "tag": element.get("tag", ""),
                        "selector": element.get("selector", ""),
                        "aria_label": element.get("attributes", {}).get("aria-label", ""),
                        "placeholder": element.get("attributes", {}).get("placeholder", ""),
                        "text_content": element.get("text_content", ""),
                        "inner_text": element.get("inner_text", "")
                    }

                    # Store in ChromaDB
                    self.collection.add(
                        documents=[description],
                        metadatas=[metadata],
                        ids=[element_id]
                    )

                    stored_count += 1

                except Exception as e:
                    # Skip problematic elements
                    print(f"[SemanticElementSelector] Failed to store element: {e}")
                    continue

        return stored_count

    def find_elements(self, task_intent: str, domain: Optional[str] = None,
                     category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find elements semantically similar to task intent.

        Args:
            task_intent: Description of what element is needed (e.g., "search input field")
            domain: Optional domain filter
            category: Optional category filter
            limit: Maximum results to return

        Returns:
            List of matching elements with similarity scores
        """
        if not self.collection:
            print("[SemanticElementSelector] Collection not initialized, cannot search")
            return []

        try:
            # Build where clause for filtering
            where_clause = {}
            if domain:
                where_clause["domain"] = domain
            if category:
                where_clause["category"] = category

            # Perform semantic search
            results = self.collection.query(
                query_texts=[task_intent],
                n_results=limit,
                where=where_clause if where_clause else None,
                include=["documents", "metadatas", "distances"]
            )

            # Format results
            matches = []
            if results["documents"] and results["metadatas"] and results["distances"]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )):
                    # Convert distance to similarity score (lower distance = higher similarity)
                    similarity = 1.0 / (1.0 + distance)

                    match = {
                        "element_id": results["ids"][0][i],
                        "description": doc,
                        "similarity": similarity,
                        "selector": metadata.get("selector", ""),
                        "tag": metadata.get("tag", ""),
                        "category": metadata.get("category", ""),
                        "url": metadata.get("url", ""),
                        "domain": metadata.get("domain", ""),
                        "aria_label": metadata.get("aria_label", ""),
                        "placeholder": metadata.get("placeholder", ""),
                        "text_content": metadata.get("text_content", ""),
                        "inner_text": metadata.get("inner_text", ""),
                        "metadata": metadata
                    }
                    matches.append(match)

            # Sort by similarity (highest first)
            matches.sort(key=lambda x: x["similarity"], reverse=True)

            return matches

        except Exception as e:
            print(f"[SemanticElementSelector] Search failed: {e}")
            return []

    def find_best_element(self, task_intent: str, domain: Optional[str] = None,
                         category: Optional[str] = None, min_similarity: float = 0.3) -> Optional[Dict[str, Any]]:
        """
        Find the single best matching element.

        Args:
            task_intent: Description of needed element
            domain: Optional domain filter
            category: Optional category filter
            min_similarity: Minimum similarity threshold

        Returns:
            Best matching element or None
        """
        matches = self.find_elements(task_intent, domain, category, limit=1)

        if matches and matches[0]["similarity"] >= min_similarity:
            return matches[0]

        return None

    def get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """
        Get statistics for a specific domain.

        Args:
            domain: Domain to analyze

        Returns:
            Statistics about stored elements
        """
        if not self.collection:
            return {"domain": domain, "error": "Collection not initialized"}

        try:
            # Query all elements for domain
            results = self.collection.get(
                where={"domain": domain},
                include=["metadatas"]
            )

            if not results["metadatas"]:
                return {"domain": domain, "total_elements": 0, "categories": {}}

            # Count by category
            categories = {}
            for metadata in results["metadatas"]:
                category = metadata.get("category", "unknown")
                categories[category] = categories.get(category, 0) + 1

            return {
                "domain": domain,
                "total_elements": len(results["metadatas"]),
                "categories": categories
            }

        except Exception as e:
            return {"domain": domain, "error": str(e)}

    def get_elements_by_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Get all elements stored for a specific URL.

        Args:
            url: URL to get elements for

        Returns:
            List of elements for the URL
        """
        if not self.collection:
            print("[SemanticElementSelector] Collection not initialized, cannot get elements by URL")
            return []

        try:
            # Query all elements for URL
            results = self.collection.get(
                where={"url": url},
                include=["metadatas", "documents"]
            )

            if not results["metadatas"]:
                return []

            # Format results
            elements = []
            metadatas = results.get("metadatas") or []
            documents = results.get("documents") or []
            ids = results.get("ids") or []

            for i, metadata in enumerate(metadatas):
                if i < len(documents) and i < len(ids):
                    element = {
                        "element_id": ids[i],
                        "description": documents[i],
                        "selector": metadata.get("selector", ""),
                        "tag": metadata.get("tag", ""),
                        "category": metadata.get("category", ""),
                        "url": metadata.get("url", ""),
                        "domain": metadata.get("domain", ""),
                        "aria_label": metadata.get("aria_label", ""),
                        "placeholder": metadata.get("placeholder", ""),
                        "text_content": metadata.get("text_content", ""),
                        "inner_text": metadata.get("inner_text", ""),
                        "metadata": metadata
                    }
                    elements.append(element)

            return elements

        except Exception as e:
            print(f"[SemanticElementSelector] Get elements by URL failed: {e}")
            return []

    def clear_domain(self, domain: str) -> int:
        """
        Clear all elements for a specific domain.

        Args:
            domain: Domain to clear

        Returns:
            Number of elements deleted
        """
        if not self.collection:
            print("[SemanticElementSelector] Collection not initialized, cannot clear domain")
            return 0

        try:
            # Get all IDs for domain
            results = self.collection.get(
                where={"domain": domain},
                include=[]
            )

            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                return len(results["ids"])

            return 0

        except Exception as e:
            print(f"[SemanticElementSelector] Clear domain failed: {e}")
            return 0

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get overall collection statistics.

        Returns:
            Collection statistics
        """
        if not self.collection:
            return {"error": "Collection not initialized"}

        try:
            # Get all elements
            results = self.collection.get(include=["metadatas"])

            if not results["metadatas"]:
                return {"total_elements": 0, "domains": {}, "categories": {}}

            # Count by domain and category
            domains = {}
            categories = {}

            for metadata in results["metadatas"]:
                # Domain stats
                domain = metadata.get("domain", "unknown")
                domains[domain] = domains.get(domain, 0) + 1

                # Category stats
                category = metadata.get("category", "unknown")
                categories[category] = categories.get(category, 0) + 1

            return {
                "total_elements": len(results["metadatas"]),
                "domains": domains,
                "categories": categories,
                "collection_name": self.collection_name
            }

        except Exception as e:
            return {"error": str(e)}

    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain name
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain

        except:
            return "unknown"

    def create_task_intent(self, task_type: str, specific_request: Optional[str] = None) -> str:
        """
        Create standardized task intent for semantic search.

        Args:
            task_type: Task type (search, navigate, etc.)
            specific_request: Specific element request

        Returns:
            Standardized intent string
        """
        base_intents = {
            "search": "search input field for entering search queries",
            "navigate": "navigation link or button for moving between pages",
            "form_fill": "form input field for entering data",
            "click_action": "clickable button or action element",
            "extract": "data container or list element"
        }

        base = base_intents.get(task_type, f"{task_type} element")

        if specific_request:
            return f"{specific_request} - {base}"
        else:
            return base

    def learn_from_success(self, element_id: str, task_intent: str) -> None:
        """
        Learn from successful element usage to improve future searches.

        Args:
            element_id: ID of successfully used element
            task_intent: Task intent that worked
        """
        if not self.collection:
            print("[SemanticElementSelector] Collection not initialized, cannot learn from success")
            return

        try:
            # Get element metadata
            results = self.collection.get(
                ids=[element_id],
                include=["metadatas", "documents"]
            )

            if results["metadatas"] and results["documents"]:
                metadata = results["metadatas"][0]
                current_doc = results["documents"][0]

                # Enhance description with successful usage
                enhanced_doc = f"{current_doc} - SUCCESSFUL: {task_intent}"

                # Update the document
                self.collection.update(
                    ids=[element_id],
                    documents=[enhanced_doc]
                )

        except Exception as e:
            print(f"[SemanticElementSelector] Learning failed: {e}")

    def reset_collection(self) -> None:
        """
        Reset the entire collection (for testing/debugging).
        """
        if not self.client:
            print("[SemanticElementSelector] Client not initialized, cannot reset collection")
            return

        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Interactive elements for semantic search"}
            )
        except Exception as e:
            print(f"[SemanticElementSelector] Reset failed: {e}")


# Global instance for easy access
_element_selector = None

def get_element_selector() -> SemanticElementSelector:
    """
    Get global element selector instance.

    Returns:
        SemanticElementSelector instance
    """
    global _element_selector
    if _element_selector is None:
        print("[get_element_selector] Creating new global instance")
        _element_selector = SemanticElementSelector()
    else:
        print("[get_element_selector] Reusing existing global instance")
    return _element_selector
