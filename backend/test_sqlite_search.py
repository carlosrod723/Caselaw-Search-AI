#!/usr/bin/env python
"""
Test script to diagnose inconsistencies between search results and case content.
This script retrieves a case by ID and then checks the actual content.

Usage:
  python test_sqlite_search.py <case_id>

Example:
  python test_sqlite_search.py 12519362
"""

import sys
import os
import logging
import json
import sqlite3

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Import our services - adjust these imports based on your project structure
sys.path.append('.')  # Add current directory to path
try:
    from app.services.case_document_service import case_document_service
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure to run this script from the root directory of your project")
    sys.exit(1)

def check_case_by_id(case_id):
    """Check the content of a case by its ID"""
    logger.info(f"Checking case with ID: {case_id}")
    
    # Connect to SQLite database
    db_path = os.path.join(os.getcwd(), "case_lookup.db")
    logger.info(f"Using SQLite database at: {db_path}")
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return
    
    try:
        # Get basic case metadata from SQLite
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query case metadata
        cursor.execute("""
            SELECT id, file_name, court, jurisdiction, decision_date, name_abbreviation
            FROM cases 
            WHERE id = ?
        """, (case_id,))
        
        result = cursor.fetchone()
        
        if not result:
            logger.error(f"Case with ID {case_id} not found in SQLite database")
            return
        
        # Extract case metadata from the database
        db_id, file_name, court, jurisdiction, decision_date, name_abbreviation = result
        
        logger.info(f"SQLite database record:")
        logger.info(f"ID: {db_id}")
        logger.info(f"Title: {name_abbreviation}")
        logger.info(f"Court: {court}")
        logger.info(f"Jurisdiction: {jurisdiction}")
        logger.info(f"Date: {decision_date}")
        logger.info(f"File name: {file_name}")
        
        # Now get the full case using the case document service
        full_case = case_document_service.get_case_by_id(case_id, full_text=True)
        
        if not full_case:
            logger.error(f"Failed to retrieve full case from document service")
            return
        
        # Check case content
        actual_title = full_case.get("name_abbreviation", "Unknown")
        actual_court = full_case.get("court", "Unknown")
        actual_text = full_case.get("text", "")
        
        logger.info(f"\nFull case content metadata:")
        logger.info(f"Title: {actual_title}")
        logger.info(f"Court: {actual_court}")
        
        # Show first 200 characters of text
        if actual_text:
            first_line = actual_text.split('\n')[0] if '\n' in actual_text else actual_text[:200]
            logger.info(f"Text preview: {first_line[:200]}...")
        
        # Check for inconsistencies
        if name_abbreviation != actual_title:
            logger.warning(f"MISMATCH: SQLite title '{name_abbreviation}' doesn't match document title '{actual_title}'")
        
        if court != actual_court:
            logger.warning(f"MISMATCH: SQLite court '{court}' doesn't match document court '{actual_court}'")
        
        # Save details to file for further analysis
        with open(f"case_check_{case_id}.json", "w") as f:
            json.dump({
                "sqlite_record": {
                    "id": db_id,
                    "file_name": file_name,
                    "title": name_abbreviation,
                    "court": court,
                    "jurisdiction": jurisdiction,
                    "date": decision_date
                },
                "full_case_content": {
                    "title": actual_title,
                    "court": actual_court,
                    "text_preview": actual_text[:500] if actual_text else ""
                }
            }, f, indent=2)
        
        logger.info(f"Details saved to case_check_{case_id}.json")
        
    except Exception as e:
        logger.error(f"Error checking case: {str(e)}")
    finally:
        conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_sqlite_search.py <case_id>")
        sys.exit(1)
    
    case_id = sys.argv[1]
    check_case_by_id(case_id)

if __name__ == "__main__":
    main()