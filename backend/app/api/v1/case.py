# app/api/v1/case.py
import logging
import os
import re
import sqlite3
import asyncio
import re
from fastapi import APIRouter, HTTPException, Path, Response, Depends, Query
from typing import Dict, Any, Optional
from io import BytesIO

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, 
    Paragraph, 
    Spacer, 
    Table, 
    TableStyle,
    Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Application services
from app.services.openai_service import openai_service
from app.services.case_document_service import case_document_service
from app.services.qdrant_service import qdrant_service

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/case", tags=["case"])

def find_case_by_metadata(title, court=None, date=None, jurisdiction=None, db_path=None):
    """
    Find a case ID by matching multiple metadata fields.
    Prioritizes exact title matches over fuzzy matching.
    
    Args:
        title: The case title/name abbreviation
        court: The court name
        date: The decision date (YYYY-MM-DD format)
        jurisdiction: The jurisdiction
        db_path: Path to the SQLite database
        
    Returns:
        Tuple of (case_id, name_abbreviation) or None if no match found
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First priority: exact title and metadata match
        query = "SELECT id, name_abbreviation FROM cases WHERE name_abbreviation = ?"
        params = [title]
        
        # Add additional conditions if provided
        if court:
            query += " AND court = ?"
            params.append(court)
        if date:
            query += " AND decision_date = ?"
            params.append(date)
        if jurisdiction:
            query += " AND jurisdiction = ?"
            params.append(jurisdiction)
            
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Found exact match for {title} with all provided metadata")
            return result
        
        # Second priority: exact title match
        cursor.execute(
            "SELECT id, name_abbreviation FROM cases WHERE name_abbreviation = ? LIMIT 1",
            (title,)
        )
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Found exact title match for {title}")
            return result
        
        # Third priority: exact title match with any one piece of metadata
        if court or date or jurisdiction:
            query_parts = []
            params = []
            
            if court:
                query_parts.append("(name_abbreviation = ? AND court = ?)")
                params.extend([title, court])
            
            if date:
                query_parts.append("(name_abbreviation = ? AND decision_date = ?)")
                params.extend([title, date])
                
            if jurisdiction:
                query_parts.append("(name_abbreviation = ? AND jurisdiction = ?)")
                params.extend([title, jurisdiction])
                
            if query_parts:
                query = f"SELECT id, name_abbreviation FROM cases WHERE {' OR '.join(query_parts)} LIMIT 1"
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"Found match for {title} with partial metadata")
                    return result
        
        # Last resort: case ID lookup (if title looks like it might be an ID)
        if title.isdigit():
            cursor.execute("SELECT id, name_abbreviation FROM cases WHERE id = ? LIMIT 1", (title,))
            result = cursor.fetchone()
            if result:
                logger.info(f"Found case by ID: {title}")
                return result
        
        # If we got here, we couldn't find a good match
        logger.warning(f"No suitable case found matching title: {title}")
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"Error finding case by metadata: {e}")
        return None

@router.get("/{point_id}/full", response_model=Dict[str, Any])
async def get_full_case_document(
    point_id: str = Path(..., description="The ID of the case"),
    title: Optional[str] = Query(None, description="Case title for verification")
):
    """Get the full document content for a case."""
    try:
        # Check if point_id is a numeric case ID (from SQLite) rather than a Qdrant vector ID
        if point_id.isdigit():
            logger.info(f"Retrieving full case directly by SQLite case ID: {point_id}")
            full_case = case_document_service.get_case_by_id(point_id, full_text=True)
            
            if not full_case:
                raise HTTPException(status_code=404, detail=f"Case with ID {point_id} not found")
            
            # Verify title if provided
            if title and full_case:
                case_title = full_case.get("name_abbreviation", "")
                if title.strip() != case_title.strip():
                    logger.warning(f"Title mismatch! Requested: '{title}', Found: '{case_title}'")
                    
                    # Try to find the correct case by title
                    db_path = case_document_service.sqlite_db_path
                    correct_case = find_case_by_metadata(title, db_path=db_path)
                    
                    if correct_case:
                        correct_id, correct_title = correct_case
                        logger.info(f"Found correct case with ID {correct_id}: '{correct_title}'")
                        
                        # Fetch the correct case
                        full_case = case_document_service.get_case_by_id(correct_id, full_text=True)
                        if full_case:
                            logger.info(f"Successfully retrieved correct case by title match")
            
            # Construct a response using the available data
            content = full_case.get("text", "")
            is_full_content = True
            
            # Base case data
            case_data = {
                "case_id": full_case.get("id", point_id),
                "title": full_case.get("name_abbreviation", ""),
                "court": full_case.get("court", ""),
                "date": full_case.get("decision_date", ""),
                "jurisdiction": full_case.get("jurisdiction", ""),
                "citation": full_case.get("citations", ""),
                "content": content,
                "is_full_content": is_full_content,
                "judges": full_case.get("judges", ""),
                "original_cid": full_case.get("cid", ""),
                "summary": "", 
                "keyPassages": []
            }
            
            # If we have full content, generate AI summary and extract key passages
            if is_full_content and content:
                try:
                    summarizable_content = content[:8000]
                    logger.info(f"Generating AI summary for case: {case_data['title']}")
                    
                    summary_prompt = (
                        "Create a concise legal syllabus for this case, structured with the following clear sections:\n\n"
                        "1. Key Legal Issue: Identify the central legal question(s) addressed by the court (1-2 sentences).\n\n"
                        "2. Holding: State the court's conclusion/ruling on each key issue (1-2 sentences).\n\n"
                        "3. Reasoning: Explain the court's rationale for its decision (3-5 sentences).\n\n"
                        "Format the response with section headers as demonstrated below:\n"
                        "**Key Legal Issue:** [your analysis here in complete sentences]\n\n"
                        "**Holding:** [your analysis here in complete sentences]\n\n"
                        "**Reasoning:** [your analysis here in complete sentences]\n\n"
                        "Keep the entire response between 200-300 words, ensuring all sections are fully readable with no cut-off sentences."
                    )
                    
                    passages_prompt = (
                        "Extract 1-2 key passages (direct quotes) from this legal opinion that represent the most "
                        "important holdings or statements of legal reasoning. Each passage must:\n\n"
                        "1. Be an exact quote from the text (100-500 characters long)\n"
                        "2. Contain complete sentences with proper punctuation\n"
                        "3. Represent core legal principles or critical holdings\n\n"
                        "Format each passage in quotation marks. Return only substantive legal quotes, not single words "
                        "or short phrases. If you cannot find suitable full-sentence quotes, respond with 'No suitable passages found.'"
                    )
                    
                    # Generate AI summary only - key passages will be extracted client-side
                    summary_result = await openai_service.async_chat_client.chat.completions.create(
                        model="gpt-4o-mini",  # Use specific model name
                        messages=[
                            {"role": "system", "content": summary_prompt},
                            {"role": "user", "content": summarizable_content}
                        ],
                        max_tokens=500,
                        temperature=0.1,
                    )
                    
                    # Extract the generated summary
                    ai_summary = summary_result.choices[0].message.content.strip()
                    
                    # Log success
                    logger.info(f"Successfully generated AI summary")

                    # Update case data with AI content
                    case_data["summary"] = ai_summary
                    case_data["keyPassages"] = []  # Empty array - passages will be extracted client-side
                    
                except Exception as e:
                    # Log the error but continue with default content
                    logger.error(f"Error generating AI content: {str(e)}")
                    # Default to first 500 chars as summary
                    case_data["summary"] = content[:500] + "..." if len(content) > 500 else content
            
            return case_data
        
        # Original code for Qdrant vector IDs
        results = qdrant_service.retrieve_points(
            ids=[point_id],
            with_payload=True
        )
        
        if not results:
            raise HTTPException(status_code=404, detail=f"Case with ID {point_id} not found")
        
        # Extract the data from the first result
        point = results[0]
        payload = point.payload or {}
        
        # Get the original_cid and case_id from payload
        original_cid = payload.get("original_cid", "")
        case_id = payload.get("case_id", "")
        payload_title = payload.get("title", "")
        
        logger.info(f"Retrieving full case for point_id: {point_id}")
        logger.info(f"Original CID: {original_cid}, Case ID: {case_id}, Title: {payload_title}")
        
        # Try to get the full case
        full_case = None
        
        # If title is provided and differs from payload title, prioritize title search
        if title and title != payload_title:
            logger.info(f"Title provided in request ({title}) differs from payload title ({payload_title})")
            db_path = case_document_service.sqlite_db_path
            correct_case = find_case_by_metadata(title, db_path=db_path)
            
            if correct_case:
                correct_id, correct_title = correct_case
                logger.info(f"Found case by title with ID {correct_id}: '{correct_title}'")
                full_case = case_document_service.get_case_by_id(correct_id, full_text=True)
        
        # If title search didn't work, try standard methods
        if not full_case:
            # First try by CID if available
            if original_cid:
                logger.info(f"Attempting to retrieve case by CID: {original_cid}")
                full_case = case_document_service.get_case_by_cid(original_cid, full_text=True)
            
            # Then try by case_id if CID didn't work
            if not full_case and case_id:
                logger.info(f"Attempting to retrieve case by ID: {case_id}")
                full_case = case_document_service.get_case_by_id(case_id, full_text=True)
        
        # Determine what content to return
        content = ""
        is_full_content = False
        
        if full_case and "text" in full_case and full_case["text"]:
            logger.info(f"Using full text content for case (length: {len(full_case['text'])})")
            content = full_case["text"]
            is_full_content = True
        else:
            # Fall back to the snippet from Qdrant
            logger.warning(f"Full case not found, using snippet (length: {len(payload.get('snippet', ''))})")
            content = payload.get("snippet", "")
        
        # Verify that the case title matches the requested title (if provided)
        if title and full_case and title != full_case.get("name_abbreviation", ""):
            logger.warning(f"Title mismatch in full case retrieval: requested '{title}', found '{full_case.get('name_abbreviation', '')}'")
        
        # Create base case data
        case_data = {
            "case_id": full_case.get("id", payload.get("case_id", "")),
            "title": full_case.get("name_abbreviation", payload.get("title", "")),
            "court": full_case.get("court", payload.get("court", "")),
            "date": full_case.get("decision_date", payload.get("date", "")),
            "jurisdiction": full_case.get("jurisdiction", payload.get("jurisdiction", "")),
            "citation": full_case.get("citations", payload.get("citations", "")),
            "content": content,
            "is_full_content": is_full_content,
            "judges": full_case.get("judges", payload.get("judges", "")),
            "original_cid": full_case.get("cid", original_cid),
            "summary": payload.get("snippet", ""),
            "keyPassages": payload.get("keyPassages", [])
        }
        
        # If we have full content, use AI to generate a proper summary and extract key passages
        if is_full_content and content:
            try:
                # Prepare a shorter version of the content for OpenAI
                summarizable_content = content[:8000]
                
                # Generate AI summary for the Syllabus
                logger.info(f"Generating AI summary for case: {case_data['title']}")
                
                # Define prompts
                summary_prompt = (
                    "Create a concise legal syllabus for this case, structured with the following clear sections:\n\n"
                    "1. Key Legal Issue: Identify the central legal question(s) addressed by the court (1-2 sentences).\n\n"
                    "2. Holding: State the court's conclusion/ruling on each key issue (1-2 sentences).\n\n"
                    "3. Reasoning: Explain the court's rationale for its decision (3-5 sentences).\n\n"
                    "Format the response with section headers as demonstrated below:\n"
                    "**Key Legal Issue:** [your analysis here in complete sentences]\n\n"
                    "**Holding:** [your analysis here in complete sentences]\n\n"
                    "**Reasoning:** [your analysis here in complete sentences]\n\n"
                    "Keep the entire response between 200-300 words, ensuring all sections are fully readable with no cut-off sentences."
                )
                
                passages_prompt = (
                    "Extract 1-2 key passages (direct quotes) from this legal opinion that represent the most "
                    "important holdings or statements of legal reasoning. Each passage must:\n\n"
                    "1. Be an exact quote from the text (100-500 characters long)\n"
                    "2. Contain complete sentences with proper punctuation\n"
                    "3. Represent core legal principles or critical holdings\n\n"
                    "Format each passage in quotation marks. Return only substantive legal quotes, not single words "
                    "or short phrases. If you cannot find suitable full-sentence quotes, respond with 'No suitable passages found.'"
                )
                
                # Generate AI summary only - key passages will be extracted client-side
                summary_result = await openai_service.async_chat_client.chat.completions.create(
                    model="gpt-4o-mini",  # Use specific model name
                    messages=[
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": summarizable_content}
                    ],
                    max_tokens=500,
                    temperature=0.1,
                )

                # Extract the generated summary
                ai_summary = summary_result.choices[0].message.content.strip()

                # Log success
                logger.info(f"Successfully generated AI summary")

                # Update case data with AI content
                case_data["summary"] = ai_summary
                case_data["keyPassages"] = []
                
            except Exception as e:
                # Log the error but continue with the standard content
                logger.error(f"Error generating AI content: {str(e)}")
        
        return case_data
    except Exception as e:
        logger.error(f"Error retrieving case: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Error retrieving case: {str(e)}")

@router.get("/{point_id}/pdf", response_class=Response)
async def get_case_pdf(
    point_id: str = Path(..., description="The ID of the case"),
    download: bool = False,
    title: Optional[str] = Query(None, description="Case title for verification"),
    court: Optional[str] = Query(None, description="Court for verification"),
    date: Optional[str] = Query(None, description="Decision date for verification"),
    jurisdiction: Optional[str] = Query(None, description="Jurisdiction for verification")
):
    """Generate a PDF of the case document."""
    try:
        # Log the PDF request with metadata for debugging
        logger.info(f"PDF request: ID={point_id}, title='{title}', court='{court}', date='{date}', jurisdiction='{jurisdiction}'")
        
        # STEP 1: Prioritize ID-based lookup first
        case_data = None
        if point_id.isdigit():
            logger.info(f"Retrieving case for PDF directly by SQLite case ID: {point_id}")
            case_data = case_document_service.get_case_by_id(point_id, full_text=True)
            
            # Verify title match if we found a case by ID and title was provided
            if case_data and title and title.strip():
                case_title = case_data.get("name_abbreviation", "")
                if title.strip() != case_title.strip():
                    logger.warning(f"Title mismatch in ID lookup! Requested: '{title}', Found: '{case_title}'")
                    # Continue with this case anyway, but log the mismatch
                    # Only do title-based lookup if explicitly requested
                    if court and date and "exactMatch" in (jurisdiction or ""):
                        logger.info("Exact match requested, trying metadata-based lookup")
                        # Clear case_data to trigger metadata-based lookup
                        case_data = None
        
        # STEP 2: If ID lookup failed or was skipped, try metadata-based lookup
        if not case_data and title:
            logger.info(f"Trying metadata-based lookup for title: '{title}'")
            db_path = case_document_service.sqlite_db_path
            
            # Try exact match first
            exact_query = "SELECT id, name_abbreviation FROM cases WHERE name_abbreviation = ?"
            exact_params = [title]
            
            # Add additional conditions if provided
            if court:
                exact_query += " AND court = ?"
                exact_params.append(court)
            if date:
                exact_query += " AND decision_date = ?"
                exact_params.append(date)
            if jurisdiction and jurisdiction != "exactMatch":
                exact_query += " AND jurisdiction = ?"
                exact_params.append(jurisdiction)
                
            # Execute exact match query
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(exact_query, exact_params)
                exact_match = cursor.fetchone()
                conn.close()
                
                if exact_match:
                    exact_id, exact_title = exact_match
                    logger.info(f"Found exact match for title '{title}' with ID {exact_id}")
                    case_data = case_document_service.get_case_by_id(exact_id, full_text=True)
                    if case_data:
                        logger.info(f"Successfully retrieved case by exact metadata match")
            except Exception as e:
                logger.error(f"Error during exact match lookup: {e}")
        
        # STEP 3: If both lookups failed, try Qdrant vector ID lookup
        if not case_data and not point_id.isdigit():
            # For non-numeric IDs, retrieve from Qdrant first
            logger.info(f"Retrieving Qdrant data for vector ID: {point_id}")
            results = qdrant_service.retrieve_points(
                ids=[point_id],
                with_payload=True
            )
            
            if results:
                # Extract the data from the first result
                point = results[0]
                payload = point.payload or {}
                
                # Get case ID from payload and use that for lookup
                case_id = payload.get("case_id", "")
                if case_id:
                    logger.info(f"Found case_id in Qdrant payload: {case_id}, using for PDF lookup")
                    case_data = case_document_service.get_case_by_id(case_id, full_text=True)
                    
                    # Verify title match if title was provided
                    if case_data and title:
                        case_title = case_data.get("name_abbreviation", "")
                        if title.strip() != case_title.strip():
                            logger.warning(f"Title mismatch in Qdrant lookup! Requested: '{title}', Found: '{case_title}'")
                    
                # If case_id lookup fails, try CID lookup
                if not case_data:
                    original_cid = payload.get("original_cid", "")
                    if original_cid:
                        logger.info(f"Attempting CID lookup with: {original_cid}")
                        case_data = case_document_service.get_case_by_cid(original_cid, full_text=True)
        
        # If we couldn't get case data, return 404
        if not case_data:
            logger.error(f"Could not retrieve case data for PDF generation: {point_id}")
            raise HTTPException(status_code=404, detail=f"Case with ID {point_id} not found")
            
        # Extract text and metadata from the case data
        text = case_data.get("text", "")
        
        # Use metadata from the case data
        case_title = case_data.get("name_abbreviation", "Untitled Case")
        court = case_data.get("court", "Unknown")
        date = case_data.get("decision_date", "Unknown")
        citation = case_data.get("citations", "Unknown")
        jurisdiction = case_data.get("jurisdiction", "")
        judges = case_data.get("judges", "")
        case_id = case_data.get("id", point_id)
        is_full_content = True
        
        # Log successful case retrieval
        logger.info(f"Successfully retrieved case for PDF: {case_title}, {court}, {date}")
                
        # Rest of PDF generation code remains the same...
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Add custom styles with UNIQUE names to avoid conflicts
        styles.add(ParagraphStyle(
            name='CaseTitle',
            parent=styles['Title'],
            fontSize=16,
            spaceAfter=12
        ))
        
        # Use a different name for heading style
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
        
        # Add the Praxis logo at the top of the document
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
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
        
        # Add title with proper styling
        elements.append(Paragraph(case_title, styles['CaseTitle']))
        
        # Add metadata section - use CaseHeading instead of Heading1
        elements.append(Paragraph("Case Information", styles['CaseHeading']))
        
        # Format metadata
        metadata = [
            ["Court:", court],
            ["Date:", date],
            ["Citation:", citation]
        ]
        
        # Add jurisdiction if available
        if jurisdiction:
            metadata.append(["Jurisdiction:", jurisdiction])
        
        # Add Judge if available
        if judges:
            metadata.append(["Judge:", judges])
        
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
        
        # Add content section - use CaseHeading instead of Heading1
        elements.append(Paragraph("Case Text", styles['CaseHeading']))
        
        # Add note about content if it's just a snippet
        if not is_full_content:
            elements.append(Paragraph("Note: This is a snippet of the case text, not the full document.", 
                                    styles['CaseItalic']))
            elements.append(Spacer(1, 6))
        
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
        
        text = clean_text_for_pdf(text)
        
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
        except Exception as e:
            logger.error(f"Fatal error building PDF: {str(e)}")
            # Create a simple error document instead
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = [
                Paragraph(f"Error generating PDF for case: {case_title}", styles['CaseTitle']),
                Paragraph("There was an error processing the case text. This may be due to formatting issues in the original document.", styles['CaseNormal']),
                Paragraph(f"Case ID: {case_id}", styles['CaseNormal']),
                Paragraph(f"Error details: {str(e)}", styles['CaseItalic'])
            ]
            doc.build(elements)
            buffer.seek(0)
        
        # Return the PDF with appropriate headers
        buffer.seek(0)
        
        # Create a clean filename
        clean_title = ''.join(c if c.isalnum() else '_' for c in case_title)[:50]
        filename = f"case_{case_id}_{clean_title}.pdf"
        
        # Set Content-Disposition based on download parameter
        disposition = "attachment" if download else "inline"
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"{disposition}; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error generating case PDF: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Error generating case PDF: {str(e)}")

@router.get("/build-index")
async def build_document_index(workers: int = 8):
    """Build the case document index (admin endpoint)."""
    try:
        logger.info(f"Starting document index build with {workers} workers")
        success = case_document_service.build_indexes(num_workers=workers)
        
        if success:
            logger.info("Document indexes built successfully")
            return {"status": "success", "message": "Document indexes built successfully"}
        else:
            logger.warning("Index build process completed with warnings")
            return {
                "status": "warning",
                "message": "Index build process completed with warnings",
                "note": "Some files may not have been properly indexed. Fallback search will be used."
            }
    except Exception as e:
        logger.error(f"Failed to build document indexes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to build document indexes: {str(e)}")