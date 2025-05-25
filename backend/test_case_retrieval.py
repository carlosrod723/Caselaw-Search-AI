# test_case_retrieval.py

"""
Test script to diagnose case retrieval issues between full text and PDF endpoints.
Run this script with a point_id to see if the same case is being retrieved in both cases.

Usage:
  python test_case_retrieval.py <point_id>

Example:
  python test_case_retrieval.py 42268aa5-8f91-5083-b458-72300351a2fb
"""

import sys
import os
import logging
from io import BytesIO

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Import our services - adjust these imports based on your project structure
sys.path.append('.')  # Add current directory to path
try:
    from app.services.qdrant_service import qdrant_service
    from app.services.case_document_service import case_document_service
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure to run this script from the root directory of your project")
    sys.exit(1)

def get_full_case_text(point_id):
    """Simulate the get_full_case_document endpoint logic"""
    logger.info(f"Testing full text retrieval for point_id: {point_id}")
    
    # Retrieve the document metadata from Qdrant
    results = qdrant_service.retrieve_points(
        ids=[point_id],
        with_payload=True
    )
    
    if not results:
        logger.error(f"Case with ID {point_id} not found")
        return None
    
    # Extract the data from the first result
    point = results[0]
    payload = point.payload or {}
    
    # Get the original_cid and case_id from payload
    original_cid = payload.get("original_cid", "")
    case_id = payload.get("case_id", "")
    
    logger.info(f"Full Text - Original CID: {original_cid}, Case ID: {case_id}")
    
    # Try to get the full case
    full_case = None
    
    # First try by CID if available
    if original_cid:
        logger.info(f"Full Text - Attempting to retrieve case by CID: {original_cid}")
        full_case = case_document_service.get_case_by_cid(original_cid, full_text=True)
    
    # Then try by case_id if CID didn't work
    if not full_case and case_id:
        logger.info(f"Full Text - Attempting to retrieve case by ID: {case_id}")
        full_case = case_document_service.get_case_by_id(case_id, full_text=True)
    
    # Determine what content to return
    content = ""
    is_full_content = False
    
    if full_case and "text" in full_case and full_case["text"]:
        logger.info(f"Full Text - Using full text content for case (length: {len(full_case['text'])})")
        content = full_case["text"]
        is_full_content = True
        
        # Extract and log the case name and first paragraph for comparison
        case_name = full_case.get("name_abbreviation", "Unknown Case")
        first_paragraph = content.split('\n')[0] if '\n' in content else content[:100]
        logger.info(f"Full Text - Case name: {case_name}")
        logger.info(f"Full Text - First paragraph preview: {first_paragraph[:100]}...")
        
        return {
            "case_id": case_id,
            "original_cid": original_cid,
            "title": case_name,
            "content": content,
            "first_paragraph": first_paragraph
        }
    else:
        logger.warning("No full case text found")
        return None

def get_pdf_case_text(point_id):
    """Simulate the get_case_pdf endpoint logic"""
    logger.info(f"Testing PDF generation for point_id: {point_id}")
    
    # Retrieve the document metadata from Qdrant
    results = qdrant_service.retrieve_points(
        ids=[point_id],
        with_payload=True
    )
    
    if not results:
        logger.error(f"Case with ID {point_id} not found")
        return None
    
    # Extract the data from the first result
    point = results[0]
    payload = point.payload or {}
    
    # Get identifiers for the case
    original_cid = payload.get("original_cid", "")
    case_id = payload.get("case_id", "")
    
    logger.info(f"PDF - Original CID: {original_cid}, Case ID: {case_id}")
    
    # Try to get the full case
    full_case = None
    
    # First try by CID if available
    if original_cid:
        logger.info(f"PDF - Attempting to retrieve case by CID: {original_cid}")
        full_case = case_document_service.get_case_by_cid(original_cid, full_text=True)
    
    # Then try by case_id if CID didn't work
    if not full_case and case_id:
        logger.info(f"PDF - Attempting to retrieve case by ID: {case_id}")
        full_case = case_document_service.get_case_by_id(case_id, full_text=True)
    
    # Determine what text to include
    if full_case and "text" in full_case and full_case["text"]:
        text = full_case["text"]
        is_full_content = True
        
        # Use metadata from the full case if available
        title = full_case.get("name_abbreviation", payload.get("title", "Untitled Case"))
        
        # Extract and log the case name and first paragraph for comparison
        first_paragraph = text.split('\n')[0] if '\n' in text else text[:100]
        logger.info(f"PDF - Case name: {title}")
        logger.info(f"PDF - First paragraph preview: {first_paragraph[:100]}...")
        
        return {
            "case_id": case_id,
            "original_cid": original_cid,
            "title": title,
            "content": text,
            "first_paragraph": first_paragraph
        }
    else:
        logger.warning("No full case text found for PDF")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_case_retrieval.py <point_id>")
        sys.exit(1)
    
    point_id = sys.argv[1]
    logger.info(f"Testing case retrieval for point_id: {point_id}")
    
    # Get full text case data
    full_text_case = get_full_case_text(point_id)
    
    # Get PDF case data
    pdf_case = get_pdf_case_text(point_id)
    
    # Compare results
    if full_text_case and pdf_case:
        logger.info("\n===== COMPARISON RESULTS =====")
        logger.info(f"Full Text Title: {full_text_case['title']}")
        logger.info(f"PDF Title: {pdf_case['title']}")
        
        title_match = full_text_case['title'] == pdf_case['title']
        logger.info(f"Title Match: {'YES' if title_match else 'NO'}")
        
        # Check if the first 100 characters of content match
        content_preview_match = full_text_case['first_paragraph'][:100] == pdf_case['first_paragraph'][:100]
        logger.info(f"Content Preview Match: {'YES' if content_preview_match else 'NO'}")
        
        # Detailed comparison if no match
        if not content_preview_match:
            logger.info("\n===== CONTENT COMPARISON =====")
            logger.info(f"Full Text First 100 chars: {full_text_case['first_paragraph'][:100]}")
            logger.info(f"PDF First 100 chars: {pdf_case['first_paragraph'][:100]}")
    else:
        logger.error("Could not retrieve both full text and PDF case data")

if __name__ == "__main__":
    main()

# Test with python test_case_retrieval.py 42268aa5-8f91-5083-b458-72300351a2fb