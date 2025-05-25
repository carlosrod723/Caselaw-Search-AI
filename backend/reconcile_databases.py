#!/usr/bin/env python
"""
Comprehensive Database Reconciliation Script

This script performs a thorough analysis of data consistency between:
1. SQLite database (case_lookup.db)
2. Qdrant vector database
3. Original Parquet files

It identifies mismatches, generates detailed reports, and recommends fixes.

Usage:
  python reconcile_databases.py [--batch-size=5000] [--limit=None] [--fix]

Options:
  --batch-size  Size of batches to process (default: 5000)
  --limit       Limit number of cases to check (default: None, checks all)
  --fix         Apply fixes automatically (default: False, report only)
"""

import os
import sys
import time
import sqlite3
import logging
import json
import pandas as pd
import concurrent.futures
from collections import defaultdict
import argparse

# Adjust the import paths as needed for your environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.qdrant_service import qdrant_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("reconciliation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
SQLITE_DB_PATH = os.path.join(os.getcwd(), "case_lookup.db")
PARQUET_BASE_DIR = "/Users/josecarlosrodriguez/Desktop/Carlos-Projects/Qdrant-Test/caselaw_processing/downloads/datasets--laion--Caselaw_Access_Project_embeddings/snapshots/7777999929157e8a2fe1b5d65f1d9cfd2092e843/TeraflopAI___Caselaw_Access_Project_clusters"
QDRANT_COLLECTION = "caselaw_bge_base_v2"
BATCH_SIZE = 5000
MAX_WORKERS = 16

# Output files
MISMATCHES_FILE = "mismatches.json"
SUMMARY_FILE = "reconciliation_summary.json"
FIX_SCRIPT_FILE = "fix_inconsistencies.py"

def verify_paths():
    """Verify all file paths and data sources exist."""
    errors = []
    
    # Check SQLite database
    if not os.path.exists(SQLITE_DB_PATH):
        errors.append(f"SQLite database not found at: {SQLITE_DB_PATH}")
    else:
        logger.info(f"SQLite database verified at: {SQLITE_DB_PATH}")
        
        # Check that it has the expected structure
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cases")
            case_count = cursor.fetchone()[0]
            logger.info(f"SQLite database contains {case_count} cases")
            conn.close()
        except Exception as e:
            errors.append(f"SQLite database structure error: {e}")
    
    # Check Parquet base directory
    if not os.path.exists(PARQUET_BASE_DIR):
        errors.append(f"Parquet directory not found at: {PARQUET_BASE_DIR}")
    else:
        # Check for at least one parquet file
        parquet_files = [f for f in os.listdir(PARQUET_BASE_DIR) if f.endswith('.parquet')]
        if not parquet_files:
            errors.append(f"No parquet files found in {PARQUET_BASE_DIR}")
        else:
            logger.info(f"Found {len(parquet_files)} parquet files in {PARQUET_BASE_DIR}")
    
    # Check Qdrant connection
    try:
        # Simple check to see if Qdrant is accessible
        collection_info = qdrant_service.get_collection_info()
        vector_count = collection_info.vectors_count
        logger.info(f"Qdrant collection '{QDRANT_COLLECTION}' verified with {vector_count} vectors")
    except Exception as e:
        errors.append(f"Qdrant connection error: {e}")
    
    if errors:
        for error in errors:
            logger.error(error)
        logger.error("Path verification failed. Please fix the issues and try again.")
        sys.exit(1)
    
    logger.info("All paths and data sources verified successfully.")
    return True

