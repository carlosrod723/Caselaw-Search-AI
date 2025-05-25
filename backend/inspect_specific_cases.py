#!/usr/bin/env python
"""
Verify specific case ID resolution through both databases
"""
import os
import sys
import logging
import sqlite3
from app.services.case_document_service import case_document_service
from app.services.qdrant_service import qdrant_service

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Specific values to check
CASE_IDS_TO_CHECK = ["1424653"]  # The problematic case ID we found
SQLITE_DB_PATH = "/Users/josecarlosrodriguez/Desktop/Carlos-Projects/Qdrant-Test/case_lookup.db"

def verify_case_mapping():
    """Check how specific case IDs map in both databases"""
    
    # First check SQLite database
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    for case_id in CASE_IDS_TO_CHECK:
        logger.info(f"Checking case ID: {case_id}")
        
        # 1. Check SQLite
        logger.info("SQLite lookup:")
        cursor.execute("SELECT id, name_abbreviation, court, jurisdiction, decision_date FROM cases WHERE id = ?", (case_id,))
        result = cursor.fetchone()
        
        if result:
            logger.info(f"  ID: {result[0]}")
            logger.info(f"  Title: {result[1]}")
            logger.info(f"  Court: {result[2]}")
            logger.info(f"  Jurisdiction: {result[3]}")
            logger.info(f"  Date: {result[4]}")
        else:
            logger.info("  Not found in SQLite")
        
        # 2. Check via full text retrieval service
        logger.info("Case document service lookup:")
        case_data = case_document_service.get_case_by_id(case_id, full_text=False)
        
        if case_data:
            logger.info(f"  Title: {case_data.get('name_abbreviation', 'N/A')}")
            logger.info(f"  Court: {case_data.get('court', 'N/A')}")
            logger.info(f"  Date: {case_data.get('decision_date', 'N/A')}")
        else:
            logger.info("  Not found via case document service")
        
        # 3. Try to find this case in Qdrant by case_id in payload
        logger.info("Qdrant search by case_id:")
        try:
            # Search for this case_id in Qdrant
            results = qdrant_service.search_by_vector(
                vector=[0.1] * 768,  # Random vector
                filter_conditions={"case_id": case_id},
                limit=5
            )
            
            logger.info(f"  Found {len(results)} results with case_id={case_id}")
            
            for i, point in enumerate(results):
                logger.info(f"  Result {i+1}:")
                logger.info(f"    Point ID: {point.id}")
                
                if hasattr(point, 'payload') and point.payload:
                    payload = point.payload
                    logger.info(f"    Title: {payload.get('title', 'N/A')}")
                    logger.info(f"    Court: {payload.get('court', 'N/A')}")
                    logger.info(f"    Date: {payload.get('date', 'N/A')}")
        except Exception as e:
            logger.error(f"  Error searching Qdrant: {e}")
        
        logger.info("-" * 50)

if __name__ == "__main__":
    verify_case_mapping()