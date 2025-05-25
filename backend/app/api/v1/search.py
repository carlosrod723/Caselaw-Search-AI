# app/api/v1/search.py - Search API endpoints and helper functions for semantic search over caselaw.
"""
Search API endpoints and helper functions for semantic search over caselaw.

This module handles:
1. Query refinement using OpenAI
2. Vector embedding generation 
3. Semantic search against Qdrant vector database
4. Result formatting and summarization
5. Caching for performance optimization
6. SQLite-based filtering for performance optimization
"""

from __future__ import annotations

import sqlite3
import asyncio
import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, status
from starlette.concurrency import run_in_threadpool

import openai as openai_mod
from app.models.search import SearchQuery, SearchResponse, SearchResult
from app.services.openai_service import openai_service
from app.services.qdrant_service import (
    QdrantClientTimeoutException,
    qdrant_service,
)

from app.services.case_document_service import case_document_service
from app.services.sqlite_search_service import sqlite_search_service

# Configure logging
logger = logging.getLogger(__name__)

# Cache configuration
RESULTS_CACHE: dict[str, tuple[float, SearchResponse, int]] = {}
CACHE_TTL = 3600  # Cache results for 1 hour 

# Count cache configuration
count_cache: dict[str, tuple[float, int]] = {}
count_cache_ttl = 3600  # 1 hour

# Search configuration
QUICK_SEARCH_THRESHOLD = 10  # Queries with limit <= 10 use quick search timeout
QUICK_SEARCH_TIMEOUT = 30    # 30 seconds for quick searches
FULL_SEARCH_TIMEOUT = 120    # 120 seconds for full searches
MAX_RESULTS_FOR_FILTERING = 200  # Maximum results to fetch for post-filtering

def extract_judge(snippet: str) -> str:
    """
    Extract judge information from a case snippet.
    Returns the judge name or None if not found.
    """
    import re
    
    if not snippet:
        return None
    
    # Patterns to match judge information
    JUDGE_PATTERNS = [
        # LASTNAME, J.
        r'^([A-Za-z]+),\s+J\.',
        
        # LASTNAME, Judge.
        r'^([A-Za-z]+),\s+Judge\.?',
        
        # LASTNAME, Justice.
        r'^([A-Za-z]+),\s+Justice',
        
        # LASTNAME, C. J.
        r'^([A-Za-z]+),\s+C\.\s*J\.',
        
        # LASTNAME, Chief Judge.
        r'^([A-Za-z]+),\s+Chief\s+Judge',
        
        # LASTNAME, Presiding Judge.
        r'^([A-Za-z]+),\s+Presiding\s+Judge',
        
        # JUSTICE LASTNAME delivered
        r'^JUSTICE\s+([A-Za-z]+)',
        
        # Justice LASTNAME delivered
        r'(?:^|\n)Justice\s+([A-Za-z]+)',
        
        # LASTNAME, J., delivered the opinion
        r'^([A-Za-z]+),\s+J\.,\s+delivered',
        
        # LASTNAME, C. J., delivered the opinion
        r'^([A-Za-z]+),\s+C\.\s*J\.,\s+delivered',
        
        # Mr. Chief Justice LASTNAME
        r'Mr\.\s+Chief\s+Justice\s+([A-Za-z]+)',
        
        # OPINION \n LASTNAME, Judge.
        r'OPINION\s*\n\s*([A-Za-z]+),\s+Judge',
        
        # Per Curiam (special case - court as a whole)
        r'^PER\s+CURIAM',
    ]
    
    # Try different patterns to match judge information
    for pattern in JUDGE_PATTERNS:
        match = re.search(pattern, snippet.strip(), re.IGNORECASE)
        if match:
            if 'PER CURIAM' in match.group(0).upper():
                return 'Per Curiam'
            return match.group(1).strip()
    
    return None

# Create router with appropriate tags
router = APIRouter(tags=["search"])

# -----------------------------------------------------------------------------
# Helper functions for search operations
# -----------------------------------------------------------------------------
async def _refine_query(raw_query: str) -> str:
    """
    Refine user query with OpenAI to improve search relevance.
    
    Args:
        raw_query: Original user query
        
    Returns:
        Refined query optimized for semantic search
    """
    return await run_in_threadpool(openai_service.refine_query, raw_query)


