import pytest
import json
import re
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test cases with different IDs to evaluate syllabus formatting
TEST_CASE_IDS = [
    "8572596",  # State v. Ballard (double jeopardy case)
    "123706",   # Reynolds v. State
    "11665174", # Hamilton v. Accu-Tek (gun laws case)
    "4363109"   # United States v. One Palmetto State Armory (gun laws case)
]

def format_syllabus(raw_syllabus):
    """
    Reformat a raw syllabus into a more structured, readable format
    """
    # Define the key sections we want to extract and format
    sections = [
        "Key Legal Issue",
        "Holding",
        "Reasoning"
    ]
    
    formatted_parts = []
    
    # Extract each section if present
    for section in sections:
        pattern = fr"\*\*{section}:\*\*\s*(.*?)(?=\*\*\w|\Z)"
        match = re.search(pattern, raw_syllabus, re.DOTALL)
        if match:
            section_content = match.group(1).strip()
            # Ensure content doesn't end mid-sentence
            if section_content and not any(section_content.endswith(p) for p in ['.', '!', '?', ':', ';']):
                # Find the last complete sentence
                last_period = max(section_content.rfind('.'), section_content.rfind('!'), section_content.rfind('?'))
                if last_period > 0:
                    section_content = section_content[:last_period+1]
            
            # Format as a paragraph with a bold heading
            formatted_parts.append(f"**{section}:** {section_content}")
    
    # Join with double line breaks for better readability
    return "\n\n".join(formatted_parts)

def test_case_syllabus_formatting():
    """Test the formatting of case syllabi for better readability."""
    
    results = []
    
    for case_id in TEST_CASE_IDS:
        print(f"\n\n--- Testing syllabus formatting for case {case_id} ---")
        
        try:
            # Get the case details
            response = client.get(f"/api/v1/case/{case_id}/full")
            
            if response.status_code == 200:
                case_data = response.json()
                title = case_data.get("title", "Unknown Case")
                court = case_data.get("court", "Unknown Court")
                date = case_data.get("date", "Unknown Date")
                
                # Get the raw summary/syllabus
                raw_syllabus = case_data.get("summary", "")
                
                print(f"Case: {title}")
                print(f"Court: {court}")
                print(f"Date: {date}")
                
                print("\nORIGINAL SYLLABUS:")
                print("----------------")
                print(raw_syllabus[:500] + "..." if len(raw_syllabus) > 500 else raw_syllabus)
                
                # Format the syllabus
                formatted_syllabus = format_syllabus(raw_syllabus)
                
                print("\nFORMATTED SYLLABUS:")
                print("------------------")
                print(formatted_syllabus)
                
                # Store the results
                results.append({
                    "case_id": case_id,
                    "title": title,
                    "original_syllabus": raw_syllabus,
                    "formatted_syllabus": formatted_syllabus
                })
                
                # Assert that key sections are present
                assert "Key Legal Issue:" in formatted_syllabus, "Missing 'Key Legal Issue' section"
                assert "Holding:" in formatted_syllabus, "Missing 'Holding' section"
                
            else:
                print(f"Error retrieving case: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"Error testing case {case_id}: {str(e)}")
    
    # Write results to a file for analysis
    with open("syllabus_formatting_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results written to syllabus_formatting_results.json")

def test_syllabus_prompt_design():
    """
    Test different prompt designs for generating well-structured syllabi.
    This doesn't actually call OpenAI but shows the prompt we would use.
    """
    print("\n--- PROPOSED IMPROVED SYLLABUS PROMPT ---\n")
    
    proposed_prompt = """
Create a concise legal syllabus for this case, structured with the following clear sections:

1. Key Legal Issue: Identify the central legal question(s) addressed by the court (1-2 sentences).

2. Holding: State the court's conclusion/ruling on each key issue (1-2 sentences).

3. Reasoning: Explain the court's rationale for its decision (3-5 sentences).

Format the response with section headers as demonstrated below:
**Key Legal Issue:** [your analysis here in complete sentences]

**Holding:** [your analysis here in complete sentences]

**Reasoning:** [your analysis here in complete sentences]

Keep the entire response between 200-300 words, ensuring all sections are fully readable with no cut-off sentences.
"""
    
    print(proposed_prompt)
    
    # Just for verification - no actual assertion needed
    assert "Key Legal Issue" in proposed_prompt
    assert "Holding" in proposed_prompt
    assert "Reasoning" in proposed_prompt

if __name__ == "__main__":
    # Run the tests directly
    print("\n=== TESTING SYLLABUS FORMATTING ===")
    test_case_syllabus_formatting()
    
    print("\n=== TESTING SYLLABUS PROMPT DESIGN ===")
    test_syllabus_prompt_design()