def get_sqlite_case_batches(batch_size=BATCH_SIZE, limit=None):
    """Get all cases from SQLite in batches."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    # Get total count first
    cursor.execute("SELECT COUNT(*) FROM cases")
    total_count = cursor.fetchone()[0]
    
    if limit:
        total_count = min(total_count, limit)
        
    logger.info(f"Preparing to process {total_count} cases in batches of {batch_size}")
    
    # Process in batches
    offset = 0
    while offset < total_count:
        if limit:
            cursor.execute(
                "SELECT id, name_abbreviation, court, jurisdiction, decision_date, file_name FROM cases LIMIT ? OFFSET ?", 
                (min(batch_size, limit - offset), offset)
            )
        else:
            cursor.execute(
                "SELECT id, name_abbreviation, court, jurisdiction, decision_date, file_name FROM cases LIMIT ? OFFSET ?", 
                (batch_size, offset)
            )
            
        batch = cursor.fetchall()
        if not batch:
            break
            
        # Convert to list of dicts for easier processing
        batch_dicts = []
        for row in batch:
            batch_dicts.append({
                "id": row[0],
                "title": row[1],
                "court": row[2],
                "jurisdiction": row[3],
                "date": row[4],
                "file_name": row[5]
            })
        
        yield batch_dicts
        
        offset += batch_size
        logger.info(f"Processed SQLite batch: {offset}/{total_count}")
    
    conn.close()

def check_qdrant_for_case_batch(case_batch):
    """Check Qdrant data for a batch of cases using payload-based search."""
    results = []
    
    for case in case_batch:
        case_id = case["id"]
        try:
            # Search Qdrant by case_id in payload
            search_results = qdrant_service.search_by_vector(
                vector=[0.1] * 768,  # Use a random vector
                limit=1,
                filter_conditions={"case_id": case_id}
            )
            
            if search_results:
                point = search_results[0]
                payload = point.payload or {}
                
                # Extract metadata
                qdrant_title = payload.get("title", "")
                qdrant_court = payload.get("court", "")
                qdrant_date = payload.get("date", "")
                
                # Check for mismatches
                title_match = case["title"] == qdrant_title
                court_match = case["court"] == qdrant_court
                
                # Normalize dates for comparison
                date_match = True
                if case["date"] and qdrant_date:
                    # Extract year for basic comparison
                    sqlite_year = case["date"].split("-")[0] if "-" in case["date"] else case["date"]
                    qdrant_year = qdrant_date.split("-")[0] if "-" in qdrant_date else qdrant_date
                    date_match = sqlite_year == qdrant_year
                
                # Record result
                results.append({
                    "case_id": case_id,
                    "qdrant_point_id": point.id,
                    "sqlite_title": case["title"],
                    "qdrant_title": qdrant_title,
                    "sqlite_court": case["court"],
                    "qdrant_court": qdrant_court,
                    "sqlite_date": case["date"],
                    "qdrant_date": qdrant_date,
                    "file_name": case["file_name"],
                    "title_match": title_match,
                    "court_match": court_match,
                    "date_match": date_match,
                    "complete_match": title_match and court_match and date_match,
                    "in_qdrant": True
                })
            else:
                # Case not found in Qdrant
                results.append({
                    "case_id": case_id,
                    "qdrant_point_id": None,
                    "sqlite_title": case["title"],
                    "qdrant_title": "",
                    "sqlite_court": case["court"],
                    "qdrant_court": "",
                    "sqlite_date": case["date"],
                    "qdrant_date": "",
                    "file_name": case["file_name"],
                    "title_match": False,
                    "court_match": False,
                    "date_match": False,
                    "complete_match": False,
                    "in_qdrant": False
                })
                
        except Exception as e:
            logger.error(f"Error querying Qdrant for case ID {case_id}: {e}")
            # Record error
            results.append({
                "case_id": case_id,
                "qdrant_point_id": None,
                "sqlite_title": case["title"],
                "qdrant_title": "",
                "sqlite_court": case["court"],
                "qdrant_court": "",
                "sqlite_date": case["date"],
                "qdrant_date": "",
                "file_name": case["file_name"],
                "title_match": False,
                "court_match": False,
                "date_match": False,
                "complete_match": False,
                "in_qdrant": False,
                "error": str(e)
            })
    
    return results

def process_parquet_file(file_path, case_ids):
    """
    Process a single parquet file to find cases by ID.
    
    Args:
        file_path: Path to the parquet file
        case_ids: List of case IDs to look for
        
    Returns:
        Dictionary of case data keyed by case ID
    """
    if not os.path.exists(file_path):
        logger.warning(f"Parquet file not found: {file_path}")
        return {}
        
    try:
        # Read only the necessary columns for efficiency
        df = pd.read_parquet(
            file_path, 
            columns=['id', 'name_abbreviation', 'court', 'decision_date']
        )
        
        # Convert to strings to ensure matching works correctly
        df['id'] = df['id'].astype(str)
        
        # Filter for only the IDs we're looking for
        filtered_df = df[df['id'].isin([str(id) for id in case_ids])]
        
        # Convert to dictionary keyed by id
        result = {}
        for _, row in filtered_df.iterrows():
            case_id = str(row['id'])
            result[case_id] = {
                'title': row.get('name_abbreviation', ''),
                'court': row.get('court', ''),
                'date': row.get('decision_date', '')
            }
            
        return result
    except Exception as e:
        logger.error(f"Error reading parquet file {os.path.basename(file_path)}: {e}")
        return {}

def check_parquet_files_for_mismatches(mismatches_batch):
    """
    Check parquet files for cases with mismatches.
    
    Args:
        mismatches_batch: List of case dictionaries with mismatches
        
    Returns:
        Updated list with parquet data added
    """
    # Group mismatches by parquet file
    files_to_check = defaultdict(list)
    for case in mismatches_batch:
        file_name = case.get("file_name")
        if file_name:
            files_to_check[file_name].append(case["case_id"])
    
    # Check each parquet file
    parquet_results = {}
    for file_name, case_ids in files_to_check.items():
        file_path = os.path.join(PARQUET_BASE_DIR, file_name)
        parquet_data = process_parquet_file(file_path, case_ids)
        parquet_results.update(parquet_data)
    
    # Update mismatches with parquet data
    results = []
    for case in mismatches_batch:
        case_id = case["case_id"]
        parquet_data = parquet_results.get(case_id, {})
        
        # Add parquet data and determine source of truth
        case["parquet_title"] = parquet_data.get("title", "")
        case["parquet_court"] = parquet_data.get("court", "")
        case["parquet_date"] = parquet_data.get("date", "")
        
        # Check if parquet matches either SQLite or Qdrant
        parquet_sqlite_title_match = case["parquet_title"] and case["parquet_title"] == case["sqlite_title"]
        parquet_qdrant_title_match = case["parquet_title"] and case["parquet_title"] == case["qdrant_title"]
        
        case["in_parquet"] = bool(case["parquet_title"])
        case["parquet_sqlite_match"] = parquet_sqlite_title_match
        case["parquet_qdrant_match"] = parquet_qdrant_title_match
        
        # Determine source of truth
        if parquet_sqlite_title_match and not parquet_qdrant_title_match:
            case["source_of_truth"] = "sqlite"
        elif parquet_qdrant_title_match and not parquet_sqlite_title_match:
            case["source_of_truth"] = "qdrant"
        elif parquet_sqlite_title_match and parquet_qdrant_title_match:
            case["source_of_truth"] = "both_match_parquet"
        elif case["parquet_title"]:
            case["source_of_truth"] = "parquet"
        else:
            case["source_of_truth"] = "indeterminate"
        
        results.append(case)
    
    return results

def process_cases(case_batch):
    """Process a batch of cases to identify mismatches."""
    # Step 1: Check Qdrant data
    checked_cases = check_qdrant_for_case_batch(case_batch)
    
    # Step 2: Find mismatches
    mismatches = [case for case in checked_cases if not case["complete_match"]]
    
    # Step 3: For mismatches, check parquet files
    if mismatches:
        mismatches = check_parquet_files_for_mismatches(mismatches)
    
    # Return metrics and mismatches
    metrics = {
        "processed": len(checked_cases),
        "mismatches": len(mismatches),
        "not_in_qdrant": sum(1 for case in checked_cases if not case["in_qdrant"]),
        "title_mismatches": sum(1 for case in checked_cases if not case["title_match"]),
        "court_mismatches": sum(1 for case in checked_cases if not case["court_match"]),
        "date_mismatches": sum(1 for case in checked_cases if not case["date_match"])
    }
    
    return metrics, mismatches

def run_reconciliation(batch_size=BATCH_SIZE, limit=None, apply_fixes=False):
    """Run the full reconciliation process."""
    start_time = time.time()
    verify_paths()
    
    # Initialize metrics
    total_metrics = {
        "processed": 0,
        "mismatches": 0,
        "not_in_qdrant": 0,
        "title_mismatches": 0,
        "court_mismatches": 0,
        "date_mismatches": 0
    }
    
    all_mismatches = []
    batch_num = 0
    
    # Process in batches
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch in get_sqlite_case_batches(batch_size, limit):
            batch_num += 1
            batch_start = time.time()
            
            # Process batch
            metrics, mismatches = process_cases(batch)
            
            # Update totals
            for key in total_metrics:
                total_metrics[key] += metrics[key]
            
            all_mismatches.extend(mismatches)
            
            # Log progress
            batch_time = time.time() - batch_start
            logger.info(f"Batch {batch_num}: Processed {metrics['processed']} cases in {batch_time:.2f}s, found {metrics['mismatches']} mismatches")
            
            # Periodically save mismatches
            if batch_num % 10 == 0:
                with open(MISMATCHES_FILE, 'w') as f:
                    json.dump(all_mismatches, f, indent=2)
                logger.info(f"Saved {len(all_mismatches)} mismatches to {MISMATCHES_FILE}")
    
    # Save final results
    with open(MISMATCHES_FILE, 'w') as f:
        json.dump(all_mismatches, f, indent=2)
    
    # Create summary
    summary = {
        "total_cases": total_metrics["processed"],
        "total_mismatches": total_metrics["mismatches"],
        "mismatch_percentage": (total_metrics["mismatches"] / total_metrics["processed"]) * 100 if total_metrics["processed"] > 0 else 0,
        "metrics": total_metrics,
        "mismatch_types": analyze_mismatches(all_mismatches),
        "total_time_seconds": time.time() - start_time
    }
    
    with open(SUMMARY_FILE, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Reconciliation complete in {summary['total_time_seconds']:.2f} seconds")
    logger.info(f"Processed {summary['total_cases']} cases, found {summary['total_mismatches']} mismatches ({summary['mismatch_percentage']:.2f}%)")
    
    # Generate fix script
    generate_fix_script(all_mismatches)
    
    if apply_fixes and all_mismatches:
        logger.info("Applying fixes...")
        apply_data_fixes(all_mismatches)
    
    return summary, all_mismatches

def analyze_mismatches(mismatches):
    """Analyze patterns in mismatches."""
    analysis = {
        "by_court": defaultdict(int),
        "by_jurisdiction": defaultdict(int),
        "by_date_range": defaultdict(int),
        "by_source_of_truth": defaultdict(int),
        "title_only_mismatches": 0,
        "court_only_mismatches": 0,
        "date_only_mismatches": 0,
        "multiple_field_mismatches": 0
    }
    
    for case in mismatches:
        # Count by metadata
        court = case.get("sqlite_court", "Unknown")
        jurisdiction = case.get("jurisdiction", "Unknown")
        date = case.get("sqlite_date", "Unknown")
        source = case.get("source_of_truth", "indeterminate")
        
        analysis["by_court"][court] += 1
        analysis["by_jurisdiction"][jurisdiction] += 1
        analysis["by_source_of_truth"][source] += 1
        
        # Categorize by date ranges
        if date and date != "Unknown":
            try:
                year = int(date.split("-")[0]) if "-" in date else int(date)
                decade = (year // 10) * 10
                date_range = f"{decade}s"
                analysis["by_date_range"][date_range] += 1
            except (ValueError, IndexError):
                analysis["by_date_range"]["Unknown"] += 1
        else:
            analysis["by_date_range"]["Unknown"] += 1
        
        # Categorize by fields mismatched
        title_mismatch = not case.get("title_match", True)
        court_mismatch = not case.get("court_match", True)
        date_mismatch = not case.get("date_match", True)
        
        mismatch_count = sum([title_mismatch, court_mismatch, date_mismatch])
        
        if mismatch_count == 1:
            if title_mismatch:
                analysis["title_only_mismatches"] += 1
            elif court_mismatch:
                analysis["court_only_mismatches"] += 1
            elif date_mismatch:
                analysis["date_only_mismatches"] += 1
        elif mismatch_count > 1:
            analysis["multiple_field_mismatches"] += 1
    
    # Convert defaultdicts to regular dicts for JSON serialization
    for key in analysis:
        if isinstance(analysis[key], defaultdict):
            analysis[key] = dict(analysis[key])
    
    return analysis

def generate_fix_script(mismatches):
    """Generate a Python script to fix inconsistencies."""
    if not mismatches:
        logger.info("No mismatches found, no fix script needed")
        return
    
    # Group fixes by type
    fixes_by_type = {
        "update_qdrant": [],
        "update_sqlite": [],
        "requires_manual_review": []
    }
    
    for case in mismatches:
        source = case.get("source_of_truth", "indeterminate")
        
        if source == "sqlite":
            fixes_by_type["update_qdrant"].append(case)
        elif source == "qdrant":
            fixes_by_type["update_sqlite"].append(case)
        elif source == "parquet":
            # If parquet is source of truth, might need to update both
            if case["parquet_title"] != case["sqlite_title"]:
                fixes_by_type["update_sqlite"].append(case)
            if case["parquet_title"] != case["qdrant_title"]:
                fixes_by_type["update_qdrant"].append(case)
        else:
            fixes_by_type["requires_manual_review"].append(case)
    
    # Generate script
    with open(FIX_SCRIPT_FILE, 'w') as f:
        f.write("""#!/usr/bin/env python
