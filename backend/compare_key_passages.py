# compare_key_passages.py

"""
Test script to compare OpenAI API key passage extraction with local extraction.

This script:
1. Retrieves a set of test cases from the database
2. For each case, gets the OpenAI-generated key passages (if available)
3. Extracts key passages using the client-side algorithm implemented in Python
4. Compares the results and timing

Usage:
  python compare_key_passages.py [--limit=10] [--case-id=123456]

Options:
  --limit=N       Number of random cases to test (default: 5)
  --case-id=ID    Test a specific case ID
"""

import sys
import time
import re
import sqlite3
import asyncio
import argparse
from typing import List, Dict, Any, Optional, Tuple

# For accessing OpenAI - use your existing service
from app.services.openai_service import openai_service

# For accessing case data - use your existing service
from app.services.case_document_service import case_document_service

# Function to implement the client-side extraction logic in Python
def extract_key_passages_local(case_text: str) -> List[str]:
    """Extract key passages using the same algorithm as the frontend."""
    # Skip if text is too short
    if not case_text or len(case_text) < 200:
        return []
    
    # Check if the text contains structured syllabus format
    has_syllabus_headings = bool(re.search(r'\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning', case_text, re.I))
    
    # Extract sentences from the text, avoiding syllabus content
    extracted_passages = []
    
    # Split the text into sentences
    sentences = re.split(r'(?<=[.!?])\s+', case_text)
    
    # Legal keywords to look for in important passages
    legal_keywords = [
        "we hold", "court held", "court found", "court ruled", "court concluded",
        "majority", "justice", "writes", "writing for", "dissent", "opinion",
        "amendment", "constitution", "statute", "pursuant to", "accordingly"
    ]
    
    # Words that indicate direct quotations
    quote_indicators = ["ruled that", "held that", "stated that", "concluded that", "found that"]
    
    # First, look for sentences that explicitly indicate court holdings
    for sentence in sentences:
        # Skip short sentences or sentences from syllabus sections
        if len(sentence) < 70 or re.search(r'\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning', sentence, re.I):
            continue
        
        # Prioritize sentences with explicit holding language
        contains_holding_language = any(keyword.lower() in sentence.lower() 
                                      for keyword in legal_keywords)
        
        # Check if it looks like a genuine quote from the court opinion
        looks_like_quote = any(indicator.lower() in sentence.lower() 
                             for indicator in quote_indicators)
        
        # If it contains legal terminology and looks like a genuine passage, add it
        if (contains_holding_language or looks_like_quote) and sentence not in extracted_passages:
            extracted_passages.append(sentence)
            
            # Stop after finding 2 good passages
            if len(extracted_passages) >= 2:
                break
    
    # If we couldn't find passages with holding language, look for sentences 
    # that appear to be from the case text rather than summary
    if len(extracted_passages) < 2:
        # Skip the first few paragraphs which might contain summary info
        later_sentences = sentences[min(10, len(sentences) // 3):]
        
        for sentence in later_sentences:
            # Skip short sentences or sentences from syllabus sections
            if len(sentence) < 70 or re.search(r'\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning', sentence, re.I):
                continue
            
            # Check for quotation marks which might indicate the text is quoting the court
            has_quotation_marks = '"' in sentence or '"' in sentence or '"' in sentence
            
            # Check for first person pronouns which might indicate direct court language
            has_first_person = bool(re.search(r'\b(we|our|us)\b', sentence, re.I))
            
            # If it has either quotation marks or first person language, consider it
            if (has_quotation_marks or has_first_person) and sentence not in extracted_passages:
                extracted_passages.append(sentence)
                
                # Stop after finding 2 good passages
                if len(extracted_passages) >= 2:
                    break
    
    # If we still don't have good passages, take sentences from the middle of the text
    # that don't match syllabus patterns to avoid duplication
    if len(extracted_passages) < 1:
        # Try to find substantial sentences from the middle of the text
        middle_index = len(sentences) // 2
        candidate_sentences = sentences[max(middle_index - 10, 0):min(middle_index + 10, len(sentences))]
        
        for sentence in candidate_sentences:
            # Exclude sentences that match syllabus section headings
            is_syllabus_section_heading = bool(re.search(r'\*\*Key Legal Issue|\*\*Holding|\*\*Reasoning', sentence, re.I))
            # Exclude sentences that are likely part of syllabus content
            likely_syllabus_content = "The court ruled" in sentence or \
                                     "The central legal question" in sentence or \
                                     "The court found that" in sentence
            
            if len(sentence) >= 70 and not is_syllabus_section_heading and \
               not likely_syllabus_content and sentence not in extracted_passages:
                extracted_passages.append(sentence)
                
                # Only need one good passage at this point
                break
    
    return extracted_passages

async def get_openai_key_passages(case_text: str) -> Tuple[List[str], float]:
    """Get key passages using the OpenAI API and measure the time taken."""
    # Skip if text is too short
    if not case_text or len(case_text) < 200:
        return [], 0
    
    # Use the same prompt as in your case.py
    passages_prompt = (
        "Extract 1-2 key passages (direct quotes) from this legal opinion that represent the most "
        "important holdings or statements of legal reasoning. Each passage must:\n\n"
        "1. Be an exact quote from the text (100-500 characters long)\n"
        "2. Contain complete sentences with proper punctuation\n"
        "3. Represent core legal principles or critical holdings\n\n"
        "Format each passage in quotation marks. Return only substantive legal quotes, not single words "
        "or short phrases. If you cannot find suitable full-sentence quotes, respond with 'No suitable passages found.'"
    )
    
    # Prepare the text for OpenAI - limit to first 8000 chars as in your code
    summarizable_content = case_text[:8000]
    
    # Measure time for OpenAI request
    start_time = time.time()
    
    try:
        # Use your existing OpenAI service
        result = await openai_service.async_chat_client.chat.completions.create(
            model="gpt-4o-mini",  # Use the same model as in your code
            messages=[
                {"role": "system", "content": passages_prompt},
                {"role": "user", "content": summarizable_content}
            ],
            max_tokens=500,
            temperature=0.1,
        )
        
        elapsed_time = time.time() - start_time
        ai_passages_text = result.choices[0].message.content.strip()
        
        # Extract passages from the response using the same logic as in case.py
        MIN_PASSAGE_LENGTH = 70
        MIN_WORD_COUNT = 10
        
        ai_passages = []
        if '"' in ai_passages_text and ai_passages_text.count('"') >= 2:
            # Extract content between quotes
            quote_matches = re.findall(r'"([^"]*)"', ai_passages_text)
            
            # Validate each potential passage
            for passage in quote_matches:
                passage = passage.strip()
                words = passage.split()
                
                # Only accept passages that meet quality criteria
                if len(passage) >= MIN_PASSAGE_LENGTH and len(words) >= MIN_WORD_COUNT:
                    # Check if it appears to be a sentence (has ending punctuation)
                    if re.search(r'[.!?]', passage):
                        ai_passages.append(passage)
        else:
            # Split by double newlines or numbered patterns
            potential_splits = re.split(r'\n\n|\d+\.\s+', ai_passages_text)
            for passage in potential_splits:
                passage = passage.strip()
                if passage and len(passage) >= MIN_PASSAGE_LENGTH and len(passage.split()) >= MIN_WORD_COUNT:
                    ai_passages.append(passage)
        
        # Trim any passages that are too long
        ai_passages = [p[:500] for p in ai_passages]
        
        return ai_passages, elapsed_time
        
    except Exception as e:
        print(f"Error with OpenAI: {e}")
        return [], time.time() - start_time

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Compare key passage extraction methods')
    parser.add_argument('--limit', type=int, default=5, help='Number of cases to test')
    parser.add_argument('--case-id', type=str, help='Specific case ID to test')
    args = parser.parse_args()
    
    # Connect to the database to get case IDs
    db_path = case_document_service.sqlite_db_path
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if args.case_id:
        # Test specific case
        cursor.execute("SELECT id FROM cases WHERE id = ?", (args.case_id,))
        case_ids = [row[0] for row in cursor.fetchall()]
        if not case_ids:
            print(f"Case ID {args.case_id} not found")
            return
    else:
        # Get random cases with substantial text
        cursor.execute("""
            SELECT id FROM cases 
            ORDER BY RANDOM() 
            LIMIT ?
        """, (args.limit,))
        case_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"Testing {len(case_ids)} cases")
    print("=" * 80)
    
    # Aggregate results
    total_openai_time = 0
    total_local_time = 0
    cases_with_openai_passages = 0
    cases_with_local_passages = 0
    
    for case_id in case_ids:
        print(f"\nProcessing case ID: {case_id}")
        
        # Get the case data with full text
        case_data = case_document_service.get_case_by_id(case_id, full_text=True)
        if not case_data or 'text' not in case_data or not case_data['text']:
            print(f"  No full text available for case {case_id}, skipping")
            continue
        
        case_text = case_data['text']
        title = case_data.get('name_abbreviation', 'Unknown Case')
        court = case_data.get('court', 'Unknown Court')
        date = case_data.get('decision_date', 'Unknown Date')
        
        print(f"  Title: {title}")
        print(f"  Court: {court}")
        print(f"  Date: {date}")
        print(f"  Text length: {len(case_text)} chars")
        
        # Get OpenAI passages with timing
        print("\n  Getting OpenAI key passages...")
        openai_start = time.time()
        openai_passages, openai_api_time = await get_openai_key_passages(case_text)
        openai_total_time = time.time() - openai_start
        total_openai_time += openai_total_time
        
        if openai_passages:
            cases_with_openai_passages += 1
            
        print(f"  OpenAI time: {openai_total_time:.2f}s (API call: {openai_api_time:.2f}s)")
        print(f"  OpenAI found {len(openai_passages)} passages")
        
        # Get local passages with timing
        print("\n  Getting local key passages...")
        local_start = time.time()
        local_passages = extract_key_passages_local(case_text)
        local_time = time.time() - local_start
        total_local_time += local_time
        
        if local_passages:
            cases_with_local_passages += 1
            
        print(f"  Local time: {local_time:.2f}s")
        print(f"  Local found {len(local_passages)} passages")
        
        # Show the passages
        print("\n  OpenAI Passages:")
        for i, passage in enumerate(openai_passages):
            print(f"  {i+1}. {passage[:100]}..." if len(passage) > 100 else f"  {i+1}. {passage}")
        
        print("\n  Local Passages:")
        for i, passage in enumerate(local_passages):
            print(f"  {i+1}. {passage[:100]}..." if len(passage) > 100 else f"  {i+1}. {passage}")
        
        print("-" * 80)
    
    # Print summary stats
    print("\nSUMMARY:")
    print("-" * 80)
    print(f"Cases tested: {len(case_ids)}")
    print(f"Cases with OpenAI passages: {cases_with_openai_passages} ({cases_with_openai_passages/len(case_ids)*100:.1f}%)")
    print(f"Cases with local passages: {cases_with_local_passages} ({cases_with_local_passages/len(case_ids)*100:.1f}%)")
    print(f"Average OpenAI time: {total_openai_time/len(case_ids):.2f}s")
    print(f"Average local time: {total_local_time/len(case_ids):.2f}s")
    print(f"Speed improvement: {(total_openai_time/total_local_time):.1f}x faster locally")

if __name__ == "__main__":
    asyncio.run(main())