async def _embed(text: str) -> list[float]:
    """
    Generate embedding vector for the given text.
    
    Args:
        text: Text to embed
        
    Returns:
        List of floats representing the embedding vector
    """
    return await run_in_threadpool(openai_service.get_embedding, text)


async def _qdrant_search(
    *,
    vector: list[float],
    limit: int,
    filters: Dict[str, Any] | None,
    offset: int = 0,  # Add offset parameter with default value of 0
    timeout: Optional[float] = None,
):
    """
    Execute vector search in Qdrant database.
    
    Args:
        vector: Query vector
        limit: Maximum results to return
        filters: Optional filter conditions
        offset: Starting index for pagination (Default: 0)
        timeout: Optional timeout override
        
    Returns:
        List of search results
    """
    logger.info(f"Executing Qdrant search with offset={offset}, limit={limit}")
    return await run_in_threadpool(
        qdrant_service.search_by_vector,
        vector=vector,
        limit=limit,
        offset=offset,  # Pass the offset parameter to the service
        filter_conditions=filters,
        timeout=timeout,
    )

async def _qdrant_count(
    *,
    vector: list[float],
    filters: Dict[str, Any] | None,
) -> int:
    """
    Get the total count of relevant results, limited to top 200.
    
    Args:
        vector: Query vector
        filters: Optional filter conditions
        
    Returns:
        Count of matching results
    """
    # Create a cache key from the first few elements of the vector and the filters
    # Don't use the whole vector to keep the key reasonably sized
    vector_prefix = str(vector[:5])  # First 5 elements are enough to identify the query
    filters_str = str(filters) if filters else "none"
    cache_key = f"{vector_prefix}_{filters_str}"
    
    # Check if we have a cached result
    if cache_key in count_cache and time.time() - count_cache[cache_key][0] < count_cache_ttl:
        cached_time, cached_count = count_cache[cache_key]
        age_seconds = int(time.time() - cached_time)
        logger.info(f"Using cached count: {cached_count} results (cached {age_seconds}s ago)")
        return cached_count
    
    try:
        # Use a larger limit just to count the relevant results
        max_results = MAX_RESULTS_FOR_FILTERING
        
        # Search with the larger limit to get a better count estimate
        count_hits = await _qdrant_search(
            vector=vector,
            limit=max_results,
            offset=0,  # Use offset 0 for counting
            filters=filters,
            timeout=QUICK_SEARCH_TIMEOUT  # Use a quick timeout for this estimate
        )
        
        # Return the actual number of hits found, up to our maximum
        result_count = len(count_hits)
        logger.info(f"Found {result_count} relevant results out of maximum {max_results}")
        
        # Cache the result
        count_cache[cache_key] = (time.time(), result_count)
        
        # Clean up cache if it gets too large
        if len(count_cache) > 100:
            # Remove oldest 20% of entries
            oldest_keys = sorted(count_cache.keys(), key=lambda k: count_cache[k][0])[:20]
            for k in oldest_keys:
                count_cache.pop(k, None)
        
        return result_count
        
    except Exception as e:
        logger.warning(f"Error estimating total count, using fallback: {e}")
        # Return a reasonable default if we can't count
        return 20