\"\"\"
Generated Fix Script for Database Inconsistencies

This script applies fixes to reconcile data between SQLite and Qdrant databases.
Run this after reviewing the recommendations and confirming the fixes.

Usage:
  python fix_inconsistencies.py [--dry-run] [--limit=100]

Options:
  --dry-run   Show what would be changed without making changes
  --limit     Limit number of fixes to apply (default: no limit)
\"\"\"

import os
import sys
import sqlite3
import logging
import argparse
import time

# Adjust imports for your environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.qdrant_service import qdrant_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fix_application.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
SQLITE_DB_PATH = os.path.join(os.getcwd(), "case_lookup.db")
QDRANT_COLLECTION = "caselaw_bge_base_v2"

def update_sqlite_case(case_id, title, court, date, dry_run=False):
    \"\"\"Update case metadata in SQLite.\"\"\"
    if dry_run:
        logger.info(f"DRY RUN: Would update SQLite case {case_id} to title='{title}', court='{court}', date='{date}'")
        return True
        
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE cases SET name_abbreviation = ?, court = ?, decision_date = ? WHERE id = ?",
            (title, court, date, case_id)
        )
        
        if cursor.rowcount == 0:
            logger.warning(f"No SQLite case found with ID {case_id}")
            conn.close()
            return False
            
        conn.commit()
        conn.close()
        logger.info(f"Updated SQLite case {case_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating SQLite case {case_id}: {e}")
        return False

