#!/usr/bin/env python3
# test_prefetch_fallback.py - Test the combined prefetch and fallback strategy
# Run from the backend directory (no external dependencies)

import requests
import re
import time
import json
import sys
from concurrent.futures import ThreadPoolExecutor

# Configuration
API_BASE_URL = "http://localhost:8000"  # Change to your API server
TIMEOUT = 30  # Request timeout in seconds
MAX_CONCURRENT = 5  # Max concurrent requests for prefetching

def search_cases(query="battery tort", limit=10):
    """Perform a search to get case IDs for testing"""
    print(f"Searching for: '{query}' (limit: {limit})...")
    
    url = f"{API_BASE_URL}/api/v1/search?q={query}&limit={limit}"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.ok:
            data = response.json()
            results = data.get("results", [])
            print(f"Found {len(results)} search results")
            return [r.get("metadata", {}).get("case_id") for r in results if r.get("metadata", {}).get("case_id")]
        else:
            print(f"Search failed: {response.status_code} - {response.reason}")
            return []
    except Exception as e:
        print(f"Error during search: {e}")
        return []

def fetch_case_details(case_id):
    """Fetch detailed case information including content"""
    url = f"{API_BASE_URL}/api/v1/case/{case_id}/full"
    start_time = time.time()
    
    try:
        response = requests.get(url, timeout=TIMEOUT)
        elapsed = time.time() - start_time
        
        if response.ok:
            data = response.json()
            return {
                "case_id": case_id,
                "elapsed": elapsed,
                "success": True,
                "title": data.get("title", "Unknown Case"),
                "summary": data.get("summary", ""),
                "content": data.get("content", ""),
                "key_passages": data.get("keyPassages", []),
                "has_ai_passages": len(data.get("keyPassages", [])) > 0
            }
        else:
            print(f"Error fetching case {case_id}: {response.status_code} - {response.reason}")
            return {
                "case_id": case_id,
                "elapsed": elapsed,
                "success": False,
                "error": f"{response.status_code} - {response.reason}"
            }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Exception fetching case {case_id}: {e}")
        return {
            "case_id": case_id,
            "elapsed": elapsed,
            "success": False,
            "error": str(e)
        }

def prefetch_case_details(case_ids, max_workers=MAX_CONCURRENT):
    """Prefetch multiple cases concurrently (simulating frontend prefetching)"""
    print(f"Prefetching {len(case_ids)} cases with {max_workers} workers...")
    start_time = time.time()
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_case = {executor.submit(fetch_case_details, case_id): case_id for case_id in case_ids}
        for future in future_to_case:
            try:
                result = future.result()
                results.append(result)
                case_id = future_to_case[future]
                status = "✓" if result.get("success", False) else "✗"
                passages = len(result.get("key_passages", []))
                print(f"{status} Case {case_id}: {result.get('elapsed', 0):.2f}s - {passages} passages")
            except Exception as e:
                print(f"Error in future: {e}")
    
    total_time = time.time() - start_time
    print(f"Total prefetch time: {total_time:.2f}s")
    return results, total_time

def extract_fallback_passage(text, min_length=75, max_length=500):
    """Extract a fallback key passage from text when AI doesn't provide one"""
    if not text or len(text) < min_length:
        return None
        
    # Try to find sentences with key legal terms
    legal_keywords = ['therefore', 'court', 'held', 'rule', 'find', 'judge', 
                     'plaintiff', 'defendant', 'affirmed', 'reversed', 
                     'conclude', 'judgment', 'opinion', 'statute']
    
    # Clean and normalize text
    text = re.sub(r'\s+', ' ', text)
    
    # Extract sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Score sentences by length and keyword presence
    scored_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if min_length <= len(sentence) <= max_length:
            # Calculate keyword score
            keyword_count = sum(1 for kw in legal_keywords if kw.lower() in sentence.lower())
            
            # Bonus for sentences with quotation marks
            quote_bonus = 5 if '"' in sentence or "'" in sentence else 0
            
            # Length score - prefer medium length sentences
            length_score = min(10, len(sentence) / 50)
            
            # Total score
            total_score = keyword_count * 2 + quote_bonus + length_score
            
            scored_sentences.append((sentence, total_score))
    
    # If we found sentences, return the highest scoring one
    if scored_sentences:
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        return scored_sentences[0][0]
        
    # If no good sentence found, just take the first reasonable chunk
    if text and len(text) >= min_length:
        return text[:max_length].rstrip() + "..."
        
    return None

