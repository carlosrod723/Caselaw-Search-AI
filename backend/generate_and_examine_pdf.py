#!/usr/bin/env python
"""
Test script to diagnose PDF generation issues.
This script retrieves case data and generates a PDF, then extracts and examines the PDF content.

Usage:
  python generate_and_examine_pdf.py <point_id>

Example:
  python generate_and_examine_pdf.py 183887a2-35d7-5532-b52f-361c6f455185
"""

import sys
import os
import logging
from io import BytesIO
import re
import subprocess
import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Import our services - adjust these imports based on your project structure
sys.path.append('.')  # Add current directory to path
try:
    from app.services.qdrant_service import qdrant_service
    from app.services.case_document_service import case_document_service
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure to run this script from the root directory of your project")
    sys.exit(1)

def get_case_data(point_id):
    """Retrieve case data from Qdrant and case document service"""
    logger.info(f"Retrieving case data for point_id: {point_id}")
    
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
    
    logger.info(f"Original CID: {original_cid}, Case ID: {case_id}")
    
    # Try to get the full case
    full_case = None
    
    # First try by CID if available
    if original_cid:
        logger.info(f"Attempting to retrieve case by CID: {original_cid}")
        full_case = case_document_service.get_case_by_cid(original_cid, full_text=True)
    
    # Then try by case_id if CID didn't work
    if not full_case and case_id:
        logger.info(f"Attempting to retrieve case by ID: {case_id}")
        full_case = case_document_service.get_case_by_id(case_id, full_text=True)
    
    if full_case and "text" in full_case and full_case["text"]:
        logger.info(f"Using full text content for case (length: {len(full_case['text'])})")
        text = full_case["text"]
        
        # Use metadata from the full case if available
        title = full_case.get("name_abbreviation", payload.get("title", "Untitled Case"))
        court = full_case.get("court", payload.get("court", "Unknown"))
        date = full_case.get("decision_date", payload.get("date", "Unknown"))
        citation = full_case.get("citations", payload.get("citations", "Unknown"))
        jurisdiction = full_case.get("jurisdiction", payload.get("jurisdiction", ""))
        judges = full_case.get("judges", payload.get("judges", ""))
        
        return {
            "case_id": case_id,
            "original_cid": original_cid,
            "title": title,
            "court": court,
            "date": date,
            "citation": citation,
            "jurisdiction": jurisdiction,
            "judges": judges,
            "text": text,
            "first_paragraph": text.split('\n')[0] if '\n' in text else text[:100]
        }
    else:
        logger.warning("No full case text found")
        return None