async def _format_hits(hits) -> list[SearchResult]:
    """
    Convert raw Qdrant hits to SearchResult objects and verify metadata against SQLite.
    Includes case type information from the case_types table.
    """
    results: list[SearchResult] = []
    
    # First pass: collect data and prepare for verification
    for idx, hit in enumerate(hits):
        payload = hit.payload or {}
        
        # Get case_id from payload
        case_id = payload.get("case_id", "")
        
        # Default case type is None
        case_type = None
        
        # If we have a case_id, verify the metadata against SQLite
        if case_id:
            # Try to get the correct data from SQLite
            try:
                # This can be made asynchronous if needed for performance
                sqlite_case = await run_in_threadpool(
                    case_document_service.get_case_by_id, case_id, False
                )
                
                # Get case type from case_types table
                conn = sqlite3.connect(case_document_service.sqlite_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT type FROM case_types WHERE case_id = ?", (case_id,))
                type_result = cursor.fetchone()
                if type_result:
                    case_type = type_result[0]
                conn.close()
                
                if sqlite_case:
                    # Use SQLite data instead of Qdrant data for consistency
                    metadata = {
                        "case_id": case_id,
                        "jurisdiction": sqlite_case.get("jurisdiction", payload.get("jurisdiction", "")),
                        "court": sqlite_case.get("court", payload.get("court", "")),
                        "date": sqlite_case.get("decision_date", payload.get("date", "")),
                        "citation": sqlite_case.get("citations", payload.get("citation", "")),
                        "judges": sqlite_case.get("judges", payload.get("judges", "")),
                        "case_type": case_type  # Add case type to metadata
                    }
                    
                    # Use the correct title from SQLite
                    title = sqlite_case.get("name_abbreviation", "")
                    
                    # If SQLite title differs from Qdrant, log the discrepancy
                    if title and payload.get("title") and title != payload.get("title"):
                        logger.warning(f"Title mismatch - Qdrant: '{payload.get('title')}', SQLite: '{title}' for case_id {case_id}")
                else:
                    # If no SQLite data, use Qdrant data
                    metadata = {
                        "case_id": case_id,
                        "jurisdiction": payload.get("jurisdiction", ""),
                        "court": payload.get("court", ""),
                        "date": payload.get("date", ""),
                        "citation": payload.get("citation", ""),
                        "judges": payload.get("judges", ""),
                        "case_type": case_type  # Add case type to metadata
                    }
                    title = payload.get("title", "")
            except Exception as e:
                logger.error(f"Error verifying metadata for case_id {case_id}: {e}")
                # Fall back to Qdrant data
                metadata = {
                    "case_id": case_id,
                    "jurisdiction": payload.get("jurisdiction", ""),
                    "court": payload.get("court", ""),
                    "date": payload.get("date", ""),
                    "citation": payload.get("citation", ""),
                    "judges": payload.get("judges", ""),
                    "case_type": None  # Set case type to None on error
                }
                title = payload.get("title", "")
        else:
            # No case_id, just use whatever Qdrant provided
            metadata = {
                "case_id": "",
                "jurisdiction": payload.get("jurisdiction", ""),
                "court": payload.get("court", ""),
                "date": payload.get("date", ""),
                "citation": payload.get("citation", ""),
                "judges": payload.get("judges", ""),
                "case_type": None  # Set case type to None for missing case_id
            }
            title = payload.get("title", "")
        
        # Create result object
        results.append(
            SearchResult(
                id=hit.id,
                score=getattr(hit, "score", 0.0),
                title=title,
                url=f"/case/{metadata.get('case_id')}" if metadata.get("case_id") else "",
                text=payload.get("snippet", ""),
                metadata=metadata,
                is_summarized=False,
                original_text=None,
                summary=payload.get("snippet", ""),  
                keyPassages=payload.get("keyPassages", []),
                caseType=metadata.get("case_type") 
            )
        )
    
    return results

def _is_date_in_range(date_str: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> bool:
    """
    Check if a date string is within the specified range.
    
    Args:
        date_str: Date to check in YYYY-MM-DD format
        date_from: Optional start date (inclusive) in YYYY-MM-DD format
        date_to: Optional end date (inclusive) in YYYY-MM-DD format
        
    Returns:
        True if the date is within range, False otherwise
    """
    if not date_str:
        return False
        
    if not date_from and not date_to:
        return True
        
    if date_from and date_str < date_from:
        return False
        
    if date_to and date_str > date_to:
        return False
        
    return True


async def _filter_by_date(
    results: List[SearchResult],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[SearchResult]:
    """
    Post-process search results to filter by date range.
    
    Args:
        results: List of search results to filter
        date_from: Optional start date (inclusive) in YYYY-MM-DD format
        date_to: Optional end date (inclusive) in YYYY-MM-DD format
        
    Returns:
        Filtered list of search results
    """
    if not date_from and not date_to:
        return results
        
    filtered_results = []
    
    for result in results:
        # Get the date from metadata
        result_date = result.metadata.get("date", "")
        if not result_date:
            continue
            
        # Check if date is within range
        if _is_date_in_range(result_date, date_from, date_to):
            filtered_results.append(result)
            
    return filtered_results

async def _filter_by_case_type(
    results: List[SearchResult],
    case_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 20
) -> Tuple[List[SearchResult], int]:
    """
    Post-process search results to filter by case type.
    
    Args:
        results: List of search results to filter
        case_type: The case type to filter for (criminal, civil, etc.)
        offset: Offset for pagination
        limit: Limit for pagination
        
    Returns:
        Tuple of (paginated filtered results, total filtered count)
    """
    if not case_type or case_type == "all":
        # Apply pagination to the original results if no filtering
        total_count = len(results)
        start_idx = min(offset, total_count)
        end_idx = min(offset + limit, total_count)
        return results[start_idx:end_idx], total_count
    
    # Get case IDs from results for efficient lookup
    case_ids = [r.metadata.get("case_id") for r in results if r.metadata.get("case_id")]
    
    if not case_ids:
        return [], 0
    
    try:
        # Use case_types table for accurate filtering
        conn = sqlite3.connect(case_document_service.sqlite_db_path)
        cursor = conn.cursor()
        
        # Query case_types table for the specified type
        placeholders = ','.join(['?' for _ in case_ids])
        query = f"SELECT case_id FROM case_types WHERE type = ? AND case_id IN ({placeholders})"
        params = [case_type.lower()] + case_ids
        
        cursor.execute(query, params)
        matching_case_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        # Filter results based on matching case IDs
        filtered_results = [
            r for r in results 
            if r.metadata.get("case_id") in matching_case_ids
        ]
        
        # Get total count of filtered results before pagination
        total_filtered = len(filtered_results)
        
        logger.info(f"Case type filter for '{case_type}' found {total_filtered} matches from {len(results)} results")
        
        # Apply pagination to filtered results
        start_idx = min(offset, total_filtered)
        end_idx = min(offset + limit, total_filtered)
        paginated_results = filtered_results[start_idx:end_idx]
        
        logger.info(f"Pagination applied: offset={offset}, limit={limit}, returning {len(paginated_results)} results")
        
        return paginated_results, total_filtered
        
    except Exception as e:
        logger.error(f"Error filtering by case type: {e}")
        # Return paginated original results if there's an error
        total_count = len(results)
        start_idx = min(offset, total_count)
        end_idx = min(offset + limit, total_count)
        return results[start_idx:end_idx], total_count

async def _sort_results(
    results: List[SearchResult],
    sort: Optional[str] = None
) -> List[SearchResult]:
    """
    Sort search results based on the sort parameter.
    
    Args:
        results: List of search results to sort
        sort: Sort parameter ('date_desc', 'date_asc', etc.)
        
    Returns:
        Sorted list of search results
    """
    if not sort or sort == 'relevance':
        # Keep original order (by relevance)
        return results
    
    # Sort by date (newest first)
    if sort == 'date_desc':
        return sorted(
            results, 
            key=lambda x: x.metadata.get('date', ''), 
            reverse=True
        )
    
    # Sort by date (oldest first)
    if sort == 'date_asc':
        return sorted(
            results, 
            key=lambda x: x.metadata.get('date', '')
        )
    
    # Default: return in original order
    return results

async def _is_filter_only_search(query: str, filters: Dict[str, Any]) -> bool:
    """
    Determine if the search is filter-only (no semantic search needed).
    
    This function checks if the search can be handled by SQLite filtering
    without using vector search for better performance.
    
    Args:
        query: The search query text
        filters: The filter conditions
        
    Returns:
        True if the search can be handled by SQLite filtering alone
    """
    # If the query is empty or just noise, we can use SQLite
    if not query or query.strip() in ('*', '', '.'):
        return True
        
    # If we have significant filters and minimal query
    if filters:
        # Count filter types
        filter_count = len(filters)
        has_date_filter = "date_from" in filters or "date_to" in filters
        
        # If we have date filters, use SQLite for better performance
        # Date filtering in vector search is slow due to post-processing
        if has_date_filter and (not query.strip() or len(query.strip()) <= 5):
            logger.info(f"Using SQLite for date filtering with query: '{query}'")
            return True
            
        # If we have other filters and minimal query, use SQLite
        if filter_count >= 2 and len(query.strip()) <= 3:
            logger.info(f"Using SQLite for multi-filter search with query: '{query}'")
            return True
            
        # If the query is very short and we have at least one filter, use SQLite
        if len(query.strip()) <= 2 and filter_count >= 1:
            logger.info(f"Using SQLite for filtered search with short query: '{query}'")
            return True
    
    # Otherwise, we need vector search for semantic matching
    return False

async def _sqlite_filter_search(
    query: str,
    filters: Dict[str, Any],
    limit: int,
    offset: int,
) -> Tuple[List[SearchResult], int]:
    """
    Perform a filter-based search using SQLite for faster performance.
    Includes error handling with graceful fallback.
    
    Args:
        query: The search query (may be empty for pure filtering)
        filters: Filter conditions
        limit: Maximum results to return
        offset: Offset for pagination
        
    Returns:
        Tuple of (search results, total count)
    """
    # Extract filter parameters
    jurisdiction = filters.get('jurisdiction')
    court = filters.get('court')
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')
    case_type = filters.get('case_type')
    sort = filters.get('sort')
    
    # Log the filter operation
    logger.info(f"Using SQLite filtering with: jurisdiction={jurisdiction}, court={court}, dates={date_from}-{date_to}")
    
    try:
        # Execute the filter query
        start_time = time.time()
        sqlite_results, total_count = await run_in_threadpool(
            sqlite_search_service.filter_cases,
            jurisdiction=jurisdiction,
            court=court,
            date_from=date_from,
            date_to=date_to,
            case_type=case_type,
            limit=limit,
            offset=offset,
            sort=sort,
        )
        
        # Format the results
        results = await run_in_threadpool(
            sqlite_search_service.format_results,
            sqlite_results
        )
        
        elapsed = time.time() - start_time
        logger.info(f"SQLite filtering completed in {elapsed:.3f}s, found {total_count} results")
        
        return results, total_count
    
    except Exception as e:
        # Log the error
        logger.error(f"SQLite search failed: {e}")
        logger.error(traceback.format_exc())
        
        # Return empty results rather than crashing
        logger.warning("Returning empty results due to SQLite error")
        return [], 0

# -----------------------------------------------------------------------------
# Search Endpoints
# -----------------------------------------------------------------------------
@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search(query: SearchQuery) -> SearchResponse:
    """
    Main vector-search endpoint with SQLite optimization for filter-only searches.
    
    1. Checks if search can be handled by SQLite filters for better performance
    2. For filter-only searches, uses direct SQLite queries
    3. For semantic searches, uses the full vector search pipeline:
       a. Refines the user query with OpenAI
       b. Generates an embedding vector
       c. Searches Qdrant vector database
       d. Applies post-processing filters (e.g., date range)
       e. Batch-summarizes snippets for improved readability
    """
    start = time.time()
    logger.info(
        "Processing search query=%r  limit=%s  offset=%s  filters=%s",
        query.query,
        query.limit,
        query.offset,
        query.filters,
    )

    # Check cache for exact query
    cache_key = f"{query.query}_{query.limit}_{query.offset}_{query.filters}"
    if (entry := RESULTS_CACHE.get(cache_key)) and time.time() - entry[0] < CACHE_TTL:
        logger.info("Cache hit for %r", cache_key)
        resp = entry[1]
        resp.total_available = entry[2]
        return resp

    # Check if this is a filter-only search that can use SQLite
    if await _is_filter_only_search(query.query, query.filters):
        logger.info(f"Using SQLite filtering for query: {query.query}")
        
        # Perform SQLite filtering
        results, total_available = await _sqlite_filter_search(
            query.query,
            query.filters,
            query.limit,
            query.offset,
        )
        
        # Create response
        resp = SearchResponse(
            results=results,
            query=query.query,
            refined_query=query.query,  # No refinement for filter-only
            total=len(results),
            total_available=total_available,
            performance_stats={
                "total_time_ms": int((time.time() - start) * 1000),
                "used_sqlite": True,  # Flag to indicate SQLite was used
            },
        )
        
        # Cache the results
        if len(query.query) > 1 or query.filters:
            RESULTS_CACHE[cache_key] = (time.time(), resp, total_available)
            
        return resp

    # For semantic searches, continue with the existing vector search logic
    # Extract date filters for post-processing
    date_from = None
    date_to = None
    case_type = None
    sort_param = None  # Add this line
    qdrant_filters = {}

    if query.filters:
        # Copy filters to ensure we don't modify the original
        filters_copy = query.filters.copy()
        
        # Extract date filters for post-processing
        date_from = filters_copy.pop("date_from", None)
        date_to = filters_copy.pop("date_to", None)
        
        # Extract case_type filter for post-processing
        case_type = filters_copy.pop("case_type", None)
        
        # Extract sort parameter 
        sort_param = filters_copy.pop("sort", None)
        
        # Use remaining filters for Qdrant search
        qdrant_filters = filters_copy
    
    # Set timeout based on query size
    quick = query.limit <= QUICK_SEARCH_THRESHOLD
    timeout = QUICK_SEARCH_TIMEOUT if quick else FULL_SEARCH_TIMEOUT

    # Step 1: Refine query with OpenAI
    refine_t0 = time.time()
    refined_query = (
        await _refine_query(query.query) if len(query.query.strip()) > 2 else query.query
    )
    refine_ms = int((time.time() - refine_t0) * 1000)

    # Step 2: Generate embedding
    embed_t0 = time.time()
    vector = await _embed(refined_query)
    embed_ms = int((time.time() - embed_t0) * 1000)

    # Step 3: Search vector database with non-date filters
    search_t0 = time.time()
    
    # Request more results if date filtering will be applied
    search_limit = MAX_RESULTS_FOR_FILTERING if (date_from or date_to) else query.limit
    search_offset = 0 if (date_from or date_to) else query.offset  # Set offset to 0 for date filtering, otherwise use query offset
    
    logger.info(f"Executing vector search with limit={search_limit}, offset={search_offset}, date_filters={bool(date_from or date_to)}")
    
    hits = await _qdrant_search(
        vector=vector,
        limit=search_limit,
        offset=search_offset,  # Use the calculated offset
        filters=qdrant_filters,
        timeout=timeout,
    )
    search_ms = int((time.time() - search_t0) * 1000)
    logger.info(f"Found {len(hits)} hits in {search_ms / 1000:.2f}s (offset={search_offset}, limit={search_limit})")

    # Step 4: Format and summarize results
    fmt_t0 = time.time()
    results = await _format_hits(hits)
    
    # Apply date filtering
    if date_from or date_to:
        logger.info(f"Before date filtering: {len(results)} results")
        results = await _filter_by_date(results, date_from, date_to)
        logger.info(f"After date filtering: {len(results)} results")
        
        # Apply pagination after filtering
        total_available = len(results)
        start_idx = query.offset
        end_idx = start_idx + query.limit
        
        logger.info(f"Applying pagination with offset={query.offset}, limit={query.limit} (start_idx={start_idx}, end_idx={end_idx})")
        
        # Ensure we don't go out of bounds
        if start_idx >= len(results):
            results = []
        else:
            results = results[start_idx:end_idx]
        
        logger.info(f"After pagination: {len(results)} results")
    else:
        # For non-date filtered searches, pagination is applied directly in Qdrant
        logger.info(f"Using direct Qdrant pagination with offset={query.offset}, limit={query.limit}")
        # Get total count with just the Qdrant filters
        total_available = await _qdrant_count(vector=vector, filters=qdrant_filters)
        if total_available is None:
            total_available = len(results)

    # For semantic searches with case type filtering, use a different approach
    if case_type and case_type != "all":
        # Always get a larger set of results when case type filtering is needed
        search_limit = MAX_RESULTS_FOR_FILTERING
        
        logger.info(f"Getting larger result set for case type filtering, limit={search_limit}")
        
        # Get a large set of results to filter
        large_hits = await _qdrant_search(
            vector=vector,
            limit=search_limit,
            offset=0,  # Always start from the beginning
            filters=qdrant_filters,
            timeout=timeout,
        )
        
        # Format all hits
        large_results = await _format_hits(large_hits)
        
        logger.info(f"Before case type filtering: {len(large_results)} results")
        
        # Filter the entire result set by case type - get all results without pagination first
        filtered_results, total_filtered = await _filter_by_case_type(
            large_results, 
            case_type,
            offset=0,  
            limit=MAX_RESULTS_FOR_FILTERING  
        )
        
        logger.info(f"After case type filtering: {len(filtered_results)} results")
        
        # Apply sorting if specified in filters - AFTER filtering but BEFORE pagination
        if sort_param:
            logger.info(f"Applying sort to filtered results: {sort_param}")
            filtered_results = await _sort_results(filtered_results, sort_param)
            logger.info(f"Filtered results sorted by {sort_param}")
        
        # Set the total available count
        total_available = total_filtered
        
        # Then apply pagination manually to the filtered and sorted results
        start_idx = query.offset
        end_idx = start_idx + query.limit
        
        # Ensure we don't go out of bounds
        if start_idx >= len(filtered_results):
            results = []
        else:
            results = filtered_results[start_idx:end_idx]
        
        logger.info(f"After pagination: {len(results)} results, page={query.offset // query.limit + 1}")
  
    fmt_ms = int((time.time() - fmt_t0) * 1000)

    # For regular searches without case type filtering that need sorting
    if sort_param and not (case_type and case_type != "all"):
        logger.info(f"Sort parameter detected: {sort_param}, fetching larger result set for global sorting")
        
        # Get a larger set of results to ensure proper sorting across pages
        large_hits = await _qdrant_search(
            vector=vector,
            limit=MAX_RESULTS_FOR_FILTERING,  # Get maximum results for proper sorting
            offset=0,  # Start from the beginning
            filters=qdrant_filters,
            timeout=timeout,
        )
        
        # Format all hits
        large_results = await _format_hits(large_hits)
        
        logger.info(f"Retrieved {len(large_results)} results for global sorting")
        
        # Apply global sorting to all results
        logger.info(f"Applying global sort: {sort_param}")
        sorted_results = await _sort_results(large_results, sort_param)
        logger.info(f"All results sorted by {sort_param}")
        
        # Set total available from the larger result set
        total_available = len(sorted_results)
        
        # Apply pagination to the sorted results
        start_idx = query.offset
        end_idx = start_idx + query.limit
        
        # Ensure we don't go out of bounds
        if start_idx >= len(sorted_results):
            results = []
        else:
            results = sorted_results[start_idx:end_idx]
        
        logger.info(f"Returning page {query.offset // query.limit + 1} with {len(results)} results after global sorting")

    # Create response with performance stats
    resp = SearchResponse(
        results=results,
        query=query.query,
        refined_query=refined_query,
        total=len(results),
        total_available=total_available,
        performance_stats={
            "refine_time_ms": refine_ms,
            "embedding_time_ms": embed_ms,
            "search_time_ms": search_ms,
            "format_time_ms": fmt_ms,
            "total_time_ms": int((time.time() - start) * 1000),
            "used_sqlite": False,  # Flag to indicate vector search was used
        },
    )

    # Cache the results if query is substantial
    if len(query.query) > 3:
        RESULTS_CACHE[cache_key] = (time.time(), resp, total_available)
        # Trim cache if it gets too large
        if len(RESULTS_CACHE) > 1_000:
            for k in sorted(RESULTS_CACHE, key=lambda k: RESULTS_CACHE[k][0])[:200]:
                RESULTS_CACHE.pop(k, None)

    return resp

@router.get("/search", response_model=SearchResponse)
async def search_get(
    q: str = Query(..., description="Search query"),
    limit: int = Query(
        10,
        description="Number of results to return",
        ge=1,
        le=200,
    ),
    offset: int = Query(0, description="Offset for pagination"),
    jurisdiction: Optional[str] = None,
    court: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: Optional[str] = None,case_type: Optional[str] = None,
) -> SearchResponse:
    """
    Browser-friendly GET variant of the search endpoint with 
    query parameters instead of JSON body.
    """
    # Log the request parameters
    logger.info(f"Search request: query='{q}', limit={limit}, offset={offset}")
    
    # Build filters from query parameters
    filters: Dict[str, Any] = {}
    if jurisdiction:
        filters["jurisdiction"] = jurisdiction
    if court:
        # Parse comma-separated court values into a list
        if "," in court:
            filters["court"] = [c.strip() for c in court.split(",")]
        else:
            filters["court"] = court
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    if sort:
        filters["sort"] = sort
    if case_type:
        filters["case_type"] = case_type

    # Create query object and call main search function
    query_obj = SearchQuery(
        query=q,
        limit=limit,
        offset=offset,
        filters=filters,
    )
    
    # Call the main search function
    response = await search(query_obj)
    
    # Log the response details for debugging
    logger.info(f"Returning {len(response.results)} results for offset={offset} (first ID: {response.results[0].id if response.results else 'none'})")
    
    return response