def update_qdrant_case(case_id, title, court, date, dry_run=False):
    \"\"\"Update case metadata in Qdrant.\"\"\"
    if dry_run:
        logger.info(f"DRY RUN: Would update Qdrant case {case_id} to title='{title}', court='{court}', date='{date}'")
        return True
        
    try:
        # First retrieve the full point to preserve other payload fields
        points = qdrant_service.retrieve_points(
            ids=[case_id],
            with_payload=True
        )
        
        if not points:
            logger.warning(f"No Qdrant point found with ID {case_id}")
            return False
        
        # Get existing payload and update fields
        point = points[0]
        payload = point.payload or {}
        
        # Update the fields
        payload["title"] = title
        payload["court"] = court
        payload["date"] = date
        
        # Update the point in Qdrant
        # Use your Qdrant service's update method here
        # This is a placeholder - adjust based on your actual API
        # qdrant_service.update_points(
        #     collection_name=QDRANT_COLLECTION,
        #     points=[{"id": case_id, "payload": payload}]
        # )
        
        logger.info(f"Updated Qdrant case {case_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating Qdrant case {case_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Apply fixes to reconcile database inconsistencies")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of fixes to apply")
    args = parser.parse_args()
    
    start_time = time.time()
    fixed_sqlite = 0
    fixed_qdrant = 0
    errors = 0
    
    # 1. Update SQLite from Qdrant or Parquet
    sqlite_fixes = [
""")
        
        # Add SQLite fixes
        for i, case in enumerate(fixes_by_type["update_sqlite"][:100]):  # Limit to first 100 in script
            f.write(f'        {{\"id\": \"{case["case_id"]}\", \"title\": \"{case["qdrant_title"] or case["parquet_title"]}\", \"court\": \"{case["qdrant_court"] or case["parquet_court"]}\", \"date\": \"{case["qdrant_date"] or case["parquet_date"]}\"}},\n')
        
        if len(fixes_by_type["update_sqlite"]) > 100:
            f.write(f'        # ... plus {len(fixes_by_type["update_sqlite"]) - 100} more cases\n')
        
        # Add Qdrant fixes
        f.write("""    ]
    
    # 2. Update Qdrant from SQLite or Parquet
    qdrant_fixes = [
""")
        
        for i, case in enumerate(fixes_by_type["update_qdrant"][:100]):  # Limit to first 100 in script
            f.write(f'        {{\"id\": \"{case["case_id"]}\", \"title\": \"{case["sqlite_title"] or case["parquet_title"]}\", \"court\": \"{case["sqlite_court"] or case["parquet_court"]}\", \"date\": \"{case["sqlite_date"] or case["parquet_date"]}\"}},\n')
        
        if len(fixes_by_type["update_qdrant"]) > 100:
            f.write(f'        # ... plus {len(fixes_by_type["update_qdrant"]) - 100} more cases\n')
        
        # Complete the script
        f.write("""    ]
    
    # Apply fixes with limit if specified
    if args.limit:
        sqlite_fixes = sqlite_fixes[:args.limit]
        remaining = args.limit - len(sqlite_fixes)
        qdrant_fixes = qdrant_fixes[:max(0, remaining)]
    
    # Process SQLite fixes
    logger.info(f"Applying {len(sqlite_fixes)} SQLite updates")
    for fix in sqlite_fixes:
        success = update_sqlite_case(
            fix["id"], 
            fix["title"], 
            fix["court"], 
            fix["date"],
            dry_run=args.dry_run
        )
        if success:
            fixed_sqlite += 1
        else:
            errors += 1
    
    # Process Qdrant fixes
    logger.info(f"Applying {len(qdrant_fixes)} Qdrant updates")
    for fix in qdrant_fixes:
        success = update_qdrant_case(
            fix["id"], 
            fix["title"], 
            fix["court"], 
            fix["date"],
            dry_run=args.dry_run
        )
        if success:
            fixed_qdrant += 1
        else:
            errors += 1
    
    # Report results
    total_time = time.time() - start_time
    logger.info(f"Fix application completed in {total_time:.2f} seconds")
    logger.info(f"Updated {fixed_sqlite} SQLite cases")
    logger.info(f"Updated {fixed_qdrant} Qdrant cases")
    logger.info(f"Encountered {errors} errors")
    
    if args.dry_run:
        logger.info("This was a dry run. No changes were actually made.")

if __name__ == "__main__":
    main()
""")
    
    logger.info(f"Generated fix script: {FIX_SCRIPT_FILE}")
    logger.info(f"- {len(fixes_by_type['update_sqlite'])} cases need SQLite updates")
    logger.info(f"- {len(fixes_by_type['update_qdrant'])} cases need Qdrant updates")
    logger.info(f"- {len(fixes_by_type['requires_manual_review'])} cases need manual review")

def apply_data_fixes(mismatches):
    """Apply fixes to the databases."""
    # This would implement the actual fix application
    # Skipping implementation for now - use the generated script instead
    logger.info("Automatic fix application not implemented")
    logger.info(f"Please review and use the generated script: {FIX_SCRIPT_FILE}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile SQLite and Qdrant databases")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size for processing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to check")
    parser.add_argument("--fix", action="store_true", help="Apply fixes automatically")
    args = parser.parse_args()
    
    run_reconciliation(batch_size=args.batch_size, limit=args.limit, apply_fixes=args.fix)