def generate_pdf(case_data, output_path):
    """Generate a PDF using the same logic as the endpoint"""
    logger.info(f"Generating PDF for case: {case_data['title']}")
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Add custom styles
    styles.add(ParagraphStyle(
        name='CaseTitle',
        parent=styles['Title'],
        fontSize=16,
        spaceAfter=12
    ))
    
    styles.add(ParagraphStyle(
        name='CaseHeading', 
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=10
    ))
    
    styles.add(ParagraphStyle(
        name='CaseNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='CaseItalic',
        parent=styles['Italic'],
        fontSize=10,
        leading=14
    ))
    
    # Create a list of elements to build the PDF
    elements = []
    
    # Try to add logo
    base_dir = os.getcwd()  # Current directory
    logo_path = os.path.join(base_dir, "images", "praxis_logo.png")
    logger.info(f"Looking for logo at: {logo_path}")
    try:
        if os.path.exists(logo_path):
            # Use fixed width and height
            logo = Image(logo_path, width=100, height=80)
            elements.append(logo)
            elements.append(Spacer(1, 12))
        else:
            logger.warning(f"Logo file not found at {logo_path}")
    except Exception as e:
        logger.warning(f"Could not load logo: {e}")
    
    # Add title
    elements.append(Paragraph(case_data['title'], styles['CaseTitle']))
    
    # Add metadata section
    elements.append(Paragraph("Case Information", styles['CaseHeading']))
    
    # Format metadata
    metadata = [
        ["Court:", case_data['court']],
        ["Date:", case_data['date']],
        ["Citation:", case_data['citation']]
    ]
    
    # Add jurisdiction if available
    if case_data['jurisdiction']:
        metadata.append(["Jurisdiction:", case_data['jurisdiction']])
    
    # Add Judge if available
    if case_data['judges']:
        metadata.append(["Judge:", case_data['judges']])
    
    # Create a table for metadata
    table_style = TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])
    
    metadata_table = Table(metadata, colWidths=[100, 400])
    metadata_table.setStyle(table_style)
    elements.append(metadata_table)
    elements.append(Spacer(1, 12))
    
    # Add content section
    elements.append(Paragraph("Case Text", styles['CaseHeading']))
    
    # Handle the text content - prevent PDF generation issues with invalid characters
    def clean_text_for_pdf(text):
        """Clean text to make it safe for PDF generation"""
        if not text:
            return ""
        
        # Replace problematic characters
        text = text.replace('\u2028', ' ')  # Line separator
        text = text.replace('\u2029', '\n')  # Paragraph separator
        text = text.replace('\u0000', '')    # Null character
        
        # Replace XML/HTML-like tags that might cause parsing issues
        text = re.sub(r'<[^>]*>', '', text)  # Remove anything that looks like HTML/XML tags
        
        # Replace any other potentially problematic characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        return text
    
    text = clean_text_for_pdf(case_data['text'])
    
    # Split text into paragraphs
    paragraphs = text.split('\n')
    for i, para in enumerate(paragraphs):
        if para.strip():  # Skip empty paragraphs
            try:
                # Ensure the paragraph is safely formatted for ReportLab
                safe_para = para.strip()
                elements.append(Paragraph(safe_para, styles['CaseNormal']))
                
                # Don't add spacer after the last paragraph
                if i < len(paragraphs) - 1:
                    elements.append(Spacer(1, 6))
            except Exception as e:
                logger.error(f"Error adding paragraph to PDF: {e}")
                # Add a placeholder for problematic paragraphs
                elements.append(Paragraph("[Content omitted due to formatting issues]", styles['CaseItalic']))
                # Continue with the next paragraph instead of failing the whole document
                continue
    
    # Build the PDF with stronger error handling
    try:
        doc.build(elements)
        logger.info(f"PDF successfully built and saved to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Fatal error building PDF: {str(e)}")
        return False

def extract_pdf_text(pdf_path):
    """Extract text from a PDF file using pdftotext if available, otherwise return first page info"""
    logger.info(f"Extracting text from PDF: {pdf_path}")
    
    try:
        # Try using pdftotext command (from poppler-utils)
        text = subprocess.check_output(['pdftotext', pdf_path, '-'], stderr=subprocess.PIPE).decode('utf-8')
        return text
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("pdftotext not available. Install poppler-utils for better PDF text extraction.")
        
        try:
            # Alternative: use less/head to check first page (works on Unix-like systems)
            first_page = subprocess.check_output(f"strings '{pdf_path}' | head -20", shell=True).decode('utf-8', errors='ignore')
            return f"First page preview:\n{first_page}"
        except:
            return "Could not extract PDF text. Install poppler-utils for better results."

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_and_examine_pdf.py <point_id>")
        sys.exit(1)
    
    point_id = sys.argv[1]
    logger.info(f"Testing PDF generation for point_id: {point_id}")
    
    # Get case data
    case_data = get_case_data(point_id)
    if not case_data:
        logger.error("Failed to retrieve case data")
        sys.exit(1)
    
    # Create temp PDF file
    pdf_path = os.path.join(os.getcwd(), f"test_case_{point_id}.pdf")
    logger.info(f"Will generate PDF at: {pdf_path}")
    
    # Generate PDF
    success = generate_pdf(case_data, pdf_path)
    if not success:
        logger.error("Failed to generate PDF")
        sys.exit(1)
    
    # Extract and check PDF text
    pdf_text = extract_pdf_text(pdf_path)
    
    logger.info("\n===== VERIFICATION RESULTS =====")
    logger.info(f"Case Title: {case_data['title']}")
    
    # Check if title appears in PDF
    title_in_pdf = case_data['title'] in pdf_text
    logger.info(f"Title appears in PDF: {'YES' if title_in_pdf else 'NO'}")
    
    # Print PDF preview
    logger.info("\n===== PDF TEXT PREVIEW =====")
    preview_length = min(500, len(pdf_text))
    logger.info(pdf_text[:preview_length] + "...")
    
    # Print path for manual inspection
    logger.info(f"\nPDF saved at: {pdf_path}")
    logger.info(f"You can open this PDF to verify its contents.")

if __name__ == "__main__":
    main()