def analyze_and_apply_fallbacks(prefetch_results):
    """Analyze prefetch results and apply fallback passages for cases without AI passages"""
    cases_with_ai_passages = [r for r in prefetch_results if r.get("success", False) and r.get("has_ai_passages", False)]
    cases_without_passages = [r for r in prefetch_results if r.get("success", False) and not r.get("has_ai_passages", False)]
    
    print(f"\n=== Passage Availability Analysis ===")
    print(f"Total cases: {len(prefetch_results)}")
    print(f"Cases with AI passages: {len(cases_with_ai_passages)} ({len(cases_with_ai_passages)/len(prefetch_results)*100:.1f}%)")
    print(f"Cases needing fallback: {len(cases_without_passages)} ({len(cases_without_passages)/len(prefetch_results)*100:.1f}%)")
    
    # Apply fallbacks for cases without passages
    fallback_results = []
    for case in cases_without_passages:
        # Try to extract from summary first, then from content
        source_text = case.get("summary", "") or case.get("content", "")
        fallback_passage = extract_fallback_passage(source_text)
        
        fallback_results.append({
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "has_summary": bool(case.get("summary")),
            "has_content": bool(case.get("content")),
            "fallback_passage": fallback_passage,
            "fallback_length": len(fallback_passage) if fallback_passage else 0,
            "source_length": len(source_text)
        })
    
    # Display fallback passages
    if fallback_results:
        print("\n=== Fallback Passages Generated ===")
        for i, result in enumerate(fallback_results, 1):
            excerpt = result.get("fallback_passage", "")[:60] + "..." if result.get("fallback_passage") else "None"
            print(f"\n{i}. Case ID: {result.get('case_id')}")
            print(f"   Title: {result.get('title', '')}")
            print(f"   Has Summary: {'Yes' if result.get('has_summary') else 'No'}")
            print(f"   Fallback Length: {result.get('fallback_length', 0)}")
            print(f"   Excerpt: {excerpt}")
        
        # Calculate success rate
        success_count = sum(1 for r in fallback_results if r.get("fallback_passage"))
        print(f"\nFallback success rate: {success_count}/{len(fallback_results)} ({success_count/len(fallback_results)*100:.1f}%)")
    
    return fallback_results

def main():
    """Test prefetching and fallback passage generation"""
    print("=== Prefetch and Fallback Test ===")
    
    # Get case IDs either from command line or by search
    if len(sys.argv) > 1:
        case_ids = sys.argv[1:]
        print(f"Using provided case IDs: {case_ids}")
    else:
        # Perform a search to get case IDs
        case_ids = search_cases(query="battery assault tort", limit=10)
        if not case_ids:
            print("No cases found to test. Please provide case IDs as arguments.")
            sys.exit(1)
    
    # Simulate prefetching of case details (as would happen when search results load)
    prefetch_results, prefetch_time = prefetch_case_details(case_ids)
    
    # Analyze results and apply fallbacks where needed
    fallback_results = analyze_and_apply_fallbacks(prefetch_results)
    
    # Save detailed results to file
    output_file = "prefetch_fallback_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "prefetch_results": prefetch_results,
            "fallback_results": fallback_results,
            "prefetch_time": prefetch_time,
            "timestamp": time.time()
        }, f, indent=2)
    
    print(f"\nDetailed results saved to {output_file}")
    
    # Provide recommendations
    print("\n=== Recommendations ===")
    print("1. Implement aggressive prefetching of case details when search results load")
    print("2. Generate fallback passages client-side when AI doesn't provide any")
    print("3. Cache both AI and fallback passages to eliminate loading time")

if __name__ == "__main__":
    main()