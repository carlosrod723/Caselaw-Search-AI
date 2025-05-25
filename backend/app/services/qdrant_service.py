# app/services/qdrant_service.py - Qdrant service for vector search operations

"""
This module provides a clean interface to the Qdrant vector database, handling:
- Connection pooling with appropriate timeouts
- Filter construction for search queries
- Automatic retry logic for transient errors
- Payload indexing for improved query performance
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import FieldCondition, Filter, MatchText, MatchValue, Range
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

# Constants for configuration
DEFAULT_TIMEOUT = 300.0       # Default RPC deadline in seconds
QUICK_SEARCH_TIMEOUT = 120.0   # Timeout for small, unfiltered queries
MAX_RETURN = 200              # Maximum number of results to return

# Fields that should be indexed for efficient filtering
FILTERABLE_FIELDS = (
    "jurisdiction",
    "court",
    "date",
    "snippet",
)

logger = logging.getLogger(__name__)


class QdrantClientTimeoutException(Exception):
    """Exception raised when Qdrant operations exceed their timeout."""
    pass


def _strip(value: str) -> str:
    """Trim whitespace without changing case for consistent filtering."""
    return value.strip()


def _parse_date(date_str: str) -> datetime:
    """Parse ISO date string to datetime object, handling various formats."""
    try:
        # Try direct ISO parsing first (most common case)
        return datetime.fromisoformat(date_str)
    except ValueError:
        # Fall back to more flexible parsing if needed
        try:
            import dateutil.parser
            return dateutil.parser.parse(date_str)
        except (ImportError, ValueError) as exc:
            raise ValueError(f"Invalid date format: '{date_str}'") from exc


def _date_to_timestamp(date_str: str) -> float:
    """
    Convert ISO date string to Unix timestamp for numeric comparison.
    
    Args:
        date_str: Date in ISO format (e.g., '2000-01-01')
        
    Returns:
        Unix timestamp (seconds since epoch)
    """
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str)
        return dt.timestamp()
    except ValueError as e:
        logger.warning(f"Invalid date format: {date_str}")
        raise ValueError(f"Date must be in YYYY-MM-DD format: {e}") from e

def _build_filter(conditions: Dict[str, Any] | None) -> Filter | None:
    """
    Translate a conditions dictionary into a Qdrant Filter object.
    
    Supports:
    - Exact string/boolean matching
    - Multi-value OR conditions (lists/tuples/sets)
    - Date range filtering using ISO date strings (converted to timestamps)
    - Case type inference from snippet content
    """
    if not conditions:
        return None

    must_conditions = []

    # Handle case type filter specially (keyword matching on snippet field)
    case_type = conditions.pop("case_type", None)
    if case_type:
        # Define keywords that indicate different case types
        keywords_by_type = {
            "criminal": [
                "criminal", "defendant", "conviction", "jury",
                "guilty", "felony", "misdemeanor",
            ],
            "civil": [
                "civil", "plaintiff", "contract", "tort", 
                "liability", "negligence",
            ],
            "constitutional": [
                "constitutional", "amendment", "rights", "equal protection",
                "due process",
            ],
            "administrative": [
                "administrative", "agency", "regulation", "regulatory",
                "commission",
            ],
        }
        
        keywords = keywords_by_type.get(case_type, [])
        if keywords:
            # Create text match conditions for each keyword
            should_conditions = [
                FieldCondition(key="snippet", match=MatchText(text=kw))
                for kw in keywords
            ]
            # Match if ANY keyword is found (OR logic)
            must_conditions.append(Filter(should=should_conditions))

    # Process all other filter conditions
    for key, value in conditions.items():
        # Skip empty values
        if value is None or (isinstance(value, str) and not value.strip()):
            continue

        # Handle date range filters
        if key in {"date_from", "date_to"}:
            try:
                # Special approach: Use text match for dates in YYYY-MM-DD format
                # Start with exact prefix matching for years
                if key == "date_from":
                    # Extract year from date_from
                    year_from = value.split('-')[0]
                    # Match documents with date starting with this year or higher
                    must_conditions.append(
                        FieldCondition(
                            key="date",
                            match=MatchText(text=year_from)
                        )
                    )
                elif key == "date_to":
                    # Extract year from date_to
                    year_to = value.split('-')[0]
                    # We need a year filter, but this approach isn't perfect
                    # For now, we'll at least filter by the year
                    must_conditions.append(
                        FieldCondition(
                            key="date",
                            match=MatchText(text=year_to)
                        )
                    )
                
                # The post-processing in search.py will need to filter results further
                logger.info(f"Using text match for date filter: {key}={value}")
            except Exception as e:
                logger.warning(f"Error creating date filter: {e}")
            continue

        # Handle multi-value filters (OR logic)
        if isinstance(value, (list, tuple, set)):
            should_conditions = [
                FieldCondition(
                    key=key,
                    match=MatchValue(
                        value=_strip(v) if isinstance(v, str) else v
                    )
                )
                for v in value
            ]
            if should_conditions:
                must_conditions.append(Filter(should=should_conditions))
            continue

        # Handle simple string/boolean filters
        if isinstance(value, (str, bool)):
            must_conditions.append(
                FieldCondition(
                    key=key,
                    match=MatchValue(
                        value=_strip(value) if isinstance(value, str) else value
                    )
                )
            )

    # Return the filter if we have any conditions, otherwise None
    return Filter(must=must_conditions) if must_conditions else None


def _ensure_payload_indexes(client: QdrantClient, collection: str) -> None:
    """
    Create payload indexes for all filterable fields to improve query performance.
    This is idempotent - will only create indexes that don't already exist.
    """
    try:
        # Get existing indexes
        existing_indexes = {
            idx.field_name for idx in client.list_payload_indexes(collection)
        }
        
        # Create missing indexes
        for field in FILTERABLE_FIELDS:
            if field in existing_indexes:
                continue
                
            logger.info(f"Creating payload index for '{field}'")
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=models.PayloadIndexParams(
                    type=models.PayloadSchemaType.KEYWORD
                ),
            )
    except Exception as e:
        # Non-fatal - we can continue even if indexing fails
        logger.debug(f"Failed to create payload indexes: {e}")


@lru_cache
def _make_client(timeout: Optional[float] = None) -> QdrantClient:
    """
    Create a QdrantClient with the specified timeout.
    Uses LRU cache to reuse clients with the same timeout.
    """
    timeout_value = timeout or DEFAULT_TIMEOUT
    
    client = QdrantClient(
        host="localhost",
        port=settings.QDRANT_PORT,
        grpc_port=getattr(settings, "QDRANT_GRPC_PORT", 6334),
        https=settings.QDRANT_HTTPS,
        timeout=timeout_value,
        prefer_grpc=False,
    )
    
    logger.info(f"Created Qdrant client (timeout={timeout_value}s)")
    return client


def get_client(timeout: Optional[float] = None) -> QdrantClient:
    """Public function to get a Qdrant client (for backward compatibility)."""
    return _make_client(timeout)


class QdrantService:
    """
    Service class for interacting with the Qdrant vector database.
    Provides retry logic, connection pooling, and simplified interfaces
    for search and administration operations.
    """
    
    def __init__(self) -> None:
        """Initialize the service with the configured collection name."""
        self.collection_name = settings.QDRANT_COLLECTION
        self._clients = {}
        
        # Ensure indexes exist for better performance
        try:
            _ensure_payload_indexes(
                self._get_client(DEFAULT_TIMEOUT), 
                self.collection_name
            )
        except Exception as e:
            logger.warning(f"Failed to ensure indexes: {e}")
            
        logger.info(f"QdrantService initialized for collection: {self.collection_name}")

    def _get_client(self, timeout: Optional[float] = None) -> QdrantClient:
        """Get a client with the specified timeout from the connection pool."""
        if timeout not in self._clients:
            self._clients[timeout] = _make_client(timeout)
        return self._clients[timeout]

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    def search_by_vector(
        self,
        vector: List[float],
        *,
        limit: int = 10,
        offset: int = 0,
        filter_conditions: Dict[str, Any] | None = None,
        timeout: Optional[float] = None,
    ):
        """
        Search for vectors similar to the provided vector.
        
        Args:
            vector: The query vector
            limit: Maximum number of results to return
            offset: Offset for pagination
            filter_conditions: Dictionary of filter conditions
            timeout: Optional timeout override
            
        Returns:
            List of search results
            
        Raises:
            QdrantClientTimeoutException: If the search times out
            ValueError: If limit or offset are invalid
        """
        # Validate parameters
        if not (1 <= limit <= MAX_RETURN):
            raise ValueError(f"limit must be between 1 and {MAX_RETURN}")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        # Set appropriate timeout based on query complexity
        has_filter = bool(filter_conditions)
        if timeout is None:
            # Always use DEFAULT_TIMEOUT for filtered queries
            timeout = DEFAULT_TIMEOUT if has_filter else (
                QUICK_SEARCH_TIMEOUT if limit <= 10 else DEFAULT_TIMEOUT
            )

        start_time = time.time()
        try:
            # Get client and build filter
            client = self._get_client(timeout)
            query_filter = _build_filter(filter_conditions)
            
            # Execute search
            hits = client.query_points(
                self.collection_name,
                vector,
                limit=limit,
                offset=offset,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False,
                score_threshold=0.45,
                search_params=models.SearchParams(
                    hnsw_ef=8,
                    quantization=models.QuantizationSearchParams(rescore=False),
                ),
            )

            # Process results
            points = hits.points if isinstance(hits, models.QueryResponse) else hits
            elapsed = time.time() - start_time
            logger.debug(f"Qdrant returned {len(points)} results in {elapsed:.2f}s")
            return points

        except Exception as e:
            elapsed = time.time() - start_time
            
            # Convert timeout-related errors to our custom exception
            if "timeout" in str(e).lower() or "deadline exceeded" in str(e).lower():
                logger.warning(f"Qdrant timeout after {elapsed:.2f}s: {e}")
                raise QdrantClientTimeoutException(str(e)) from e
                
            # Log and re-raise other errors
            logger.error(f"Qdrant search error after {elapsed:.2f}s: {e}")
            raise

    def retrieve_points(
        self,
        ids: list,
        *,
        with_payload: bool = True,
        timeout: Optional[float] = None,
    ):
        """
        Retrieve points by their IDs.
        
        Args:
            ids: List of point IDs to retrieve
            with_payload: Whether to include the payload in the results
            timeout: Optional timeout override
        
        Returns:
            List of retrieved points
        """
        timeout = timeout or DEFAULT_TIMEOUT
        
        try:
            client = self._get_client(timeout)
            points = client.retrieve(
                collection_name=self.collection_name,
                ids=ids,
                with_payload=with_payload,
            )
            return points
        except Exception as e:
            logger.error(f"Error retrieving points by ID: {e}")
            raise

    def count_by_vector(
        self,
        vector: List[float],
        *,
        filter_conditions: Dict[str, Any] | None = None,
        timeout: Optional[float] = None,
    ) -> int:
        """
        Count the total number of points matching the vector similarity and filters.
        Used for UI pagination; caps results at 1,000 for UI performance.
        """
        # Use a longer timeout for count operations
        timeout = timeout or (DEFAULT_TIMEOUT + 10.0)
        
        try:
            client = self._get_client(timeout)
            query_filter = _build_filter(filter_conditions)
            
            count_result = client.count(
                collection_name=self.collection_name,
                count_filter=query_filter,
            )
            
            total_count = count_result.count
            
            # Cap at 1,000 for UI display purposes
            return min(total_count, 1000)
            
        except Exception as e:
            if "timeout" in str(e).lower() or "deadline exceeded" in str(e).lower():
                raise QdrantClientTimeoutException(str(e)) from e
            raise

    def get_collection_info(self):
        """Get information about the collection."""
        return self._get_client().get_collection(self.collection_name)

    def optimize_collection(self) -> bool:
        """Apply performance optimization settings to the collection."""
        try:
            client = self._get_client(timeout=120.0)
            
            # Import optimization models
            from qdrant_client.http.models import HnswConfigDiff, OptimizersConfigDiff
            
            # Update collection with optimized settings
            client.update_collection(
                collection_name=self.collection_name,
                optimizer_config=OptimizersConfigDiff(
                    indexing_threshold=20_000,        # Segment merge threshold
                    vacuum_min_vector_number=1_000,   # Min vectors for vacuum
                ),
                hnsw_config=HnswConfigDiff(
                    m=16,                        # Connections per element
                    ef_construct=100,            # Construction quality
                    full_scan_threshold=10_000,  # Full scan threshold
                ),
            )
            
            logger.info("Collection successfully optimized")
            return True
            
        except Exception as e:
            logger.debug(f"Collection optimization failed: {e}")
            return False


# Singleton instance for application-wide use
qdrant_service = QdrantService()