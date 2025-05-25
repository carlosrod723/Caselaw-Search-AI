"""
SQLite-based search service for fast filter operations on case data.

This module provides direct SQLite database access for filter-based searches,
bypassing vector search when appropriate for maximum performance.
"""

import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Maximum results to return from SQLite searches
MAX_RESULTS = 1000


class SQLiteSearchService:
    """
    Service for performing filter-based searches directly against the SQLite database.
    This provides fast filtering without the overhead of vector search.
    """
    
    def __init__(self):
        """Initialize the SQLite search service."""
        self.db_path = settings.SQLITE_DB_PATH
        self.is_available = self._check_database()
        
        if self.is_available:
            logger.info(f"SQLiteSearchService initialized with database: {self.db_path}")
        else:
            logger.warning(f"SQLite database not available at {self.db_path} or missing required table. SQLite search functionality will be disabled.")

    def _check_database(self) -> bool:
        """
        Check if the database exists and has the required structure.
        Returns True if the database is available and usable, False otherwise.
        """
        if not os.path.exists(self.db_path):
            logger.warning(f"SQLite database not found at {self.db_path}")
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if case_lookup table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='case_lookup'")
            if not cursor.fetchone():
                logger.warning("Required table 'case_lookup' not found in SQLite database")
                return False
            
            # Get table schema to verify columns
            cursor.execute("PRAGMA table_info(case_lookup)")
            columns = {row[1] for row in cursor.fetchall()}
            
            # Verify essential columns exist
            required_columns = {"jurisdiction", "court", "date", "case_id"}
            missing_columns = required_columns - columns
            if missing_columns:
                logger.warning(f"Missing required columns in case_lookup table: {missing_columns}")
                return False
            
            logger.info("SQLite database verification successful")
            return True
            
        except Exception as e:
            logger.warning(f"Error checking SQLite database: {e}")
            return False
            
        finally:
            if 'conn' in locals():
                conn.close()

    def filter_cases(
        self,
        jurisdiction: Optional[str] = None,
        court: Optional[str | List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        case_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort: Optional[str] = None,
        query: Optional[str] = None  # Add support for basic text search
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filter cases based on metadata criteria without using vector search.
        Enhanced to handle date filtering more efficiently.
        
        Args:
            jurisdiction: Filter by jurisdiction
            court: Filter by court (single value or list)
            date_from: Filter by date (from)
            date_to: Filter by date (to)
            case_type: Filter by case type
            limit: Maximum number of results to return
            offset: Offset for pagination
            sort: Sort criteria (date_asc, date_desc, etc.)
            query: Optional simple text search term
            
        Returns:
            Tuple of (list of case dictionaries, total count)
        """
        # Check if SQLite is available
        if not self.is_available:
            logger.warning("SQLite search attempted but database is not available")
            return [], 0
        
        # Validate parameters
        limit = min(limit, MAX_RESULTS)
        if limit < 1:
            limit = 20
        if offset < 0:
            offset = 0
            
        # Build SQL query
        base_query = """
        SELECT 
            id, case_id, title, court, jurisdiction, 
            date, citations, original_cid, snippet
        FROM case_lookup
        """
        
        count_query = "SELECT COUNT(*) FROM case_lookup"
        
        # Build WHERE clause
        conditions = []
        params = []
        
        # Add basic text search if query is provided
        if query and query.strip():
            query_text = query.strip()
            conditions.append("(title LIKE ? OR snippet LIKE ?)")
            params.extend([f"%{query_text}%", f"%{query_text}%"])
        
        if jurisdiction and jurisdiction != "all":
            conditions.append("jurisdiction = ?")
            params.append(jurisdiction)
        
        if court:
            if isinstance(court, list):
                if len(court) == 1:
                    # Single court in a list
                    conditions.append("court = ?")
                    params.append(court[0])
                elif len(court) > 1:
                    # Multiple courts (OR condition)
                    placeholders = ", ".join(["?" for _ in court])
                    conditions.append(f"court IN ({placeholders})")
                    params.extend(court)
            else:
                # Single court as string
                conditions.append("court = ?")
                params.append(court)
        
        # Handle date filtering explicitly
        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)
        
        # Add basic case type filtering based on keywords in snippet
        if case_type and case_type != "all":
            # Simple approach - look for case type keywords in the snippet
            keywords = {
                "criminal": ["criminal", "defendant", "conviction", "jury", "guilty"],
                "civil": ["civil", "plaintiff", "contract", "tort", "liability"],
                "constitutional": ["constitutional", "amendment", "rights"],
                "administrative": ["administrative", "agency", "regulation"]
            }.get(case_type.lower(), [])
            
            if keywords:
                # Create OR conditions for each keyword
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append("snippet LIKE ?")
                    params.append(f"%{keyword}%")
                
                if keyword_conditions:
                    conditions.append(f"({' OR '.join(keyword_conditions)})")
        
        # Add WHERE clause if we have conditions
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
            base_query += " " + where_clause
            count_query += " " + where_clause
        
        # Add ORDER BY clause
        if sort:
            if sort == "date_desc":
                base_query += " ORDER BY date DESC"
            elif sort == "date_asc":
                base_query += " ORDER BY date ASC"
            # Add other sort options as needed
        else:
            # Default to date descending
            base_query += " ORDER BY date DESC"
        
        # Add LIMIT and OFFSET
        base_query += f" LIMIT {limit} OFFSET {offset}"
        
        # Execute queries
        try:
            start_time = time.time()
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            # Get total count first
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Execute main query if we have results
            results = []
            if total_count > 0:
                cursor.execute(base_query, params)
                results = [dict(row) for row in cursor.fetchall()]
            
            elapsed = time.time() - start_time
            logger.info(f"SQLite filter completed in {elapsed:.3f}s, found {total_count} results (date_from={date_from}, date_to={date_to})")
            
            return results, total_count
            
        except Exception as e:
            logger.error(f"Error executing SQLite filter query: {e}")
            return [], 0
            
        finally:
            if 'conn' in locals():
                conn.close()

    def format_results(self, sqlite_results: List[Dict[str, Any]]) -> List:
        """
        Format SQLite query results into SearchResult objects that match the format
        expected by the search API.
        
        Args:
            sqlite_results: List of result dictionaries from SQLite
            
        Returns:
            List of SearchResult objects
        """
        search_results = []
        
        for idx, result in enumerate(sqlite_results):
            # Calculate a fake score that decreases with index (1.0 to 0.8)
            # This is just for ordering since we don't have real relevance scores
            score = max(0.8, 1.0 - (idx * 0.01))
            
            # Extract snippet
            snippet = result.get("snippet", "")
            
            # Create metadata dictionary
            metadata = {
                "case_id": result.get("case_id", ""),
                "jurisdiction": result.get("jurisdiction", ""),
                "court": result.get("court", ""),
                "date": result.get("date", ""),
                "citation": result.get("citations", ""),  # Note: using 'citations' from DB
            }
            
            # Create SearchResult object
            search_result = {
                "id": result.get("id", ""),
                "score": score,
                "title": result.get("title", ""),
                "url": f"/case/{result.get('case_id')}" if result.get("case_id") else "",
                "text": snippet,
                "metadata": metadata,
                "is_summarized": False,
                "original_text": None,
            }
            
            search_results.append(search_result)
        
        return search_results


# Singleton instance for application-wide use
sqlite_search_service = SQLiteSearchService()